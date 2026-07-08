"""V2 workflow-shaped endpoints for ``lfx serve``.

Gives the standalone lfx runtime the same request/response contract as the
langflow backend ``POST /api/v2/workflows`` for the ``sync`` and ``stream``
execution modes, so a client integrates against one contract regardless of which
runtime serves it.

Background and public modes stay backend-only: they need a database, job queue,
and auth model that stateless ``lfx serve`` does not have.

Built on the shared contract layer in ``lfx.workflow`` (adapters + converters)
and the native ``lfx`` ``Graph.async_start`` event stream.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from lfx.cli.common import execute_graph_with_capture
from lfx.cli.runtime_variables import apply_global_vars_to_graph, build_request_variables_from_global_vars
from lfx.events.event_manager import create_stream_tokens_event_manager
from lfx.processing.process import run_graph_internal
from lfx.run._defaults import apply_run_defaults
from lfx.schema.schema import InputValueRequest

# WorkflowRunRequest stays a runtime import: FastAPI resolves the route's body
# annotation at request-model build time, so it cannot live under TYPE_CHECKING.
from lfx.schema.workflow import WorkflowRunRequest  # noqa: TC001
from lfx.services.variable.request_scope import activate_request_variables, reset_request_variables
from lfx.utils.flow_validation import validate_flow_for_current_settings
from lfx.workflow.adapters import (
    STREAM_ADAPTERS,
    StreamAdapterContext,
    available_protocols,
    get_stream_adapter,
)
from lfx.workflow.converters import (
    create_error_response,
    parse_workflow_run_request,
    run_response_to_workflow_response,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI

    from lfx.graph.graph.base import Graph
    from lfx.schema.workflow import WorkflowExecutionResponse
    from lfx.workflow.adapters import StreamAdapter
    from lfx.workflow.converters import ParsedWorkflowRun


# Bounded queue between the graph run and the SSE consumer, mirroring the backend
# stream loop: on overflow (a slow client) the run fails with an explicit stream
# error rather than silently dropping frames.
_STREAM_QUEUE_MAX_SIZE = 256

_QueueItem = tuple[str | None, bytes | None, float]


class _WorkflowEventQueue:
    """Bounded EventManager handoff that fails explicitly instead of dropping events.

    ``EventManager`` dispatches with ``put_nowait``, so a plain bounded
    ``asyncio.Queue`` would silently drop frames via ``QueueFull`` when the SSE
    client falls behind. Ported from the langflow backend v2 stream wrapper: the
    first overflow flips the queue closed and enqueues a single ``error`` event
    followed by the terminal sentinel, so the consumer surfaces the failure and
    ends the stream cleanly.
    """

    def __init__(self, maxsize: int) -> None:
        self._queue: asyncio.Queue[_QueueItem] = asyncio.Queue(maxsize=maxsize)
        self._overflowed = False
        self._loop = asyncio.get_running_loop()
        self._overflow_task: asyncio.Task[None] | None = None

    @property
    def maxsize(self) -> int:
        return self._queue.maxsize

    async def get(self) -> _QueueItem:
        return await self._queue.get()

    async def put(self, item: _QueueItem) -> None:
        if self._overflowed:
            return
        await self._queue.put(item)

    def put_nowait(self, item: _QueueItem) -> None:
        if self._overflowed:
            return
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            self._overflowed = True
            self._overflow_task = self._loop.create_task(self._emit_overflow_error())

    async def _emit_overflow_error(self) -> None:
        payload = {
            "event": "error",
            "data": {
                "error": "Workflow event stream exceeded buffering capacity; client is consuming events too slowly."
            },
        }
        await self._queue.put((f"error-{uuid4()}", json.dumps(payload).encode("utf-8"), time.time()))
        await self._queue.put((None, None, time.time()))

    async def aclose(self) -> None:
        if self._overflow_task is not None and not self._overflow_task.done():
            self._overflow_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._overflow_task


def _validate_output_ids(output_ids: list[str] | None, terminal_node_ids: list[str]) -> None:
    """Reject ``output_ids`` the flow does not produce, before running.

    Mirrors the langflow backend v2 sync path: an unknown id is a 422 up front
    rather than wasted compute followed by a completed response with no selected
    output. Validated against the flow's terminal (sink) nodes, the same set the
    converter resolves selections against.
    """
    if not output_ids:
        return
    known = set(terminal_node_ids)
    unknown = [output_id for output_id in output_ids if output_id not in known]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Unknown output_ids",
                "code": "UNKNOWN_OUTPUT_IDS",
                "message": f"output_ids not produced by this flow: {unknown}.",
                "available": terminal_node_ids,
            },
        )


@dataclass
class _RunResponse:
    """Minimal ``RunResponseLike``: the two attributes the converter reads."""

    outputs: list[Any] | None
    session_id: str | None


def _reject_unsupported_fields(parsed: ParsedWorkflowRun) -> None:
    """Reject request fields lfx serve does not execute yet.

    lfx serve runs a pre-registered, prepared graph and has no per-request graph
    rebuild, so live ``data`` overrides, ``tweaks``, ``files``, and partial-run
    boundaries are not supported here yet (they remain available on the langflow
    backend). Request-level ``globals`` are supported and applied as
    request-scoped variables, so they are not rejected here. Reject the rest
    explicitly rather than silently ignore so a caller is never surprised.
    """
    unsupported: list[str] = []
    if parsed.tweaks:
        unsupported.append("tweaks")
    if parsed.data is not None:
        unsupported.append("data")
    if parsed.files:
        unsupported.append("files")
    if parsed.start_component_id is not None:
        unsupported.append("start_component_id")
    if parsed.stop_component_id is not None:
        unsupported.append("stop_component_id")
    if unsupported:
        fields = ", ".join(unsupported)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Unsupported request fields",
                "code": "LFX_SERVE_UNSUPPORTED_FIELDS",
                "message": f"lfx serve does not support these v2 fields yet: {fields}. Use the langflow "
                "backend for live-data overrides, tweaks, files, or partial-run boundaries.",
                "fields": unsupported,
            },
        )


def _build_inputs(parsed: ParsedWorkflowRun) -> list[InputValueRequest] | None:
    """Build the single chat input for the run, scoped to the session, if any."""
    if not parsed.input_value:
        return None
    return [InputValueRequest(components=[], input_value=parsed.input_value, type="chat", session=parsed.session_id)]


def _terminal_node_ids(graph: Graph) -> list[str]:
    """The flow's output (sink) vertices, computed the way the converter does."""
    return [vertex.id for vertex in graph.vertices if not graph.successor_map.get(vertex.id, [])]


