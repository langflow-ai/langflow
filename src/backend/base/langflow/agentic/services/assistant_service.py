"""Assistant service with validation and retry logic."""

from __future__ import annotations

import asyncio
from contextlib import aclosing
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from lfx.log.logger import logger

from langflow.agentic.helpers.code_extraction import extract_component_code
from langflow.agentic.helpers.code_security import scan_code_security
from langflow.agentic.helpers.error_handling import extract_friendly_error
from langflow.agentic.helpers.input_sanitization import REFUSAL_MESSAGE, sanitize_input
from langflow.agentic.helpers.sse import (
    format_cancelled_event,
    format_complete_event,
    format_error_event,
    format_progress_event,
    format_token_event,
)
from langflow.agentic.helpers.streaming_retry import emit_execution_retry_events
from langflow.agentic.helpers.validation import validate_component_code, validate_component_runtime
from langflow.agentic.services.flow_executor import (
    execute_flow_file,
    execute_flow_file_streaming,
    extract_response_text,
)
from langflow.agentic.services.flow_types import (
    EXECUTION_RETRY_TEMPLATE,
    MAX_VALIDATION_RETRIES,
    OFF_TOPIC_REFUSAL_MESSAGE,
    VALIDATION_RETRY_TEMPLATE,
    VALIDATION_UI_DELAY_SECONDS,
    FlowExecutionError,
)
from langflow.agentic.services.helpers.intent_classification import classify_intent

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine

    from langflow.agentic.api.schemas import StepType


