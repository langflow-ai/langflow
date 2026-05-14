"""FastAPI application factory for serving **multiple** LFX graphs at once.

This module is used by the CLI *serve* command when the provided path is a
folder containing multiple ``*.json`` flow files.  Each flow is exposed under
its own router prefix::

    /flows/{flow_id}/run  - POST - execute the flow
    /flows/{flow_id}/info - GET  - metadata

A global ``/flows`` endpoint lists all available flows and returns a JSON array
of metadata objects, allowing API consumers to discover IDs without guessing.

Authentication behaves exactly like the single-flow serving: all execution
endpoints require the ``x-api-key`` header (or query parameter) validated by
:func:`lfx.cli.commands.verify_api_key`.
"""

from __future__ import annotations

import asyncio
import time
from copy import deepcopy
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import BaseModel, Field

from lfx.cli.common import (
    execute_graph_with_capture,
    extract_result_data,
    flow_id_from_content,
    get_api_key,
)
from lfx.load import load_flow_from_json
from lfx.log.logger import logger
from lfx.utils.flow_validation import validate_flow_for_current_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from lfx.graph import Graph

# Security - use the same pattern as Langflow main API
API_KEY_NAME = "x-api-key"
api_key_query = APIKeyQuery(name=API_KEY_NAME, scheme_name="API key query", auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, scheme_name="API key header", auto_error=False)


def verify_api_key(
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
) -> str:
    """Verify API key from query parameter or header."""
    provided_key = query_param or header_param
    if not provided_key:
        raise HTTPException(status_code=401, detail="API key required")

    try:
        expected_key = get_api_key()
        if provided_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return provided_key


class FlowMeta(BaseModel):
    """Metadata returned by the ``/flows`` endpoint."""

    id: str = Field(..., description="Deterministic flow identifier (UUIDv5)")
    relative_path: str = Field(..., description="Path of the flow JSON relative to the deployed folder")
    title: str = Field(..., description="Human-readable title (filename stem if unknown)")
    description: str | None = Field(None, description="Optional flow description")


class RunRequest(BaseModel):
    """Request model for executing a LFX flow."""

    input_value: str = Field(..., description="Input value passed to the flow")
    session_id: str | None = Field(default=None, description="Session ID for maintaining conversation state")


class StreamRequest(BaseModel):
    """Request model for streaming execution of a LFX flow."""

    input_value: str = Field(..., description="Input value passed to the flow")
    input_type: str = Field(default="chat", description="Type of input (chat, text)")
    output_type: str = Field(default="chat", description="Type of output (chat, text, debug, any)")
    output_component: str | None = Field(default=None, description="Specific output component to stream from")
    session_id: str | None = Field(default=None, description="Session ID for maintaining conversation state")
    tweaks: dict[str, Any] | None = Field(default=None, description="Optional tweaks to modify flow behavior")


class RunResponse(BaseModel):
    """Response model mirroring the single-flow server."""

    result: str = Field(..., description="The output result from the flow execution")
    success: bool = Field(..., description="Whether execution was successful")
    logs: str = Field("", description="Captured logs from execution")
    type: str = Field("message", description="Type of result")
    component: str = Field("", description="Component that generated the result")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    success: bool = Field(default=False, description="Always false for errors")


class FlowRegistry:
    """Mutable in-process registry of loaded flows."""

    def __init__(self) -> None:
        self._flows: dict[str, tuple[Graph, FlowMeta]] = {}

    def add(self, graph: Graph, meta: FlowMeta) -> None:
        self._flows[meta.id] = (graph, meta)

    def get(self, flow_id: str) -> tuple[Graph, FlowMeta] | None:
        return self._flows.get(flow_id)

    def list_metas(self) -> list[FlowMeta]:
        return [meta for _, meta in self._flows.values()]

    def remove(self, flow_id: str) -> bool:
        if flow_id in self._flows:
            del self._flows[flow_id]
            return True
        return False

    def __len__(self) -> int:
        return len(self._flows)


class UploadFlowRequest(BaseModel):
    name: str = Field(..., description="Human-readable name for the flow (matches FlowBase.name)")
    data: dict = Field(..., description="Raw flow JSON — nodes and edges (matches FlowBase.data)")
    description: str | None = Field(default=None, description="Optional flow description")


class UploadFlowResponse(BaseModel):
    id: str = Field(..., description="Deterministic UUID5 of flow content")
    name: str
    description: str | None
    run_url: str = Field(..., description="Endpoint to POST run requests, e.g. /flows/{id}/run")


# -----------------------------------------------------------------------------
# Streaming helper functions
# -----------------------------------------------------------------------------


