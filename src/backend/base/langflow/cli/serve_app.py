from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from langflow.cli.common import execute_graph_with_capture, extract_result_data
from langflow.events.event_manager import create_stream_tokens_event_manager

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from langflow.graph import Graph

"""FastAPI application factory for serving **multiple** Langflow graphs at once.

This module is used by the CLI *serve* command when the provided path is a
folder containing multiple ``*.json`` flow files.  Each flow is exposed under
its own router prefix::

    /flows/{flow_id}/run  - POST - execute the flow
    /flows/{flow_id}/info - GET  - metadata

A global ``/flows`` endpoint lists all available flows and returns a JSON array
of metadata objects, allowing API consumers to discover IDs without guessing.

Authentication behaves exactly like the single-flow serving: all execution
endpoints require the ``x-api-key`` header (or query parameter) validated by
:func:`langflow.cli.commands.verify_api_key`.
"""


def _analyze_graph_structure(graph: Graph) -> dict[str, Any]:
    """Analyze the graph structure to extract dynamic documentation information.

    Args:
        graph: The Langflow graph to analyze

    Returns:
        dict: Graph analysis including components, input/output types, and flow details
    """
    analysis: dict[str, Any] = {
        "components": [],
        "input_types": set(),
        "output_types": set(),
        "node_count": 0,
        "edge_count": 0,
        "entry_points": [],
        "exit_points": [],
    }

    try:
        # Analyze nodes
        for node_id, node in graph.nodes.items():
            analysis["node_count"] += 1
            component_info = {
                "id": node_id,
                "type": node.data.get("type", "Unknown"),
                "name": node.data.get("display_name", node.data.get("type", "Unknown")),
                "description": node.data.get("description", ""),
                "template": node.data.get("template", {}),
            }
            analysis["components"].append(component_info)

            # Identify entry points (nodes with no incoming edges)
            if not any(edge.source == node_id for edge in graph.edges):
                analysis["entry_points"].append(component_info)

            # Identify exit points (nodes with no outgoing edges)
            if not any(edge.target == node_id for edge in graph.edges):
                analysis["exit_points"].append(component_info)

        # Analyze edges
        analysis["edge_count"] = len(graph.edges)

        # Try to determine input/output types from entry/exit points
        for entry in analysis["entry_points"]:
            template = entry.get("template", {})
            for field_config in template.values():
                if field_config.get("type") in ["str", "text", "string"]:
                    analysis["input_types"].add("text")
                elif field_config.get("type") in ["int", "float", "number"]:
                    analysis["input_types"].add("numeric")
                elif field_config.get("type") in ["file", "path"]:
                    analysis["input_types"].add("file")

        for exit_point in analysis["exit_points"]:
            template = exit_point.get("template", {})
            for field_config in template.values():
                if field_config.get("type") in ["str", "text", "string"]:
                    analysis["output_types"].add("text")
                elif field_config.get("type") in ["int", "float", "number"]:
                    analysis["output_types"].add("numeric")
                elif field_config.get("type") in ["file", "path"]:
                    analysis["output_types"].add("file")

    except (KeyError, AttributeError):
        # If analysis fails, provide basic info
        analysis["components"] = [{"type": "Unknown", "name": "Graph Component"}]
        analysis["input_types"] = {"text"}
        analysis["output_types"] = {"text"}

    # Convert sets to lists for JSON serialization
    analysis["input_types"] = list(analysis["input_types"])
    analysis["output_types"] = list(analysis["output_types"])

    return analysis