async def execute_flow_with_validation(
    flow_filename: str,
    input_value: str,
    global_variables: dict[str, str],
    *,
    max_retries: int = MAX_VALIDATION_RETRIES,
    user_id: str | None = None,
    session_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> dict:
    """Execute flow and validate the generated component code.

    If the response contains Python code, it validates the code.
    If validation fails, re-executes the flow with error context.
    Continues until valid code is generated or max retries reached.
    """
    # Layer 1: Input sanitization
    sanitization = sanitize_input(input_value)
    if not sanitization.is_safe:
        logger.warning(f"Input sanitization blocked request: {sanitization.violation}")
        return {"result": REFUSAL_MESSAGE}

    current_input = sanitization.sanitized_input
    attempt = 0

    while attempt <= max_retries:
        attempt += 1
        logger.info(f"Component generation attempt {attempt}/{max_retries + 1}")

        result = await execute_flow_file(
            flow_filename=flow_filename,
            input_value=current_input,
            global_variables=global_variables,
            verbose=True,
            user_id=user_id,
            session_id=session_id,
            provider=provider,
            model_name=model_name,
            api_key_var=api_key_var,
        )

        response_text = extract_response_text(result)
        code = extract_component_code(response_text)

        if not code:
            logger.debug("No Python code found in response, returning as-is")
            return result

        logger.info("Validating generated component code...")
        validation = validate_component_code(code)

        # Layer 3: Security scan on generated code
        security_result = scan_code_security(code)
        if not security_result.is_safe:
            violations_str = "; ".join(security_result.violations)
            logger.warning(f"Code security violations detected: {violations_str}")
            if attempt > max_retries:
                return {
                    **result,
                    "validated": False,
                    "validation_error": f"Security violations: {violations_str}",
                    "validation_attempts": attempt,
                }
            current_input = VALIDATION_RETRY_TEMPLATE.format(
                error=f"Security violations: {violations_str}. Do NOT use dangerous functions.",
                code=code,
            )
            continue

        if validation.is_valid:
            logger.info(f"Component '{validation.class_name}' validated successfully!")
            return {
                **result,
                "validated": True,
                "class_name": validation.class_name,
                "component_code": code,
                "validation_attempts": attempt,
            }

        logger.warning(f"Validation failed (attempt {attempt}): {validation.error}")

        if attempt > max_retries:
            logger.error(f"Max retries ({max_retries}) reached. Returning last result with error.")
            return {
                **result,
                "validated": False,
                "validation_error": validation.error,
                "validation_attempts": attempt,
            }

        current_input = VALIDATION_RETRY_TEMPLATE.format(error=validation.error, code=code)
        logger.info("Retrying with error context...")

    # Safety return: the while loop always returns via internal checks above
    return {
        **result,
        "validated": False,
        "validation_error": validation.error,
        "validation_attempts": attempt,
    }


async def execute_flow_with_validation_streaming(
    flow_filename: str,
    input_value: str,
    global_variables: dict[str, str],
    *,
    max_retries: int = MAX_VALIDATION_RETRIES,
    user_id: str | None = None,
    session_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
    is_disconnected: Callable[[], Coroutine[Any, Any, bool]] | None = None,
) -> AsyncGenerator[str, None]:
    """Execute flow with validation, yielding SSE progress and token events.

    SSE Event Flow:
        For component generation (detected from user input):
            1. generating_component - Show reasoning UI (no token streaming)
            2. extracting_code, validating, etc.

        For Q&A:
            1. generating - LLM is generating response
            1a. token events - Real-time token streaming
            2. complete - Done

    Note: Component generation is detected by analyzing the user's input.
    """
    # Layer 1: Input sanitization (before any LLM call)
    sanitization = sanitize_input(input_value)
    if not sanitization.is_safe:
        logger.warning(f"Input sanitization blocked request: {sanitization.violation}")
        yield format_complete_event({"result": REFUSAL_MESSAGE})
        return

    current_input = sanitization.sanitized_input

    # Classify intent using LLM (handles multi-language support)
    # This translates the input and determines if user wants to generate a component or ask a question
    # Use a separate session for intent classification to prevent
    # TranslationFlow messages from contaminating the assistant's memory
    intent_result = await classify_intent(
        text=current_input,
        global_variables=global_variables,
        user_id=user_id,
        provider=provider,
        model_name=model_name,
        api_key_var=api_key_var,
    )

    # Layer 4: Off-topic rejection (saves LLM API costs)
    if intent_result.intent == "off_topic":
        logger.info("Off-topic request detected, returning refusal")
        yield format_complete_event({"result": OFF_TOPIC_REFUSAL_MESSAGE})
        return

    # Check if this is a component generation request based on LLM classification
    is_component_request = intent_result.intent == "generate_component"
    logger.info(f"Intent classification: {intent_result.intent} (is_component_request={is_component_request})")

    # Create cancel event for propagating cancellation to flow executor
    cancel_event = asyncio.Event()

    # Helper to check if client disconnected
    async def check_cancelled() -> bool:
        if cancel_event.is_set():
            return True
        if is_disconnected is not None:
            return await is_disconnected()
        return False

    try:
        # max_retries=0 means 1 attempt (no retries), matching non-streaming semantics
        total_attempts = max_retries + 1

        for attempt in range(total_attempts):
            # Check if client disconnected before starting
            if await check_cancelled():
                logger.info("Client disconnected, cancelling generation")
                yield format_cancelled_event()
                return

            logger.debug(f"Starting attempt {attempt}, is_disconnected provided: {is_disconnected is not None}")

            # Step 1: Generating (different step name based on intent)
            step_name: StepType = "generating_component" if is_component_request else "generating"
            yield format_progress_event(
                step_name,
                attempt + 1,
                total_attempts,
                message="Generating response...",
            )

            result = None
            cancelled = False
            execution_error: str | None = None
            # aclosing guarantees the async generator is closed on every exit path
            # (normal completion, exception, or cancellation) — not relying on GC.
            async with aclosing(
                execute_flow_file_streaming(
                    flow_filename=flow_filename,
                    input_value=current_input,
                    global_variables=global_variables,
                    user_id=user_id,
                    session_id=session_id,
                    provider=provider,
                    model_name=model_name,
                    api_key_var=api_key_var,
                    is_disconnected=is_disconnected,
                    cancel_event=cancel_event,
                )
            ) as flow_generator:
                try:
                    async for event_type, event_data in flow_generator:
                        if event_type == "token":
                            # Stream tokens for both Q&A and component generation
                            # For components, the frontend shows live code preview
                            yield format_token_event(event_data)
                        elif event_type == "end":
                            result = event_data
                        elif event_type == "cancelled":
                            logger.info("Flow execution cancelled by client disconnect")
                            cancelled = True
                            break
                except GeneratorExit:
                    logger.info("Assistant generator closed, setting cancel event")
                    cancel_event.set()
                    yield format_cancelled_event()
                    return
                except FlowExecutionError as e:
                    # Internal retry loop reads the raw error to pick a friendly message;
                    # the public HTTP detail stays generic (see FlowExecutionError docstring).
                    execution_error = extract_friendly_error(e.original_error_message)
                except HTTPException as e:
                    execution_error = extract_friendly_error(str(e.detail))
                except (ValueError, RuntimeError, OSError) as e:
                    execution_error = extract_friendly_error(str(e))

            if cancelled:
                yield format_cancelled_event()
                return

            if execution_error is not None:
                logger.error(f"Flow execution failed (attempt {attempt + 1}): {execution_error}")

                # Q&A has no retry semantics — emit error and exit immediately
                if not is_component_request:
                    yield format_error_event(execution_error)
                    return

                async for event in emit_execution_retry_events(
                    attempt=attempt,
                    total_attempts=total_attempts,
                    error=execution_error,
                ):
                    yield event

                if attempt >= total_attempts - 1:
                    return  # complete event already emitted by the helper
                current_input = EXECUTION_RETRY_TEMPLATE.format(
                    error=execution_error,
                    original_input=sanitization.sanitized_input,
                )
                continue

            if result is None:
                logger.error("Flow execution returned no result")
                yield format_error_event("Flow execution returned no result")
                return

            # Step 2: Generation complete
            yield format_progress_event(
                "generation_complete",
                attempt + 1,
                total_attempts,
                message="Response ready",
            )

            # For Q&A responses, return immediately without code extraction/validation.
            # This prevents example code snippets in explanatory answers from being
            # mistakenly treated as component generation results.
            if not is_component_request:
                yield format_complete_event(result)
                return

            # Extract and validate component code from generation responses
            response_text = extract_response_text(result)
            code = extract_component_code(response_text)

            if not code:
                # No code found even though user asked for component generation
                yield format_complete_event(result)
                return

            # Check for cancellation before extraction
            if await check_cancelled():
                logger.info("Client disconnected before code extraction, cancelling")
                yield format_cancelled_event()
                return

            # Step 3: Extracting code (only shown when code is found)
            yield format_progress_event(
                "extracting_code",
                attempt + 1,
                total_attempts,
                message="Extracting Python code from response...",
            )
            await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

            # Check for cancellation before validation
            if await check_cancelled():
                logger.info("Client disconnected before validation, cancelling")
                yield format_cancelled_event()
                return

            # Step 4: Validating (include code so frontend can show preview)
            yield format_progress_event(
                "validating",
                attempt + 1,
                total_attempts,
                message="Validating component code...",
                component_code=code,
            )
            await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

            validation = validate_component_code(code)

            # Layer 3: Security scan on generated code
            security_result = scan_code_security(code)
            if not security_result.is_safe:
                violations_str = "; ".join(security_result.violations)
                logger.warning(f"Code security violations detected: {violations_str}")
                yield format_progress_event(
                    "validation_failed",
                    attempt,
                    max_retries,
                    message="Security violations detected in generated code",
                    error=f"Security violations: {violations_str}",
                    component_code=code,
                )
                await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

                if attempt >= total_attempts - 1:
                    yield format_complete_event(
                        {
                            **result,
                            "validated": False,
                            "validation_error": f"Security violations: {violations_str}",
                            "validation_attempts": attempt + 1,
                            "component_code": code,
                        }
                    )
                    return

                yield format_progress_event(
                    "retrying",
                    attempt,
                    max_retries,
                    message=f"Retrying with security context (attempt {attempt + 1}/{max_retries})...",
                    error=f"Security violations: {violations_str}",
                )
                await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)
                current_input = VALIDATION_RETRY_TEMPLATE.format(
                    error=f"Security violations: {violations_str}. "
                    "Do NOT use dangerous functions like os.system, subprocess, exec, eval. "
                    "Use Langflow's built-in integrations instead.",
                    code=code,
                )
                continue

            if validation.is_valid:
                # Runtime validation: try to actually instantiate the component
                runtime_error = validate_component_runtime(code, user_id=user_id)
                if runtime_error:
                    logger.warning(f"Runtime validation failed (attempt {attempt}): {runtime_error}")
                    validation = type(validation)(
                        is_valid=False,
                        code=code,
                        error=runtime_error,
                        class_name=validation.class_name,
                    )

            if validation.is_valid:
                logger.info(f"Component '{validation.class_name}' validated successfully")
                yield format_progress_event(
                    "validated",
                    attempt,
                    max_retries,
                    message=f"Component '{validation.class_name}' validated successfully!",
                    class_name=validation.class_name,
                    component_code=code,
                )
                await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

                yield format_complete_event(
                    {
                        **result,
                        "validated": True,
                        "class_name": validation.class_name,
                        "component_code": code,
                        "validation_attempts": attempt + 1,
                    }
                )
                return

            # Step 5b: Validation failed
            logger.warning(f"Validation failed (attempt {attempt}): {validation.error}")
            yield format_progress_event(
                "validation_failed",
                attempt + 1,
                total_attempts,
                message="Validation failed",
                error=validation.error,
                class_name=validation.class_name,
                component_code=code,
            )
            await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

            if attempt >= total_attempts - 1:
                # Max attempts reached, return with error
                yield format_complete_event(
                    {
                        **result,
                        "validated": False,
                        "validation_error": validation.error,
                        "validation_attempts": attempt + 1,
                        "component_code": code,
                    }
                )
                return

            # Step 6: Retrying
            yield format_progress_event(
                "retrying",
                attempt + 1,
                total_attempts,
                message="Retrying with error context...",
                error=validation.error,
            )
            await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

            current_input = VALIDATION_RETRY_TEMPLATE.format(error=validation.error, code=code)
    finally:
        # Always set cancel event when generator exits to stop any pending flow execution
        logger.debug("Assistant generator exiting, setting cancel event")
        cancel_event.set()
