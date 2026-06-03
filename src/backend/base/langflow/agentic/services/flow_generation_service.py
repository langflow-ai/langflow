"""Flow generation service — SSE pipeline for natural-language → multi-node flow.

Takes a user prompt, builds the component catalog, calls the FlowGenerator LLM
graph, extracts compact JSON from the response, validates it against the live
component registry, expands it to full ReactFlow format, and emits SSE events
at each step.

Usage:
    from langflow.agentic.services.flow_generation_service import generate_flow_streaming
    async for sse_event in generate_flow_streaming(...):
        yield sse_event
"""

from __future__ import annotations

import asyncio
from contextlib import aclosing
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.agentic.helpers.component_catalog import (
    build_component_catalog_prompt,
    get_all_types_dict,
)
from langflow.agentic.helpers.flow_extraction import extract_compact_flow
from langflow.agentic.helpers.flow_validation import validate_compact_flow
from langflow.agentic.helpers.sse import (
    format_cancelled_event,
    format_complete_event,
    format_error_event,
    format_progress_event,
    format_token_event,
)
from langflow.agentic.services.flow_executor import (
    execute_flow_file_streaming,
    extract_response_text,
)
from langflow.agentic.services.flow_types import FlowExecutionError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine
    from uuid import UUID

# Maximum characters of flow context to inject (prevents token overruns)
_MAX_FLOW_CONTEXT_CHARS = 4000

# Retry template when the LLM generates invalid flow JSON
_FLOW_RETRY_TEMPLATE = """\
{original_input}

---
The previous attempt produced invalid flow JSON. Errors found:
{errors}

Fix these issues and output ONLY the corrected compact flow JSON object.
"""


async def _get_flow_context(
    flow_id: str | None,
    user_id: Any,
) -> str:
    """Return a text representation of the user's current flow, or empty string."""
    if not flow_id:
        return ""
    try:
        from langflow.agentic.utils.flow_graph import get_flow_graph_representations

        result = await get_flow_graph_representations(flow_id, user_id)
        if "error" in result or not result.get("text_repr"):
            return ""

        text_repr: str = result["text_repr"]
        vertex_count = result.get("vertex_count", 0)

        # Skip injecting context for empty or near-empty flows
        if vertex_count == 0:
            return ""

        # Truncate to avoid token overruns
        if len(text_repr) > _MAX_FLOW_CONTEXT_CHARS:
            text_repr = text_repr[:_MAX_FLOW_CONTEXT_CHARS] + "\n... (truncated)"

        return (
            f"\n## Current Flow\n"
            f"The user's canvas currently has these components and connections:\n"
            f"{text_repr}\n"
            f"\nApply the user's requested changes to this existing flow structure. "
            f"Preserve components and connections that the user did not mention changing.\n"
        )
    except Exception:  # noqa: BLE001
        return ""


def _build_user_message(
    user_input: str,
    catalog: str,
    flow_context: str,
) -> str:
    """Compose the full user message sent to the FlowGenerator LLM."""
    parts = [
        "## Available Components",
        catalog,
    ]
    if flow_context:
        parts.append(flow_context)
    parts += [
        "## User Request",
        user_input,
    ]
    return "\n".join(parts)