async def consume_and_yield(queue: asyncio.Queue, client_consumed_queue: asyncio.Queue) -> AsyncGenerator:
    """Consumes events from a queue and yields them to the client while tracking timing metrics.

    This coroutine continuously pulls events from the input queue and yields them to the client.
    It tracks timing metrics for how long events spend in the queue and how long the client takes
    to process them.

    Args:
        queue (asyncio.Queue): The queue containing events to be consumed and yielded
        client_consumed_queue (asyncio.Queue): A queue for tracking when the client has consumed events

    Yields:
        The value from each event in the queue

    Notes:
        - Events are tuples of (event_id, value, put_time)
        - Breaks the loop when receiving a None value, signaling completion
        - Tracks and logs timing metrics for queue time and client processing time
        - Notifies client consumption via client_consumed_queue
    """
    while True:
        event_id, value, put_time = await queue.get()
        if value is None:
            break
        get_time = time.time()
        yield value
        get_time_yield = time.time()
        client_consumed_queue.put_nowait(event_id)
        logger.debug(
            f"consumed event {event_id} "
            f"(time in queue, {get_time - put_time:.4f}, "
            f"client {get_time_yield - get_time:.4f})"
        )


async def run_flow_generator_for_serve(
    graph: Graph,
    input_request: StreamRequest,
    flow_id: str,
    event_manager,
    client_consumed_queue: asyncio.Queue,
) -> None:
    """Executes a flow asynchronously and manages event streaming to the client.

    This coroutine runs a flow with streaming enabled and handles the event lifecycle,
    including success completion and error scenarios.

    Args:
        graph (Graph): The graph to execute
        input_request (StreamRequest): The input parameters for the flow
        flow_id (str): The ID of the flow being executed
        event_manager: Manages the streaming of events to the client
        client_consumed_queue (asyncio.Queue): Tracks client consumption of events

    Events Generated:
        - "add_message": Sent when new messages are added during flow execution
        - "token": Sent for each token generated during streaming
        - "end": Sent when flow execution completes, includes final result
        - "error": Sent if an error occurs during execution

    Notes:
        - Runs the flow with streaming enabled via execute_graph_with_capture()
        - On success, sends the final result via event_manager.on_end()
        - On error, logs the error and sends it via event_manager.on_error()
        - Always sends a final None event to signal completion
    """
    try:
        # For the serve app, we'll use execute_graph_with_capture with streaming
        # Note: This is a simplified version. In a full implementation, you might want
        # to integrate with the full LFX streaming pipeline from endpoints.py
        results, logs = await execute_graph_with_capture(
            graph, input_request.input_value, session_id=input_request.session_id
        )
        result_data = extract_result_data(results, logs)

        # Send the final result
        event_manager.on_end(data={"result": result_data})
        await client_consumed_queue.get()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error running flow {flow_id}: {e}")
        event_manager.on_error(data={"error": str(e)})
    finally:
        await event_manager.queue.put((None, None, time.time()))


# -----------------------------------------------------------------------------
# Application factory
# -----------------------------------------------------------------------------


