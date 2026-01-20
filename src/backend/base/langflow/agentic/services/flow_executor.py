"""Flow execution service."""

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from lfx.base.models.unified_models import get_provider_config
from lfx.events.event_manager import EventManager, create_default_event_manager
from lfx.log.logger import logger
from lfx.run.base import run_flow

# Base path for flow JSON files
FLOWS_BASE_PATH = Path(__file__).parent.parent / "flows"

# Streaming configuration
STREAMING_QUEUE_MAX_SIZE = 1000
STREAMING_EVENT_TIMEOUT_SECONDS = 300.0


@dataclass
class FlowExecutionResult:
    """Holds the result or error from async flow execution."""

    result: dict[str, Any] = field(default_factory=dict)
    error: Exception | None = None

    @property
    def has_error(self) -> bool:
        return self.error is not None

    @property
    def has_result(self) -> bool:
        return bool(self.result)


def inject_model_into_flow(
    flow_data: dict,
    provider: str,
    model_name: str,
    api_key_var: str | None = None,
) -> dict:
    """Inject model configuration into the flow's Agent component.

    Args:
        flow_data: The flow JSON as a dict
        provider: The provider name (e.g., "OpenAI", "Anthropic")
        model_name: The model name (e.g., "gpt-4o", "claude-sonnet-4-5-20250929")
        api_key_var: Optional API key variable name. If not provided, uses provider's default.

    Returns:
        Modified flow data with the model configuration injected

    Raises:
        ValueError: If provider is unknown
    """
    # Get provider config from unified models
    provider_config = get_provider_config(provider)

    # Use provided api_key_var or default from config
    api_key_var = api_key_var or provider_config["variable_name"]

    metadata = {
        "api_key_param": provider_config["api_key_param"],
        "context_length": 128000,
        "model_class": provider_config["model_class"],
        "model_name_param": provider_config["model_name_param"],
    }

    # Add extra params from provider config (url_param, project_id_param, base_url_param)
    for extra_param in ("url_param", "project_id_param", "base_url_param"):
        if extra_param in provider_config:
            metadata[extra_param] = provider_config[extra_param]

    model_value = [{
        "category": provider,
        "icon": provider_config["icon"],
        "metadata": metadata,
        "name": model_name,
        "provider": provider,
    }]

    # Inject into all Agent nodes
    for node in flow_data.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        if node_data.get("type") == "Agent":
            template = node_data.get("node", {}).get("template", {})
            if "model" in template:
                template["model"]["value"] = model_value
            # Note: Do NOT set api_key here. The Agent component will automatically
            # look up the API key from the user's global variables using get_api_key_for_provider()
            # when the api_key field is empty/falsy.

    return flow_data