async def run_workflow_sync(
    graph: Graph, parsed: ParsedWorkflowRun, flow_id: str, *, user_id: str | None = None
) -> WorkflowExecutionResponse:
    """Run a flow to completion and build a v2 ``WorkflowExecutionResponse``.

    Uses ``run_graph_internal`` (the same primitive the langflow backend sync
    path uses) so the result is the aggregated ``RunOutputs`` shape the shared
    converter expects. Unknown ``output_ids`` are rejected up front (422);
    component-level failures are returned in the body (HTTP 200) to match the v2
    two-tier contract.
    """
    job_id = str(uuid4())
    terminal_ids = _terminal_node_ids(graph)
    _validate_output_ids(parsed.output_ids, terminal_ids)

    # Pin the verified caller identity onto the graph (and Memory vertices) the same
    # way execute_graph_with_capture does for the stream path. run_graph_internal
    # does not touch user_id, so without this the sync path would drop it.
    apply_run_defaults(graph, session_id=parsed.session_id, user_id=user_id, overwrite_user_id=user_id is not None)

    # Activate request-scoped variables (the route applied request-level globals
    # to graph.context) so components resolving through VariableService.get_variable
    # see them, matching the streaming path where execute_graph_with_capture does
    # the same activation. run_graph_internal does not activate them itself.
    scope_vars = build_request_variables_from_global_vars(graph.context.get("request_variables"))
    scope_token = activate_request_variables(scope_vars or None)
    try:
        run_outputs, session_id = await run_graph_internal(
            graph,
            flow_id,
            stream=False,
            session_id=parsed.session_id,
            inputs=_build_inputs(parsed),
            outputs=terminal_ids,
        )
    except Exception as exc:  # noqa: BLE001
        return create_error_response(
            flow_id=flow_id,
            job_id=job_id,
            inputs=parsed.tweaks,
            error=exc,
            effective_globals=parsed.globals,
        )
    finally:
        reset_request_variables(scope_token)
    run_response = _RunResponse(outputs=run_outputs, session_id=session_id)
    return run_response_to_workflow_response(
        run_response=run_response,
        flow_id=flow_id,
        job_id=job_id,
        inputs=parsed.tweaks,
        graph=graph,
        effective_globals=parsed.globals,
        selected_ids=parsed.output_ids,
    )


def _format_sse(data_json: str, seq: int) -> bytes:
    """Frame one event as an SSE message with a monotonic id for ``Last-Event-ID``.

    lfx has no ``format_sse_event`` helper, so frame manually to the same wire
    shape the backend emits (``id:`` + ``data:`` lines).
    """
    return f"id: {seq}\ndata: {data_json}\n\n".encode()


