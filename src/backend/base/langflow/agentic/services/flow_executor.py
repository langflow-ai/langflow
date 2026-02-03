"""Flow execution service."""

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from lfx.events.event_manager import EventManager, create_default_event_manager
from lfx.log.logger import logger
from lfx.run.base import run_flow

from langflow.agentic.services.flow_preparation import load_and_prepare_flow

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
        flow_json = load_and_prepare_flow(flow_path, provider, model_name, api_key_var)
        result = await run_flow(
            flow_json=flow_json,
            input_value=input_value,
            global_variables=global_variables or {},
            verbose=verbose,
            check_variables=False,
            user_id=user_id,
            session_id=session_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Flow execution error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while executing the flow.") from e

    return result


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
    user_id: str | None,
    session_id: str | None,
    event_manager: EventManager,
    event_queue: asyncio.Queue,
    execution_result: FlowExecutionResult,
    *,
    verbose: bool = False,
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
    except Exception as e:  # noqa: BLE001
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
        flow_json = load_and_prepare_flow(flow_path, provider, model_name, api_key_var)
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.error(f"Flow preparation error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while preparing the flow.") from e

    event_queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue(maxsize=STREAMING_QUEUE_MAX_SIZE)
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
            status_code=500, detail="An error occurred while executing the flow."
        ) from execution_result.error

    yield ("end", execution_result.result if execution_result.has_result else {})


async def _consume_streaming_events(
    event_queue: asyncio.Queue[tuple[str, bytes, float] | None],
) -> AsyncGenerator[tuple[str, str], None]:
    """Consume events from queue and yield parsed token events."""
    while True:
        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=STREAMING_EVENT_TIMEOUT_SECONDS)
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