async def execute_flow_file(
    flow_filename: str,
    input_value: str | None = None,
    global_variables: dict[str, str] | None = None,
    *,
    verbose: bool = False,
    user_id: str | None = None,
    session_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> dict:
    """Execute a flow from a JSON file.

    Args:
        flow_filename: Name of the flow file (e.g., "MyFlow.json")
        input_value: Input value to pass to the flow
        global_variables: Dict of global variables to inject into the flow context
        verbose: Whether to enable verbose logging
        user_id: User ID for components that require user context
        session_id: Unique session ID to isolate memory between requests
        provider: Model provider to inject into Agent nodes
        model_name: Model name to inject into Agent nodes
        api_key_var: API key variable name to inject into Agent nodes

    Returns:
        dict: Result from flow execution

    Raises:
        HTTPException: If flow file not found or execution fails
    """
    flow_path = FLOWS_BASE_PATH / flow_filename

    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow file '{flow_filename}' not found")

    try:
        flow_data = json.loads(flow_path.read_text())

        if provider and model_name:
            flow_data = inject_model_into_flow(flow_data, provider, model_name, api_key_var)

        flow_json = json.dumps(flow_data)
        result = await run_flow(
            flow_json=flow_json,
            input_value=input_value,
            global_variables=global_variables or {},
            verbose=verbose,
            check_variables=False,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception as e:
        logger.error(f"Flow execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing flow: {e}") from e

    return result


def _load_and_prepare_flow(
    flow_path: Path,
    provider: str | None,
    model_name: str | None,
    api_key_var: str | None,
) -> str:
    """Load flow file and prepare JSON with model injection."""
    flow_data = json.loads(flow_path.read_text())

    if provider and model_name:
        flow_data = inject_model_into_flow(flow_data, provider, model_name, api_key_var)

    return json.dumps(flow_data)


def _parse_event_data(event_data: bytes) -> tuple[str | None, dict[str, Any]]:
    """Parse raw event bytes into event type and data."""
    event_str = event_data.decode("utf-8").strip()
    if not event_str:
        return None, {}

    event_json = json.loads(event_str)
    return event_json.get("event"), event_json.get("data", {})


async def _create_flow_runner(
    flow_json: str,
    input_value: str | None,
    global_variables: dict[str, str] | None,
    verbose: bool,
    user_id: str | None,
    session_id: str | None,
    event_manager: EventManager,
    event_queue: asyncio.Queue,
    execution_result: FlowExecutionResult,
) -> None:
    """Execute flow and store result, signaling completion via queue."""
    try:
        result = await run_flow(
            flow_json=flow_json,
            input_value=input_value,
            global_variables=global_variables or {},
            verbose=verbose,
            check_variables=False,
            user_id=user_id,
            session_id=session_id,
            event_manager=event_manager,
        )
        execution_result.result = result
    except Exception as e:
        execution_result.error = e
        logger.error(f"Flow execution error: {e}")
    finally:
        await event_queue.put(None)


async def execute_flow_file_streaming(
    flow_filename: str,
    input_value: str | None = None,
    global_variables: dict[str, str] | None = None,
    *,
    verbose: bool = False,
    user_id: str | None = None,
    session_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> AsyncGenerator[tuple[str, Any], None]:
    """Execute a flow from a JSON file with token streaming.

    Yields events as they occur:
    - ("token", chunk): Token chunk from LLM streaming
    - ("end", result): Final result when flow completes

    Args:
        flow_filename: Name of the flow file (e.g., "MyFlow.json")
        input_value: Input value to pass to the flow
        global_variables: Dict of global variables to inject into the flow context
        verbose: Whether to enable verbose logging
        user_id: User ID for components that require user context
        session_id: Unique session ID to isolate memory between requests
        provider: Model provider to inject into Agent nodes
        model_name: Model name to inject into Agent nodes
        api_key_var: API key variable name to inject into Agent nodes

    Yields:
        tuple[str, Any]: Event type and data pairs

    Raises:
        HTTPException: If flow file not found or execution fails
    """
    flow_path = FLOWS_BASE_PATH / flow_filename

    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow file '{flow_filename}' not found")

    try:
        flow_json = _load_and_prepare_flow(flow_path, provider, model_name, api_key_var)
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.error(f"Flow preparation error: {e}")
        raise HTTPException(status_code=500, detail=f"Error preparing flow: {e}") from e

    event_queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue(
        maxsize=STREAMING_QUEUE_MAX_SIZE
    )
    event_manager = create_default_event_manager(event_queue)
    execution_result = FlowExecutionResult()

    flow_task = asyncio.create_task(
        _create_flow_runner(
            flow_json=flow_json,
            input_value=input_value,
            global_variables=global_variables,
            verbose=verbose,
            user_id=user_id,
            session_id=session_id,
            event_manager=event_manager,
            event_queue=event_queue,
            execution_result=execution_result,
        )
    )

    try:
        async for event_type, chunk in _consume_streaming_events(event_queue):
            if event_type == "token":
                yield ("token", chunk)
            elif event_type == "end":
                break
    finally:
        if not flow_task.done():
            await flow_task

    if execution_result.has_error:
        raise HTTPException(
            status_code=500,
            detail=f"Error executing flow: {execution_result.error}"
        ) from execution_result.error

    yield ("end", execution_result.result if execution_result.has_result else {})


async def _consume_streaming_events(
    event_queue: asyncio.Queue[tuple[str, bytes, float] | None],
) -> AsyncGenerator[tuple[str, str], None]:
    """Consume events from queue and yield parsed token events."""
    while True:
        try:
            event = await asyncio.wait_for(
                event_queue.get(),
                timeout=STREAMING_EVENT_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.warning("Event queue timeout - flow may be stuck")
            break

        if event is None:
            break

        _event_id, event_data, _timestamp = event

        try:
            event_type, data = _parse_event_data(event_data)
            if event_type == "token":
                chunk = data.get("chunk", "")
                if chunk:
                    yield ("token", chunk)
            elif event_type == "end":
                yield ("end", "")
                break
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.debug(f"Failed to parse event: {e}")
            continue


def extract_response_text(result: dict) -> str:
    """Extract text from flow execution result."""
    if "result" in result:
        return result["result"]
    if "text" in result:
        return result["text"]
    if "exception_message" in result:
        return result["exception_message"]

    return str(result)