async def generate_flow_streaming(
    user_input: str,
    *,
    flow_id: str | None = None,
    user_id: str | UUID | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
    global_variables: dict[str, str] | None = None,
    max_retries: int = 2,
    session_id: str | None = None,
    is_disconnected: Callable[[], Coroutine[Any, Any, bool]] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream SSE events for natural-language → multi-node flow generation.

    Pipeline:
        1. Build component catalog from live registry
        2. Inject current flow context (for edit requests)
        3. Call FlowGenerator LLM (streaming tokens)
        4. Extract compact JSON from LLM response
        5. Validate against registry (retry with error context on failure)
        6. Expand to full ReactFlow JSON
        7. Emit complete event with flow_data + expanded_flow

    Args:
        user_input: Translated user request (from intent classifier).
        flow_id: Current flow ID for edit context injection (optional).
        user_id: User ID for flow lookup and graph session.
        provider: LLM provider (e.g., "OpenAI").
        model_name: LLM model name (e.g., "gpt-4o-mini").
        api_key_var: API key variable name.
        global_variables: Global variables dict for the graph execution context.
        max_retries: Number of retry attempts on validation failure (default 2).
        session_id: Session ID for multi-turn editing context.
        is_disconnected: Async callable that returns True if client disconnected.

    Yields:
        SSE-formatted strings (data: {...}\\n\\n).
    """
    total_attempts = max_retries + 1
    cancel_event = asyncio.Event()

    async def check_cancelled() -> bool:
        if cancel_event.is_set():
            return True
        if is_disconnected is not None:
            return await is_disconnected()
        return False

    try:
        # --- Step 1: Build catalog ---
        yield format_progress_event(
            "generating_flow",
            1,
            total_attempts,
            message="Analyzing available components...",
        )

        try:
            catalog, all_types_dict = await asyncio.gather(
                build_component_catalog_prompt(),
                get_all_types_dict(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to build component catalog: {exc}")
            yield format_error_event("Failed to load component catalog. Please try again.")
            return

        # --- Step 2: Get flow context (for edit requests) ---
        flow_context = await _get_flow_context(flow_id, user_id)

        # Base user message (catalog + context + request)
        base_message = _build_user_message(user_input, catalog, flow_context)
        current_input = base_message

        for attempt in range(total_attempts):
            if await check_cancelled():
                yield format_cancelled_event()
                return

            # --- Step 3: Generate via LLM ---
            yield format_progress_event(
                "generating_flow",
                attempt + 1,
                total_attempts,
                message="Designing your flow...",
            )

            result = None
            cancelled = False
            execution_error: str | None = None
            full_response = ""

            # Use a distinct session namespace so the flow generator's message
            # storage doesn't collide with the translation flow's session data.
            flow_session_id = f"flowgen_{session_id}" if session_id else None

            async with aclosing(
                execute_flow_file_streaming(
                    "flow_generator.py",
                    input_value=current_input,
                    global_variables=global_variables,
                    user_id=str(user_id) if user_id else None,
                    session_id=flow_session_id,
                    provider=provider,
                    model_name=model_name,
                    api_key_var=api_key_var,
                    is_disconnected=is_disconnected,
                    cancel_event=cancel_event,
                )
            ) as flow_gen:
                try:
                    async for event_type, event_data in flow_gen:
                        if event_type == "token":
                            full_response += event_data
                            yield format_token_event(event_data)
                        elif event_type == "end":
                            result = event_data
                        elif event_type == "cancelled":
                            cancelled = True
                            break
                except GeneratorExit:
                    cancel_event.set()
                    yield format_cancelled_event()
                    return
                except FlowExecutionError as exc:
                    execution_error = exc.original_error_message
                except Exception as exc:  # noqa: BLE001
                    execution_error = str(exc)

            if cancelled:
                yield format_cancelled_event()
                return

            if execution_error is not None:
                logger.error(f"Flow generator execution error (attempt {attempt + 1}): {execution_error}")
                yield format_error_event(f"Flow generation failed: {execution_error}")
                return

            # Use result text if tokens didn't accumulate (non-streaming fallback)
            if not full_response and result is not None:
                full_response = extract_response_text(result)

            if not full_response:
                logger.error("Flow generator returned empty response")
                yield format_error_event("Flow generator returned an empty response.")
                return

            if await check_cancelled():
                yield format_cancelled_event()
                return

            # --- Step 4: Extract compact JSON ---
            yield format_progress_event(
                "extracting_flow",
                attempt + 1,
                total_attempts,
                message="Extracting flow structure...",
            )

            compact_data = extract_compact_flow(full_response)
            if compact_data is None:
                logger.warning(f"Failed to extract compact flow (attempt {attempt + 1})")
                if attempt >= total_attempts - 1:
                    yield format_error_event(
                        "Could not extract a valid flow from the LLM response. "
                        "The model did not produce JSON in the expected format."
                    )
                    return
                # Retry with explicit instruction to output JSON only
                current_input = (
                    base_message + "\n\n---\nIMPORTANT: Output ONLY the JSON object. "
                    "No explanation, no markdown fences, no preamble."
                )
                yield format_progress_event(
                    "retrying",
                    attempt + 1,
                    total_attempts,
                    message="Retrying — model must output JSON only...",
                )
                continue

            # --- Step 5: Validate ---
            yield format_progress_event(
                "validating_flow",
                attempt + 1,
                total_attempts,
                message="Validating components and connections...",
            )

            validation = await validate_compact_flow(
                compact_data,
                all_types_dict=all_types_dict,
            )

            if validation.warnings:
                for w in validation.warnings:
                    logger.info(f"Flow validation warning: {w}")

            if not validation.is_valid:
                logger.warning(f"Flow validation failed (attempt {attempt + 1}): {validation.errors}")
                yield format_progress_event(
                    "validation_failed",
                    attempt + 1,
                    total_attempts,
                    message="Flow validation failed",
                    error="; ".join(validation.errors),
                )

                if attempt >= total_attempts - 1:
                    yield format_complete_event(
                        {
                            "result": full_response,
                            "validated": False,
                            "flow_validated": False,
                            "validation_error": "; ".join(validation.errors),
                            "validation_attempts": attempt + 1,
                        }
                    )
                    return

                errors_str = "\n".join(f"- {e}" for e in validation.errors)
                current_input = _FLOW_RETRY_TEMPLATE.format(
                    original_input=base_message,
                    errors=errors_str,
                )
                yield format_progress_event(
                    "retrying",
                    attempt + 1,
                    total_attempts,
                    message=f"Retrying with validation feedback (attempt {attempt + 2}/{total_attempts})...",
                    error="; ".join(validation.errors),
                )
                continue

            # --- Step 6: Expand to full ReactFlow JSON ---
            corrected_compact = validation.compact_data
            yield format_progress_event(
                "validated_flow",
                attempt + 1,
                total_attempts,
                message="Flow validated! Preparing canvas data...",
                flow_data=corrected_compact,  # sent here so the frontend can animate nodes
            )

            try:
                from langflow.processing.expand_flow import expand_compact_flow

                expanded_flow = expand_compact_flow(corrected_compact, all_types_dict)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to expand compact flow: {exc}")
                yield format_error_event(f"Failed to expand flow to canvas format: {exc}")
                return

            # --- Step 7: Complete ---
            node_count = len(corrected_compact.get("nodes", []))
            edge_count = len(corrected_compact.get("edges", []))
            logger.info(
                f"Flow generation complete: {node_count} nodes, {edge_count} edges"
                f" (attempt {attempt + 1}/{total_attempts})"
            )

            yield format_complete_event(
                {
                    "result": full_response,
                    "validated": True,
                    "flow_validated": True,
                    "flow_data": corrected_compact,
                    "expanded_flow": expanded_flow,
                    "node_count": node_count,
                    "edge_count": edge_count,
                    "validation_attempts": attempt + 1,
                    "warnings": validation.warnings if validation.warnings else None,
                }
            )
            return

    finally:
        logger.debug("Flow generation generator exiting, setting cancel event")
        cancel_event.set()
