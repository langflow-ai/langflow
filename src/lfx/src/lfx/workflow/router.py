"""The shared v2 workflow HTTP router.

lfx owns the env-neutral handler body: request parsing, stream-protocol
validation, sync/stream dispatch, error -> HTTP mapping, the lfx-default SSE
framing loop, and the ``developer_api_enabled`` router guard (which reads lfx's
own settings service). The host (:mod:`lfx.workflow.host`) supplies the
DB/tenant-bound capabilities (caller resolution, fetch-and-authorize, the
request session, durable background runs) and may override sync/stream
execution; the langflow host does, keeping its richer SSE pipeline.

Both runtimes mount the same router via :func:`create_workflow_router`, so the
request/response contract and the admission + error mapping are single-sourced.
The SSE framing is single-sourced only for hosts using the lfx default (bare
``lfx serve``); langflow overrides it.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from lfx.cli.common import execute_graph_with_capture
from lfx.cli.runtime_variables import apply_global_vars_to_graph, build_request_variables_from_global_vars
from lfx.events.event_manager import create_stream_tokens_event_manager
from lfx.processing.process import run_graph_internal
from lfx.schema.schema import InputValueRequest

# WorkflowRunRequest / WorkflowStopRequest stay runtime imports: FastAPI resolves
# a route's body annotation at request-model build time, so they cannot live under
# TYPE_CHECKING.
from lfx.schema.workflow import WorkflowRunRequest, WorkflowStopRequest  # noqa: TC001
from lfx.services.deps import get_settings_service
from lfx.services.variable.request_scope import activate_request_variables, reset_request_variables
from lfx.workflow.actions import WorkflowAction
from lfx.workflow.adapters import (
    STREAM_ADAPTERS,
    available_protocols,
)
from lfx.workflow.converters import (
    create_error_response,
    parse_workflow_run_request,
    run_response_to_workflow_response,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.graph.graph.base import Graph
    from lfx.schema.workflow import WorkflowExecutionResponse
    from lfx.workflow.adapters import StreamAdapter
    from lfx.workflow.converters import ParsedWorkflowRun
    from lfx.workflow.host import WorkflowHost


# Bounded queue between the graph run and the SSE consumer: a slow client applies
# backpressure instead of letting frames accumulate without bound.
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


@dataclass
class _RunResponse:
    """Minimal ``RunResponseLike``: the two attributes the converter reads."""

    outputs: list[Any] | None
    session_id: str | None


async def check_developer_api_enabled() -> None:
    """Router guard: 403 when the developer API is disabled in lfx settings.

    Reads lfx's own settings service, so the guard is host-independent and
    applies identically on both runtimes.
    """
    settings_service = get_settings_service()
    if settings_service is None or not settings_service.settings.developer_api_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Developer API disabled",
                "code": "DEVELOPER_API_DISABLED",
                "message": "The v2 workflow API is disabled. Set developer_api_enabled to enable it.",
            },
        )


def _reject_unsupported_fields(parsed: ParsedWorkflowRun) -> None:
    """Reject request fields a no-overrides host does not execute.

    A host without per-request graph rebuild (bare ``lfx serve``) runs a
    pre-registered, prepared graph, so live ``data`` overrides, ``tweaks``,
    ``files``, and partial-run boundaries are not supported. Request-level
    ``globals`` are supported and applied as request-scoped variables, so they
    are not rejected here. Reject the rest explicitly rather than silently ignore.
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
                "message": f"This runtime does not support these v2 fields yet: {fields}. Use the langflow "
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


