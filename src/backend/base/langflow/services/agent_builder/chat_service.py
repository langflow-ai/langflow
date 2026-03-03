"""Agent chat orchestration — resolves context and streams responses."""

import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import HTTPException
from lfx.events.event_manager import create_default_event_manager
from lfx.interface.components import get_and_cache_all_types_dict
from lfx.load import aload_flow_from_json
from lfx.log.logger import logger

from langflow.agentic.helpers.sse import (
    format_cancelled_event,
    format_complete_event,
    format_error_event,
    format_token_event,
)
from langflow.agentic.services.flow_executor import _run_graph_with_events
from langflow.agentic.services.flow_preparation import inject_model_into_flow
from langflow.agentic.services.flow_types import STREAMING_QUEUE_MAX_SIZE, FlowExecutionResult
from langflow.agentic.services.helpers.event_consumer import consume_streaming_events
from langflow.agentic.services.provider_service import (
    PREFERRED_PROVIDERS,
    get_default_model,
    get_enabled_providers_for_user,
)
from langflow.services.agent_builder.flow_generator import generate_agent_flow
from langflow.services.deps import get_settings_service


async def resolve_provider_and_model(
    user_id: uuid.UUID,
    session: Any,
    provider: str | None,
    model_name: str | None,
) -> tuple[str, str]:
    """Resolve which provider and model to use for agent chat.

    Raises:
        HTTPException: If no provider is configured or provider is invalid.
    """
    from lfx.base.models.unified_models import get_model_provider_variable_mapping

    enabled_providers, _ = await get_enabled_providers_for_user(user_id, session)
    if not enabled_providers:
        raise HTTPException(
            status_code=400,
            detail="No model provider is configured. Please configure at least one model provider in Settings.",
        )

    resolved_provider = _pick_provider(provider, enabled_providers)
    provider_variable_map = get_model_provider_variable_mapping()
    if resolved_provider not in provider_variable_map:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {resolved_provider}")

    resolved_model = model_name or get_default_model(resolved_provider) or ""
    return resolved_provider, resolved_model


async def stream_agent_chat(
    *,
    system_prompt: str,
    tool_components: list[str],
    input_value: str,
    provider: str,
    model_name: str,
    user_id: str,
    session_id: str,
    global_variables: dict[str, str],
    is_disconnected: Any = None,
) -> AsyncGenerator[str, None]:
    """Execute agent flow and yield SSE events.

    Generates the flow JSON dynamically, loads it as a graph,
    injects the model, and streams token events back to the client.
    """
    tool_codes, tool_outputs = await _resolve_tool_info(tool_components)
    flow_data = generate_agent_flow(
        system_prompt=system_prompt,
        tool_class_names=tool_components,
        tool_codes=tool_codes,
        tool_outputs=tool_outputs,
    )
    flow_data = inject_model_into_flow(flow_data, provider, model_name)

    try:
        graph = await aload_flow_from_json(flow_data, disable_logs=True)
    except (ValueError, OSError, KeyError) as e:
        logger.error(f"Agent flow preparation error: {e}")
        yield format_error_event("Failed to prepare agent flow.")
        return

    event_queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue(maxsize=STREAMING_QUEUE_MAX_SIZE)
    event_manager = create_default_event_manager(event_queue)
    execution_result = FlowExecutionResult()

    flow_task = asyncio.create_task(
        _run_graph_with_events(
            graph=graph,
            input_value=input_value,
            global_variables=global_variables,
            user_id=user_id,
            session_id=session_id,
            event_manager=event_manager,
            event_queue=event_queue,
            execution_result=execution_result,
        )
    )

    cancelled = False
    try:
        async for event_type, chunk in consume_streaming_events(event_queue, is_disconnected):
            if event_type == "token":
                yield format_token_event(chunk.decode() if isinstance(chunk, bytes) else str(chunk))
            elif event_type == "end":
                break
            elif event_type == "cancelled":
                cancelled = True
                break
    except GeneratorExit:
        logger.info("Agent chat stream closed by client")
        cancelled = True
    finally:
        if not flow_task.done():
            flow_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await flow_task

    if cancelled:
        yield format_cancelled_event()
        return

    if execution_result.has_error:
        yield format_error_event("An error occurred during agent execution.")
        return

    result = execution_result.result if execution_result.has_result else {}
    yield format_complete_event(result)


async def _resolve_tool_info(
    tool_names: list[str],
) -> tuple[dict[str, str], dict[str, list[dict]]]:
    """Look up tool code and outputs from the component registry.

    Returns:
        (tool_codes, tool_outputs): codes maps name→source code,
        outputs maps name→list of output dicts from the registry.
    """
    if not tool_names:
        return {}, {}

    all_types = await get_and_cache_all_types_dict(settings_service=get_settings_service())
    codes: dict[str, str] = {}
    outputs: dict[str, list[dict]] = {}
    for name in tool_names:
        for components in all_types.values():
            if name in components:
                comp_info = components[name]
                code_field = comp_info.get("template", {}).get("code", {})
                code_value = code_field.get("value", "")
                if code_value:
                    codes[name] = code_value
                comp_outputs = comp_info.get("outputs", [])
                if comp_outputs:
                    outputs[name] = comp_outputs
                break
    return codes, outputs


def _pick_provider(requested: str | None, enabled: list[str]) -> str:
    """Pick the best provider from request or defaults."""
    if requested:
        if requested not in enabled:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{requested}' is not configured. Available: {enabled}",
            )
        return requested

    for preferred in PREFERRED_PROVIDERS:
        if preferred in enabled:
            return preferred
    return enabled[0]