def create_multi_serve_app(
    *,
    registry: FlowRegistry,
    verbose_print: Callable[[str], None],  # noqa: ARG001
) -> FastAPI:
    """Create a FastAPI app exposing LFX flows via a mutable registry.

    Routes dispatch to ``registry`` at request time, so flows added after
    startup (via ``POST /flows/upload/``) are immediately reachable.
    """
    app = FastAPI(
        title=f"LFX Multi-Flow Server ({len(registry)})",
        description=(
            "Hosts LFX graphs under the `/flows/{{id}}` prefix. "
            "Use `/flows` to list available IDs then POST your input to `/flows/{{id}}/run`. "
            "Use `POST /flows/upload/` to register new flows at runtime."
        ),
        version="1.0.0",
    )
    app.state.registry = registry

    # ------------------------------------------------------------------
    # Global endpoints
    # ------------------------------------------------------------------

    @app.get(
        "/flows",
        response_model=list[FlowMeta],
        tags=["info"],
        summary="List available flows",
    )
    async def list_flows():
        return registry.list_metas()

    @app.get("/health", tags=["info"], summary="Global health check")
    async def global_health():
        return {"status": "healthy", "flow_count": len(registry)}

    # ------------------------------------------------------------------
    # Upload endpoint — registered BEFORE /{flow_id} to avoid shadowing
    # ------------------------------------------------------------------

    @app.post(
        "/flows/upload/",
        response_model=UploadFlowResponse,
        status_code=201,
        tags=["upload"],
        summary="Upload and register a new flow",
        dependencies=[Depends(verify_api_key)],
    )
    async def upload_flow(body: UploadFlowRequest) -> UploadFlowResponse:
        try:
            graph = load_flow_from_json(body.data)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid flow data: {exc}") from exc

        try:
            graph.prepare()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Flow preparation failed: {exc}") from exc

        flow_id = flow_id_from_content(body.data)
        meta = FlowMeta(
            id=flow_id,
            relative_path="<uploaded>",
            title=body.name,
            description=body.description,
        )
        registry.add(graph, meta)
        return UploadFlowResponse(
            id=flow_id,
            name=body.name,
            description=body.description,
            run_url=f"/flows/{flow_id}/run",
        )

    # ------------------------------------------------------------------
    # Per-flow dispatch routes
    # ------------------------------------------------------------------

    def _get_flow_or_404(flow_id: str) -> tuple[Graph, FlowMeta]:
        result = registry.get(flow_id)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "flow not found", "flow_id": flow_id},
            )
        return result

    @app.get(
        "/flows/{flow_id}/info",
        response_model=FlowMeta,
        tags=["flows"],
        summary="Flow metadata",
        dependencies=[Depends(verify_api_key)],
    )
    async def flow_info(flow_id: str) -> FlowMeta:
        _, meta = _get_flow_or_404(flow_id)
        return meta

    @app.post(
        "/flows/{flow_id}/run",
        response_model=RunResponse,
        responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
        tags=["flows"],
        summary="Execute flow",
        dependencies=[Depends(verify_api_key)],
    )
    async def run_flow(flow_id: str, request: RunRequest) -> RunResponse:
        graph, _ = _get_flow_or_404(flow_id)
        try:
            validate_flow_for_current_settings(graph)
            graph_copy = deepcopy(graph)
            results, logs = await execute_graph_with_capture(
                graph_copy, request.input_value, session_id=request.session_id
            )
            result_data = extract_result_data(results, logs)

            if not result_data.get("success", True):
                error_message = result_data.get("result", result_data.get("text", "No response generated"))
                return RunResponse(
                    result=error_message,
                    success=False,
                    logs=logs
                    or (f"Flow execution completed but no valid result was produced.\nResult data: {result_data}"),
                    type="error",
                    component=result_data.get("component", ""),
                )
            return RunResponse(
                result=result_data.get("result", result_data.get("text", "")),
                success=result_data.get("success", True),
                logs=logs,
                type=result_data.get("type", "message"),
                component=result_data.get("component", ""),
            )
        except Exception as exc:  # noqa: BLE001
            import traceback

            error_traceback = traceback.format_exc()
            error_message = f"Flow execution failed: {exc!s}"
            logger.error(f"Error running flow {flow_id}: {exc}")
            logger.debug(f"Full traceback for flow {flow_id}:\n{error_traceback}")
            return RunResponse(
                result=error_message,
                success=False,
                logs=f"ERROR: {error_message}\n\nFull traceback:\n{error_traceback}",
                type="error",
                component="",
            )

    @app.post(
        "/flows/{flow_id}/stream",
        response_model=None,
        tags=["flows"],
        summary="Stream flow execution",
        dependencies=[Depends(verify_api_key)],
    )
    async def stream_flow(flow_id: str, request: StreamRequest) -> StreamingResponse:
        graph, _ = _get_flow_or_404(flow_id)
        try:
            validate_flow_for_current_settings(graph)
            from lfx.events.event_manager import create_stream_tokens_event_manager

            asyncio_queue: asyncio.Queue = asyncio.Queue()
            asyncio_queue_client_consumed: asyncio.Queue = asyncio.Queue()
            event_manager = create_stream_tokens_event_manager(queue=asyncio_queue)

            main_task = asyncio.create_task(
                run_flow_generator_for_serve(
                    graph=graph,
                    input_request=request,
                    flow_id=flow_id,
                    event_manager=event_manager,
                    client_consumed_queue=asyncio_queue_client_consumed,
                )
            )

            async def on_disconnect() -> None:
                logger.debug(f"Client disconnected from flow {flow_id}, closing tasks")
                main_task.cancel()

            return StreamingResponse(
                consume_and_yield(asyncio_queue, asyncio_queue_client_consumed),
                background=on_disconnect,
                media_type="text/event-stream",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error setting up streaming for flow {flow_id}: {exc}")
            error_message = f"Failed to start streaming: {exc!s}"

            async def error_stream():
                yield f'data: {{"error": "{error_message}", "success": false}}\n\n'

            return StreamingResponse(error_stream(), media_type="text/event-stream")

    return app