async def run_workflow_sync(graph: Graph, parsed: ParsedWorkflowRun, flow_id: str) -> WorkflowExecutionResponse:
    """Run a flow to completion and build a v2 ``WorkflowExecutionResponse``.

    Uses ``run_graph_internal`` (the same primitive the langflow backend sync
    path uses) so the result is the aggregated ``RunOutputs`` shape the shared
    converter expects. Request-level ``globals`` are applied as request-scoped
    variables; unknown ``output_ids`` are rejected up front (422); component-level
    failures are returned in the body (HTTP 200) to match the v2 two-tier contract.
    """
    job_id = str(uuid4())
    terminal_ids = _terminal_node_ids(graph)
    _validate_output_ids(parsed.output_ids, terminal_ids)

    # Apply request-level globals to the graph, then activate the request scope so
    # components resolving through VariableService.get_variable see them, matching
    # the streaming path where execute_graph_with_capture does the same activation.
    # run_graph_internal does not activate them itself.
    apply_global_vars_to_graph(graph, parsed.globals)
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
    graph: Graph, parsed: ParsedWorkflowRun, adapter: StreamAdapter
) -> AsyncIterator[bytes]:
    """Run a flow and stream its events through ``adapter`` as SSE frames.

    The graph runs via ``execute_graph_with_capture`` with a token-stream
    ``EventManager`` wired in, so component token/message/error events land on a
    queue while this consumer translates them through the adapter. A failure
    becomes the adapter's terminal-error event rather than an HTTP error.

    Request-level ``globals`` are applied to the graph as request-scoped
    variables before the run; ``execute_graph_with_capture`` activates that scope
    for the duration of the run, matching the sync path.
    """
    apply_global_vars_to_graph(graph, parsed.globals)
    queue = _WorkflowEventQueue(maxsize=_STREAM_QUEUE_MAX_SIZE)
    event_manager = create_stream_tokens_event_manager(queue=queue)
    drive_error: BaseException | None = None

    async def drive() -> None:
        nonlocal drive_error
        try:
            await execute_graph_with_capture(
                graph, parsed.input_value or None, session_id=parsed.session_id, event_manager=event_manager
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


def create_workflow_router(
    host: WorkflowHost,
    *,
    prefix: str = "/workflows",
    tags: tuple[str, ...] = ("Workflow",),
    developer_api_guard: bool = True,
    auto_register_job_routes: bool = True,
    responses: dict | None = None,
) -> APIRouter:
    """Build the v2 workflow router bound to ``host``.

    Registers ``POST {prefix}`` (sync + stream + background-gated dispatch) on
    every runtime. Background job endpoints (GET status, POST ``/stop``) are
    auto-registered ONLY when ``host.supports_background`` is ``True`` *and*
    ``auto_register_job_routes`` is ``True``; bare serve's OpenAPI surface stays
    exactly ``POST {prefix}``.

    The two concerns are split on purpose. ``host.supports_background`` gates the
    POST ``mode="background"`` dispatch to :meth:`WorkflowHost.submit_background`
    (otherwise the branch 422s). ``auto_register_job_routes`` separately controls
    whether *this* router also mounts the generic GET status + POST ``/stop``
    handlers. The langflow backend passes ``supports_background=True`` (so
    background submit works) but ``auto_register_job_routes=False``, because it
    mounts its own behaviorally-richer GET ``""`` / POST ``/stop`` /
    GET ``/{job_id}/events`` handlers on the same prefix; auto-registering the
    generic ones too would put two handlers on identical method+path and shadow
    the langflow versions. Bare ``lfx serve`` keeps the default
    (``auto_register_job_routes=True``, ``supports_background=False``), so the
    ``False`` short-circuits before the flag is consulted and its surface stays
    exactly ``POST {prefix}``.

    ``developer_api_guard`` controls the ``developer_api_enabled`` 403 guard. It
    defaults to ``True`` but is an opt-in that no production mount enables: both
    the langflow backend and bare ``lfx serve`` pass ``False``, and the v2
    ``/workflows`` surface never carried a developer-API gate (byte-identical to
    today's behavior). Bare ``lfx serve`` also has no settings service to read,
    so the guard could not run there anyway.
    """
    dependencies = [Depends(check_developer_api_enabled)] if developer_api_guard else []
    router = APIRouter(prefix=prefix, tags=list(tags), dependencies=dependencies)

    @router.post(
        "",
        response_model=None,
        responses=responses or {},
        summary="Execute Workflow (v2 sync or stream)",
    )
    async def execute_workflow(request: WorkflowRunRequest, http_request: Request, background_tasks: BackgroundTasks):
        caller = await host.resolve_caller(http_request)

        # Validate the stream protocol before fetching the flow so an unknown
        # protocol returns 422 regardless of whether the flow exists or the
        # caller may access it (matches the pre-seam handler's precedence).
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

        flow = await host.get_flow(request.flow_id, caller)
        await host.authorize(caller, flow, WorkflowAction.EXECUTE)

        parsed = parse_workflow_run_request(request)
        if not host.supports_request_overrides:
            _reject_unsupported_fields(parsed)

        if parsed.mode == "background":
            if not host.supports_background:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "Unsupported mode",
                        "code": "LFX_SERVE_UNSUPPORTED_MODE",
                        "message": "This runtime supports mode 'sync' and 'stream'. Background runs need the "
                        "langflow backend (durable jobs + queue).",
                    },
                )
            return await host.submit_background(parsed, flow, caller, stream_protocol=request.stream_protocol)

        if parsed.mode == "stream":
            # The host owns the SSE loop so a DB-backed runtime can inject its own
            # build/persistence pipeline (langflow's v1 build-vertex loop, agui
            # side-channel, vertex-build persistence). Bare serve falls back to
            # lfx's leaner ``stream_workflow_frames`` via the base default.
            return host.stream_response(
                parsed,
                flow,
                caller,
                stream_protocol=request.stream_protocol,
                http_request=http_request,
                background_tasks=background_tasks,
            )

        return await host.run_sync(parsed, flow, caller, http_request=http_request, background_tasks=background_tasks)

    if host.supports_background and auto_register_job_routes:
        _register_job_routes(router, host)

    return router


def _register_job_routes(router: APIRouter, host: WorkflowHost) -> None:
    """Register the durable background job endpoints (LF-only, gated by the host)."""

    @router.get("", response_model=None, summary="Get Workflow Job Status (v2 background)")
    async def get_job_status(job_id: str, http_request: Request):
        caller = await host.resolve_caller(http_request)
        async with host.session() as session:
            return await host.get_job_status(job_id, caller, session)

    @router.post("/stop", summary="Stop Workflow Job (v2 background)")
    async def stop_job(request: WorkflowStopRequest, http_request: Request):
        caller = await host.resolve_caller(http_request)
        return await host.stop_job(str(request.job_id), caller)
