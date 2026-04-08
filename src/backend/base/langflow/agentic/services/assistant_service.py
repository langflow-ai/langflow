"""Assistant service with validation and retry logic."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from lfx.components.tools.flow_builder_tools import drain_flow_events, init_working_flow, reset_working_flow
from lfx.graph.flow_builder.flow import flow_to_spec_summary
from lfx.log.logger import logger

from langflow.agentic.helpers.code_extraction import extract_component_code, extract_flow_json
from langflow.agentic.helpers.code_security import scan_code_security
from langflow.agentic.helpers.error_handling import extract_friendly_error
from langflow.agentic.helpers.input_sanitization import REFUSAL_MESSAGE, sanitize_input
from langflow.agentic.helpers.sse import (
    format_cancelled_event,
    format_complete_event,
    format_error_event,
    format_flow_preview_event,
    format_flow_update_event,
    format_progress_event,
    format_token_event,
)
from langflow.agentic.helpers.validation import validate_component_code, validate_component_runtime
from langflow.agentic.services.flow_executor import (
    execute_flow_file,
    execute_flow_file_streaming,
    extract_response_text,
)
from langflow.agentic.services.flow_types import (
    FLOW_BUILDER_ASSISTANT_FLOW,
    MAX_VALIDATION_RETRIES,
    OFF_TOPIC_REFUSAL_MESSAGE,
    VALIDATION_RETRY_TEMPLATE,
    VALIDATION_UI_DELAY_SECONDS,
)
from langflow.agentic.services.helpers.intent_classification import classify_intent

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine

    from langflow.agentic.api.schemas import StepType


async def _get_current_flow_summary(flow_id: str | None) -> str | None:
    """Build a spec-like summary and initialize working flow from the user's canvas."""
    if not flow_id:
        return None
    try:
        from uuid import UUID

        from lfx.services.deps import session_scope

        from langflow.services.database.models.flow import Flow

        async with session_scope() as session:
            flow = await session.get(Flow, UUID(flow_id))
            if flow and flow.data:
                flow_dict = {"name": flow.name, "data": flow.data}
                # Initialize working flow so tools can read/write the actual canvas
                init_working_flow(flow_dict, flow_id)
                return flow_to_spec_summary(flow_dict)
    except Exception:  # noqa: BLE001
        logger.debug("Could not load current flow for context", exc_info=True)
    return None


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

        # Check if the flow builder tools produced updates
        flow_updates = drain_flow_events()
        if flow_updates:
            logger.info("Flow updates from agent in non-streaming response")
            reset_working_flow()
            return {**result, "has_flow": True, "flow_updates": flow_updates}

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

    # Route based on intent classification
    is_component_request = intent_result.intent == "generate_component"
    is_flow_request = intent_result.intent == "build_flow"
    logger.info(f"Intent classification: {intent_result.intent}")

    # Reset flow builder state for each request
    reset_working_flow()

    # Inject current flow context for all intents so the agent
    # can answer questions about or modify the user's canvas
    current_flow_summary = await _get_current_flow_summary(global_variables.get("FLOW_ID"))
    if current_flow_summary:
        current_input = f"[Current flow on canvas:\n{current_flow_summary}\n]\n\n{current_input}"

    # Use the flow builder assistant for flow building requests
    if is_flow_request:
        flow_filename = FLOW_BUILDER_ASSISTANT_FLOW

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
            if is_component_request:
                step_name: StepType = "generating_component"
            elif is_flow_request:
                step_name = "generating_flow"
            else:
                step_name = "generating"
            yield format_progress_event(
                step_name,
                attempt + 1,
                total_attempts,
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
                has_flow_updates = False
                async for event_type, event_data in flow_generator:
                    if event_type == "token":
                        # Drain any flow_update events from tools
                        for update in drain_flow_events():
                            has_flow_updates = True
                            yield format_flow_update_event(update)
                        yield format_token_event(event_data)
                    elif event_type == "flow_preview":
                        has_flow_updates = True
                        yield format_flow_preview_event(
                            flow_data=event_data.get("flow", {}),
                            name=event_data.get("name", ""),
                            node_count=event_data.get("node_count", 0),
                            edge_count=event_data.get("edge_count", 0),
                        )
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
                attempt + 1,
                total_attempts,
                message="Response ready",
            )

            # Extract the response text and check for flow or component artifacts
            response_text = extract_response_text(result)

            # Drain any remaining flow events
            for update in drain_flow_events():
                has_flow_updates = True
                yield format_flow_update_event(update)

            if has_flow_updates:
                yield format_complete_event({**result, "has_flow": True})
                reset_working_flow()
                return

            # Fallback: check for flow JSON in the response text.
            # This only triggers if the agent produced raw JSON instead of using
            # its tools -- likely a prompt or tool execution issue.
            flow_data = extract_flow_json(response_text)
            if flow_data and "data" in flow_data and "nodes" in flow_data.get("data", {}):
                logger.warning("Flow data found as text instead of via tools -- agent may not be using tools correctly")
                yield format_flow_preview_event(
                    flow_data=flow_data,
                    name=flow_data.get("name", ""),
                    node_count=len(flow_data["data"].get("nodes", [])),
                    edge_count=len(flow_data["data"].get("edges", [])),
                )
                yield format_complete_event({**result, "has_flow": True})
                return

            # For Q&A responses, return immediately without code extraction/validation.
            # This prevents example code snippets in explanatory answers from being
            # mistakenly treated as component generation results.
            if not is_component_request:
                yield format_complete_event(result)
                return

            # Extract and validate component code from generation responses
            code = extract_component_code(response_text)

            if not code:
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
        reset_working_flow()