def _generate_dynamic_run_description(graph: Graph) -> str:
    """Generate dynamic description for the /run endpoint based on graph analysis.

    Args:
        graph: The Langflow graph

    Returns:
        str: Dynamic description for the /run endpoint
    """
    analysis = _analyze_graph_structure(graph)

    # Determine input examples based on entry points
    input_examples = []
    for entry in analysis["entry_points"]:
        template = entry.get("template", {})
        for field_name, field_config in template.items():
            if field_config.get("type") in ["str", "text", "string"]:
                input_examples.append(f'"{field_name}": "Your input text here"')
            elif field_config.get("type") in ["int", "float", "number"]:
                input_examples.append(f'"{field_name}": 42')
            elif field_config.get("type") in ["file", "path"]:
                input_examples.append(f'"{field_name}": "/path/to/file.txt"')

    if not input_examples:
        input_examples = ['"input_value": "Your input text here"']

    # Determine output examples based on exit points
    output_examples = []
    for exit_point in analysis["exit_points"]:
        template = exit_point.get("template", {})
        for field_name, field_config in template.items():
            if field_config.get("type") in ["str", "text", "string"]:
                output_examples.append(f'"{field_name}": "Processed result"')
            elif field_config.get("type") in ["int", "float", "number"]:
                output_examples.append(f'"{field_name}": 123')
            elif field_config.get("type") in ["file", "path"]:
                output_examples.append(f'"{field_name}": "/path/to/output.txt"')

    if not output_examples:
        output_examples = ['"result": "Processed result"']

    description_parts = [
        f"Execute the deployed Langflow graph with {analysis['node_count']} components.",
        "",
        "**Graph Analysis**:",
        f"- Entry points: {len(analysis['entry_points'])}",
        f"- Exit points: {len(analysis['exit_points'])}",
        f"- Input types: {', '.join(analysis['input_types']) if analysis['input_types'] else 'text'}",
        f"- Output types: {', '.join(analysis['output_types']) if analysis['output_types'] else 'text'}",
        "",
        "**Authentication Required**: Include your API key in the `x-api-key` header or as a query parameter.",
        "",
        "**Example Request**:",
        "```json",
        "{",
        f"  {', '.join(input_examples)}",
        "}",
        "```",
        "",
        "**Example Response**:",
        "```json",
        "{",
        f"  {', '.join(output_examples)},",
        '  "success": true,',
        '  "logs": "Graph execution completed successfully",',
        '  "type": "message",',
        '  "component": "FinalComponent"',
        "}",
        "```",
    ]

    return "\n".join(description_parts)


class FlowMeta(BaseModel):
    """Metadata returned by the ``/flows`` endpoint."""

    id: str = Field(..., description="Deterministic flow identifier (UUIDv5)")
    relative_path: str = Field(..., description="Path of the flow JSON relative to the deployed folder")
    title: str = Field(..., description="Human-readable title (filename stem if unknown)")
    description: str | None = Field(None, description="Optional flow description")


class RunRequest(BaseModel):
    """Request model for executing a Langflow flow."""

    input_value: str = Field(..., description="Input value passed to the flow")


