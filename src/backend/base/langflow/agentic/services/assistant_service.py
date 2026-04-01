"""Assistant service with validation and retry logic."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any

from fastapi import HTTPException
from lfx.log.logger import logger

from langflow.agentic.helpers.code_extraction import extract_component_code
from langflow.agentic.helpers.error_handling import extract_friendly_error
from langflow.agentic.helpers.sse import (
    format_cancelled_event,
    format_complete_event,
    format_error_event,
    format_progress_event,
    format_token_event,
)
from langflow.agentic.helpers.validation import validate_component_code
from langflow.agentic.services.flow_executor import (
    execute_flow_file,
    execute_flow_file_streaming,
    extract_response_text,
)
from langflow.agentic.services.flow_types import (
    MAX_VALIDATION_RETRIES,
    VALIDATION_RETRY_TEMPLATE,
    VALIDATION_UI_DELAY_SECONDS,
)
from langflow.agentic.services.helpers.intent_classification import classify_intent


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
    current_input = input_value
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
    current_input = input_value

    # Classify intent using LLM (handles multi-language support)
    # This translates the input and determines if user wants to generate a component or ask a question
    intent_result = await classify_intent(
        text=input_value,
        global_variables=global_variables,
        user_id=user_id,
        session_id=session_id,
        provider=provider,
        model_name=model_name,
        api_key_var=api_key_var,
    )

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
        # First attempt (attempt=0) doesn't count as retry
        # Retries are attempt 1, 2, 3... up to max_retries
        for attempt in range(max_retries + 1):  # 0 = first try, 1..max_retries = retries
            # Check if client disconnected before starting
            if await check_cancelled():
                logger.info("Client disconnected, cancelling generation")
                yield format_cancelled_event()
                return

            logger.debug(f"Starting attempt {attempt}, is_disconnected provided: {is_disconnected is not None}")

            # Step 1: Generating (different step name based on intent)
            yield format_progress_event(
                "generating_component" if is_component_request else "generating",
                attempt,  # 0 for first try, 1+ for retries
                max_retries,  # max retries (not counting first try)
                message="Generating response...",
            )

            result = None
            cancelled = False
            flow_generator = execute_flow_file_streaming(
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
            try:
                # Use streaming executor to get token events
                async for event_type, event_data in flow_generator:
                    if event_type == "token":
                        # Only stream tokens for Q&A, not for component generation
                        if not is_component_request:
                            yield format_token_event(event_data)
                    elif event_type == "end":
                        # Flow completed, store result
                        result = event_data
                    elif event_type == "cancelled":
                        # Flow was cancelled due to client disconnect
                        logger.info("Flow execution cancelled by client disconnect")
                        cancelled = True
                        break
            except GeneratorExit:
                # This generator was closed (client disconnected)
                logger.info("Assistant generator closed, setting cancel event")
                cancel_event.set()
                await flow_generator.aclose()
                yield format_cancelled_event()
                return
            except HTTPException as e:
                friendly_msg = extract_friendly_error(str(e.detail))
                logger.error(f"Flow execution failed: {friendly_msg}")
                yield format_error_event(friendly_msg)
                return
            except (ValueError, RuntimeError, OSError) as e:
                friendly_msg = extract_friendly_error(str(e))
                logger.error(f"Flow execution failed: {friendly_msg}")
                yield format_error_event(friendly_msg)
                return

            # Handle cancellation
            if cancelled:
                yield format_cancelled_event()
                return

            if result is None:
                logger.error("Flow execution returned no result")
                yield format_error_event("Flow execution returned no result")
                return

            # Step 2: Generation complete
            yield format_progress_event(
                "generation_complete",
                attempt,
                max_retries,
                message="Response ready",
            )

            # For Q&A responses, return immediately without code extraction/validation
            if not is_component_request:
                yield format_complete_event(result)
                return

            # Only extract and validate code for component generation requests
            response_text = extract_response_text(result)
            code = extract_component_code(response_text)

            if not code:
                # No code found even though user asked for component generation
                # Return as plain text response
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
                attempt,
                max_retries,
                message="Extracting Python code from response...",
            )
            await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

            # Check for cancellation before validation
            if await check_cancelled():
                logger.info("Client disconnected before validation, cancelling")
                yield format_cancelled_event()
                return

            # Step 4: Validating
            yield format_progress_event(
                "validating",
                attempt,
                max_retries,
                message="Validating component code...",
            )
            await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

            validation = validate_component_code(code)

            if validation.is_valid:
                # Step 5a: Validated successfully
                logger.info(f"Component '{validation.class_name}' validated successfully")
                yield format_progress_event(
                    "validated",
                    attempt,
                    max_retries,
                    message=f"Component '{validation.class_name}' validated successfully!",
                )
                await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

                yield format_complete_event(
                    {
                        **result,
                        "validated": True,
                        "class_name": validation.class_name,
                        "component_code": code,
                        "validation_attempts": attempt,
                    }
                )
                return

            # Step 5b: Validation failed
            logger.warning(f"Validation failed (attempt {attempt}): {validation.error}")
            yield format_progress_event(
                "validation_failed",
                attempt,
                max_retries,
                message="Validation failed",
                error=validation.error,
                class_name=validation.class_name,
                component_code=code,
            )
            await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

            if attempt >= max_retries:
                # Max attempts reached, return with error
                yield format_complete_event(
                    {
                        **result,
                        "validated": False,
                        "validation_error": validation.error,
                        "validation_attempts": attempt,
                        "component_code": code,
                    }
                )
                return

            # Step 6: Retrying
            yield format_progress_event(
                "retrying",
                attempt,
                max_retries,
                message=f"Retrying with error context (attempt {attempt + 1}/{max_retries})...",
                error=validation.error,
            )
            await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

            current_input = VALIDATION_RETRY_TEMPLATE.format(error=validation.error, code=code)
    finally:
        # Always set cancel event when generator exits to stop any pending flow execution
        logger.debug("Assistant generator exiting, setting cancel event")
        cancel_event.set()