async def stream_workflow_frames(
    graph: Graph, parsed: ParsedWorkflowRun, adapter: StreamAdapter, *, user_id: str | None = None
) -> AsyncIterator[bytes]:
    """Run a flow and stream its events through ``adapter`` as SSE frames.

    The graph runs via ``execute_graph_with_capture`` with a token-stream
    ``EventManager`` wired in, so component token/message/error events land on a
    queue while this consumer translates them through the adapter. A failure
    becomes the adapter's terminal-error event rather than an HTTP error.
    """
    queue = _WorkflowEventQueue(maxsize=_STREAM_QUEUE_MAX_SIZE)
    event_manager = create_stream_tokens_event_manager(queue=queue)
    drive_error: BaseException | None = None

    async def drive() -> None:
        nonlocal drive_error
        try:
            await execute_graph_with_capture(
                graph,
                parsed.input_value or None,
                session_id=parsed.session_id,
                user_id=user_id,
                event_manager=event_manager,
            )
            # lfx's async_start does not emit a terminal ``end`` event (the
            # langflow build loop does). Emit one so the adapter closes the run
            # cleanly: the agui adapter rides RUN_FINISHED on translating ``end``,
            # and the langflow adapter emits its final ``end`` frame.
            event_manager.on_end(data={})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            drive_error = exc
        finally:
            await queue.put((None, None, time.time()))

    seq = 0
    run_task = asyncio.create_task(drive())
    try:
        for event in adapter.initial_events():
            yield _format_sse(event.data_json, seq)
            seq += 1
        while True:
            _event_id, value, _put_time = await queue.get()
            if value is None:
                break
            payload = json.loads(value.decode("utf-8"))
            for event in adapter.translate(payload.get("event", ""), payload.get("data") or {}):
                yield _format_sse(event.data_json, seq)
                seq += 1
        for event in adapter.final_events():
            yield _format_sse(event.data_json, seq)
            seq += 1
        # Guaranteed terminal-error fallback: if the run raised before a
        # cooperative error reached the queue, emit the adapter's error event(s).
        if drive_error is not None:
            for event in adapter.error_events(drive_error):
                yield _format_sse(event.data_json, seq)
                seq += 1
    finally:
        if not run_task.done():
            run_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await run_task
        await queue.aclose()


def add_v2_workflow_routes(app: FastAPI, registry, *, api_key_dependency, identity_dependency) -> None:
    """Register ``POST /workflows`` (v2 sync + stream) on the serve app.

    Mirrors the langflow backend ``POST /api/v2/workflows`` contract: same
    ``WorkflowRunRequest`` body (``flow_id`` included) and
    ``WorkflowExecutionResponse`` / SSE responses, so a client integrates
    identically against lfx serve.

    ``identity_dependency`` is serve's ``resolve_identity`` (sub-depends on the
    api-key floor), so the route enforces the configured identity mode
    (jwt/header) exactly like ``/flows/{id}/run`` and threads the verified
    ``user_id`` into execution instead of accepting a bare api key.
    """

    @app.post(
        "/workflows",
        response_model=None,
        tags=["workflow"],
        summary="Execute Workflow (v2 sync or stream)",
        dependencies=[Depends(api_key_dependency)],
    )
    async def execute_workflow(
        request: WorkflowRunRequest,
        # Depends() in the default (not Annotated) so FastAPI reads the live closure-local
        # resolver; see the run_flow note. resolve_identity enforces jwt/header identity here.
        user_id: str | None = Depends(identity_dependency),  # noqa: FAST002
    ):
        result = registry.get(request.flow_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "flow not found", "code": "FLOW_NOT_FOUND", "flow_id": request.flow_id},
            )
        graph, _meta = result

        if request.stream_protocol not in STREAM_ADAPTERS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "Unknown stream_protocol",
                    "code": "UNKNOWN_STREAM_PROTOCOL",
                    "message": f"Unknown stream_protocol {request.stream_protocol!r}.",
                    "available": available_protocols(),
                },
            )

        parsed = parse_workflow_run_request(request)
        _reject_unsupported_fields(parsed)

        if parsed.mode == "background":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "Unsupported mode",
                    "code": "LFX_SERVE_UNSUPPORTED_MODE",
                    "message": "lfx serve supports mode 'sync' and 'stream'. Background runs need the "
                    "langflow backend (durable jobs + queue).",
                },
            )

        # Per-request isolation: never mutate the shared cached graph. Mirrors the
        # run/stream endpoints. deepcopy drops graph.context, so re-stamp the
        # registry's env policy.
        validate_flow_for_current_settings(graph)
        graph_copy = deepcopy(graph)
        registry.stamp(graph_copy)
        # Apply request-level globals as request-scoped variables on the copy, the
        # same way the run/stream endpoints do. Both sync and stream then resolve
        # credentialized variables from the request (backend v2 parity).
        apply_global_vars_to_graph(graph_copy, parsed.globals)

        if parsed.mode == "stream":
            adapter = get_stream_adapter(
                request.stream_protocol,
                StreamAdapterContext(run_id=str(uuid4()), thread_id=parsed.session_id or request.flow_id),
            )
            return StreamingResponse(
                stream_workflow_frames(graph_copy, parsed, adapter, user_id=user_id),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        return await run_workflow_sync(graph_copy, parsed, request.flow_id, user_id=user_id)