class StreamRequest(BaseModel):
    """Request model for streaming execution of a Langflow flow."""

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
        # to integrate with the full Langflow streaming pipeline from endpoints.py
        results, logs = execute_graph_with_capture(graph, input_request.input_value)
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
    root_dir: Path,  # noqa: ARG001
    graphs: dict[str, Graph],
    metas: dict[str, FlowMeta],
    verbose_print: Callable[[str], None],  # noqa: ARG001
) -> FastAPI:
    """Create a FastAPI app exposing multiple Langflow flows.

    Parameters
    ----------
    root_dir
        Folder originally supplied to the serve command.  All *relative_path*
        values are relative to this directory.
    graphs
        Mapping ``flow_id -> Graph`` containing prepared graph objects.
    metas
        Mapping ``flow_id -> FlowMeta`` containing metadata for each flow.
    verbose_print
        Diagnostic printer inherited from the CLI (unused, kept for backward compatibility).
    """
    # Import here to avoid circular import
    from langflow.cli.commands import verify_api_key

    if set(graphs) != set(metas):  # pragma: no cover - sanity check
        msg = "graphs and metas must contain the same keys"
        raise ValueError(msg)

    app = FastAPI(
        title=f"Langflow Multi-Flow Server ({len(graphs)})",
        description=(
            "This server hosts multiple Langflow graphs under the `/flows/{id}` prefix. "
            "Use `/flows` to list available IDs then POST your input to `/flows/{id}/run`."
        ),
        version="1.0.0",
    )

    # ------------------------------------------------------------------
    # Global endpoints
    # ------------------------------------------------------------------

    @app.get("/flows", response_model=list[FlowMeta], tags=["info"], summary="List available flows")
    async def list_flows():
        """Return metadata for all flows hosted in this server."""
        return list(metas.values())

    @app.get("/health", tags=["info"], summary="Global health check")
    async def global_health():
        return {"status": "healthy", "flow_count": len(graphs)}

    # ------------------------------------------------------------------
    # Per-flow routers
    # ------------------------------------------------------------------

    def create_flow_router(flow_id: str, graph: Graph, meta: FlowMeta) -> APIRouter:
        """Create a router for a specific flow to avoid loop variable binding issues."""
        analysis = _analyze_graph_structure(graph)
        run_description = _generate_dynamic_run_description(graph)

        router = APIRouter(
            prefix=f"/flows/{flow_id}",
            tags=[meta.title or flow_id],
            dependencies=[Depends(verify_api_key)],  # Auth for all routes inside
        )

        @router.post(
            "/run",
            response_model=RunResponse,
            responses={500: {"model": ErrorResponse}},
            summary="Execute flow",
            description=run_description,
        )
        async def run_flow(
            request: RunRequest,
        ) -> RunResponse:
            try:
                results, logs = execute_graph_with_capture(graph, request.input_value)
                result_data = extract_result_data(results, logs)

                # Debug logging
                logger.debug(f"Flow {flow_id} execution completed: {len(results)} results, {len(logs)} log chars")
                logger.debug(f"Flow {flow_id} result data: {result_data}")

                # Check if the execution was successful
                if not result_data.get("success", True):
                    # If the flow execution failed, return error details in the response
                    error_message = result_data.get("result", result_data.get("text", "No response generated"))

                    # Add more context to the logs when there's an error
                    error_logs = logs
                    if not error_logs.strip():
                        error_logs = (
                            f"Flow execution completed but no valid result was produced.\nResult data: {result_data}"
                        )

                    return RunResponse(
                        result=error_message,
                        success=False,
                        logs=error_logs,
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

                # Capture the full traceback for debugging
                error_traceback = traceback.format_exc()
                error_message = f"Flow execution failed: {exc!s}"

                # Log to server console for debugging
                logger.error(f"Error running flow {flow_id}: {exc}")
                logger.debug(f"Full traceback for flow {flow_id}:\n{error_traceback}")

                # Return error details in the API response instead of raising HTTPException
                return RunResponse(
                    result=error_message,
                    success=False,
                    logs=f"ERROR: {error_message}\n\nFull traceback:\n{error_traceback}",
                    type="error",
                    component="",
                )

        @router.post(
            "/stream",
            response_model=None,
            summary="Stream flow execution",
            description=f"Stream the execution of {meta.title or flow_id} with real-time events and token streaming.",
        )
        async def stream_flow(
            request: StreamRequest,
        ) -> StreamingResponse:
            """Stream the execution of the flow with real-time events."""
            try:
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
                # Return a simple error stream
                error_message = f"Failed to start streaming: {exc!s}"

                async def error_stream():
                    yield f'data: {{"error": "{error_message}", "success": false}}\n\n'

                return StreamingResponse(
                    error_stream(),
                    media_type="text/event-stream",
                )

        @router.get("/info", summary="Flow metadata", response_model=FlowMeta)
        async def flow_info():
            """Return metadata and basic analysis for this flow."""
            # Enrich meta with analysis data for convenience
            return {
                **meta.dict(),
                "components": analysis["node_count"],
                "connections": analysis["edge_count"],
                "input_types": analysis["input_types"],
                "output_types": analysis["output_types"],
            }

        return router

    for flow_id, graph in graphs.items():
        meta = metas[flow_id]
        router = create_flow_router(flow_id, graph, meta)
        app.include_router(router)

    return app
