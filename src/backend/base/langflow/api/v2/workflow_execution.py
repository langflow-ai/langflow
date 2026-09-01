"""Synchronous and streaming execution for V2 workflows.

This module owns the run-driving machinery shared by every execution mode:

    - ``execute_sync_workflow`` / ``execute_sync_workflow_with_timeout``: the
      inline sync path that returns a complete ``WorkflowExecutionResponse``.
    - ``_stream_event_frames``: the single chokepoint that drives the v1
      build-vertex loop and dispatches its events through a ``StreamAdapter``.
      The streaming route, the public endpoint, and the background buffer all
      consume it.
    - ``_execute_streaming_workflow``: wraps ``_stream_event_frames`` in an SSE
      response for live streaming.

Configuration:
    EXECUTION_TIMEOUT: Maximum execution time for synchronous workflows (300 seconds).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Final
from uuid import UUID, uuid4

from ag_ui.core import CustomEvent
from fastapi import BackgroundTasks, Request
from fastapi.responses import EventSourceResponse
from fastapi.sse import format_sse_event
from lfx.events.event_manager import create_default_event_manager
from lfx.exceptions.tweaks import TweakRefusedError
from lfx.graph.checkpoint.store import CheckpointStore
from lfx.graph.exceptions import GraphPausedException
from lfx.graph.graph.base import Graph
from lfx.log.logger import logger
from lfx.observability import execution_protocol, extract_trace_link, queued_trace_link, tracing_is_available
from lfx.schema.schema import InputValueRequest
from lfx.schema.workflow import JobStatus, WorkflowExecutionResponse
from lfx.workflow.adapters import StreamAdapter, StreamEvent
from lfx.workflow.adapters.langflow import WORKFLOW_OUTPUT_CAPTURE_EVENT, build_terminal_output_event
from lfx.workflow.converters import ParsedWorkflowRun, create_error_response, run_response_to_workflow_response

from langflow.api.utils import extract_global_variables_from_headers
from langflow.api.utils.execution_errors import caller_owns_flow, error_for_client
from langflow.api.v1.schemas import FlowDataRequest, RunResponse
from langflow.api.v2.workflow_validation import _validate_output_ids
from langflow.api.warm_graph import warm_deepcopy
from langflow.exceptions.api import WorkflowTimeoutError, WorkflowValidationError
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_job_service, get_memory_base_service, get_settings_service, get_task_service
from langflow.services.model_provider_policy_scope import scoped_model_provider_policy_for_flow
from langflow.services.warm_registry.service import flow_version

# Configuration constants
EXECUTION_TIMEOUT = 300  # 5 minutes default timeout for sync execution, used as a fallback


def _resolve_execution_timeout() -> int:
    """Wall-clock ceiling for a single workflow run, from settings.

    Falls back to ``EXECUTION_TIMEOUT`` if the settings service is unavailable
    (e.g. a fire-and-forget background coroutine running during teardown).
    """
    try:
        return get_settings_service().settings.workflow_execution_timeout
    except Exception:  # noqa: BLE001
        return EXECUTION_TIMEOUT


# Inline stream queue between the build loop and the SSE consumer. Bounded
# so a slow consumer applies backpressure to the build loop instead of
# letting frames accumulate without bound when the network is slow.
_EVENT_QUEUE_MAX_SIZE = 256


class _CeilingFromSettings:
    """Sentinel type for ``_stream_event_frames(execution_timeout=...)``.

    Its own class rather than a bare ``object()`` so the parameter carries a real
    static type and an ``isinstance`` check narrows the remaining value to
    ``float | None`` for ``asyncio.wait_for``. Distinct from ``None`` so a caller
    can ask for "unbounded" without it collapsing into "use the default".
    """


_CEILING_FROM_SETTINGS: Final = _CeilingFromSettings()


async def generate_flow_events(*args, **kwargs) -> None:
    """Lazily call the v1 build stream to avoid import cycles during router setup."""
    from langflow.api.build import generate_flow_events as _generate_flow_events

    await _generate_flow_events(*args, **kwargs)


def _resolve_request_variables(body_globals: dict[str, str], http_request: Request | None) -> dict[str, str]:
    """Merge request-level global variables for a v2 workflow execution.

    v2 workflows take globals from the JSON request body (``globals``). The
    ``X-LANGFLOW-GLOBAL-VAR-*`` headers remain a supported transport (the
    OpenAI-compatible Responses API passes globals that way); body globals win
    on conflict.
    """
    header_globals: dict[str, str] = {}
    if http_request is not None:
        header_globals = extract_global_variables_from_headers(http_request.headers)
    return {**header_globals, **dict(body_globals or {})}


def _build_run_inputs(parsed: ParsedWorkflowRun) -> list[InputValueRequest] | None:
    """Build the graph input list from the AG-UI chat message, if any.

    The last user message becomes a single chat input; an empty message means
    the flow runs with no chat input (parameters arrive via tweaks instead).
    """
    if not parsed.input_value:
        return None
    return [InputValueRequest(components=[], input_value=parsed.input_value, type="chat")]


def _single_input_value_request(parsed: ParsedWorkflowRun) -> InputValueRequest | None:
    """Build the single chat InputValueRequest the v1 build loop accepts.

    The v1 build path (``generate_flow_events``) takes a single
    ``InputValueRequest``; when it receives ``None`` it falls back to
    ``InputValueRequest(session=str(flow_id))``, which would wipe out the
    caller's session id. We always return one with the parsed session so
    component messages stay scoped to the user's active session, even when
    there is no chat input (e.g. the playground "Run Flow" button).
    """
    if not parsed.session_id and not parsed.input_value:
        return None
    return InputValueRequest(
        components=[],
        input_value=parsed.input_value or "",
        type="chat",
        session=parsed.session_id,
    )


_QueueItem = tuple[str | None, bytes | None, float]


class _WorkflowEventQueue:
    """Bounded EventManager handoff that fails explicitly instead of dropping events."""

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


async def _queued_trace_link_for(job_id: UUID | None):
    """Return a link to the request that enqueued *job_id*, or None.

    None for a synchronous run, which has no job row, and for a job enqueued while nothing was
    tracing. Never raises: a run must not fail because its telemetry could not be looked up.
    """
    if job_id is None:
        return None
    if not tracing_is_available():
        # The row would be read, parsed, and thrown away. A deployment without the telemetry
        # extra should not pay a SELECT per run and per resume for a link nothing can render.
        return None
    try:
        job = await get_job_service().get_job_by_job_id(job_id)
    except Exception:  # noqa: BLE001
        await logger.adebug("could not read the job row for its trace carrier", exc_info=True)
        return None
    return extract_trace_link(job.job_metadata if job else None)


async def _stream_event_frames(
    *,
    adapter: StreamAdapter,
    flow_id: UUID,
    flow_name: str | None,
    background_tasks: BackgroundTasks,
    parsed: ParsedWorkflowRun,
    current_user: UserRead,
    provider_policy_flow: FlowRead | None = None,
    source_flow_id: UUID | None = None,
    source_flow_owner_id: UUID | None = None,
    run_id: str | None = None,
    job_id: UUID | None = None,
    resume: dict | None = None,
    track_job_status: bool = True,
    # Required, not defaulted: a default is how an unwired caller gets a confidently wrong
    # label, which is the one thing the absent-rather-than-"unknown" rule exists to prevent.
    protocol: str,
    emit_output_capture: bool = False,
    expose_error_details: bool = False,
    execution_timeout: float | None | _CeilingFromSettings = _CEILING_FROM_SETTINGS,
) -> AsyncIterator[tuple[bytes, str]]:
    """Run a flow via the v1 build-vertex loop, dispatch its events through ``adapter``.

    Yields ``(sse_frame_bytes, event_type_str)`` pairs. The consumer
    (streaming endpoint, background buffer) frames are pre-formatted with a
    monotonic ``id:`` for ``Last-Event-ID`` resume. The ``event_type_str`` is
    the adapter's protocol-native type so the buffer task can finalize a
    background job's status structurally (no substring matching).

    A failure during the run becomes a terminal protocol event (e.g.
    ``RUN_ERROR`` for AG-UI, ``error`` for langflow) routed through the
    adapter; closing the consumer cancels the run.

    When the adapter is AG-UI, side-channel ``CustomEvent`` frames carry
    the raw Langflow payload alongside the AG-UI translation for the
    playground's chat-view. A follow-up retires this once chat-view
    consumes the AG-UI ``TEXT_MESSAGE_*`` lifecycle directly.

    ``execution_timeout`` bounds the run. It defaults to the settings ceiling,
    which is the right budget for a caller with a waiting HTTP client (stream,
    public). Background runs pass ``None``: nothing is waiting on them, and their
    budget is ``background_job_timeout``, enforced by ``JobRunner`` one layer out.
    Resolving the ceiling here for them too nested two budgets, and the inner one
    always wins, which made the documented ``background_job_timeout=None``
    ("no timeout") silently cap at the sync ceiling instead.
    """
    # EventManager uses put_nowait(), so a plain bounded asyncio.Queue would
    # silently drop frames via QueueFull. This adapter keeps memory bounded and
    # converts overflow into an explicit stream error + sentinel.
    queue = _WorkflowEventQueue(maxsize=_EVENT_QUEUE_MAX_SIZE)
    event_manager = create_default_event_manager(queue)
    input_request = _single_input_value_request(parsed)
    flow_data = FlowDataRequest(**parsed.data) if parsed.data else None
    # Ceiling for the modes whose caller is waiting on a socket (stream, public).
    # Sync uses its own asyncio.wait_for upstream; background passes None and is
    # bounded by JobRunner instead. wait_for(timeout=None) simply awaits.
    if isinstance(execution_timeout, _CeilingFromSettings):
        execution_timeout = _resolve_execution_timeout()

    # Captured from drive()'s exception path so the consumer can yield a
    # guaranteed adapter.error_events(...) fallback after the queue loop ends.
    # Layered error handling, by design:
    #   1. ``event_manager.on_error(...)`` is the cooperative path: the
    #      translator turns it into the protocol's terminal-error event (e.g.
    #      RUN_ERROR for AG-UI, ``error`` for langflow) so the buffer's
    #      structural detector flips the job to FAILED.
    #   2. ``adapter.error_events(exc)`` is the dispatcher's guaranteed
    #      fallback: emitted from the consumer side when ``generate_flow_events``
    #      raises before any cooperative terminal error reaches the queue.
    #      Without this yield, an early failure would leave the stream with no
    #      terminal error event and the buffer would mark the job COMPLETED.
    #   3. The buffer task's ``terminal_error_type`` check fires on either
    #      RUN_ERROR source, so a single drive() failure cannot result in a
    #      job marked COMPLETED.
    drive_error: Exception | None = None

    async def drive() -> None:
        nonlocal drive_error
        try:
            # Bound here rather than in the enclosing generator: drive() runs as its own task, so
            # the set/reset pair cannot straddle a generator suspension point and leak into the
            # consumer task that resumes it.
            #
            # The queued-run link rides alongside for the same reason and in the same place. It
            # is None for a run with a live request above it, and the context manager is a no-op
            # then, so this costs a synchronous path nothing.
            with (
                scoped_model_provider_policy_for_flow(
                    provider_policy_flow,
                    user_id=current_user.id,
                    is_superuser=bool(getattr(current_user, "is_superuser", False)),
                ),
                execution_protocol(protocol),
                queued_trace_link(await _queued_trace_link_for(job_id)),
            ):
                await asyncio.wait_for(
                    generate_flow_events(
                        flow_id=flow_id,
                        provider_policy_flow=provider_policy_flow,
                        background_tasks=background_tasks,
                        event_manager=event_manager,
                        inputs=input_request,
                        data=flow_data,
                        files=parsed.files,
                        stop_component_id=parsed.stop_component_id,
                        start_component_id=parsed.start_component_id,
                        # Persist vertex builds only for durable/background jobs. Live streams
                        # carry a ``run_id`` for job/trace/telemetry correlation, but keep the
                        # existing no-build-persistence behavior because they pass no ``job_id``.
                        log_builds=job_id is not None,
                        current_user=current_user,
                        flow_name=flow_name,
                        source_flow_id=source_flow_id,
                        source_flow_owner_id=source_flow_owner_id,
                        run_id=run_id,
                        job_id=job_id,
                        resume=resume,
                        track_job_status=track_job_status,
                        # The sync path applies tweaks before Graph construction; this loop
                        # builds from the DB (or request data), so without this the streaming
                        # and background paths silently drop request tweaks.
                        tweaks=parsed.tweaks,
                        expose_error_details=expose_error_details,
                        # Anonymous serving runs are ephemeral: thread the no-persist
                        # decision onto the graph so astore_message skips the DB write.
                        persist_messages=parsed.persist_messages,
                        # Carry the end-user identity onto the graph so per-user state
                        # (chat memory) scopes to the end user.
                        end_user_id=parsed.end_user_id,
                    ),
                    timeout=execution_timeout,
                )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            # Wall-clock ceiling hit. Surface it as a sanitized terminal error
            # through the guaranteed-fallback block below: stream/public clients
            # see a clean RUN_ERROR/error and a background job is marked FAILED.
            # No internal detail reaches the wire (coordinates with I3).
            await logger.awarning(
                "Workflow run %s exceeded %ss execution ceiling", run_id or flow_id, execution_timeout
            )
            drive_error = WorkflowTimeoutError("Workflow execution timed out.")
            with contextlib.suppress(Exception):
                await event_manager.queue.put((None, None, time.time()))
        except Exception as exc:  # noqa: BLE001
            await logger.aexception("Workflow run %s failed during event generation", run_id or flow_id)
            drive_error = exc
            with contextlib.suppress(Exception):
                await event_manager.queue.put((None, None, time.time()))
        # generate_flow_events emits on_end and the sentinel on success.

    def _frame(stream_event: StreamEvent, seq: int) -> tuple[bytes, str]:
        return (
            format_sse_event(data_str=stream_event.data_json, id=str(seq)),
            stream_event.type,
        )

    # The AG-UI playground's chat-view consumes the v1 message payload via a
    # side-channel ``CustomEvent``; emitted only when the wire protocol is
    # AG-UI. A follow-up retires this once chat-view consumes AG-UI primitives.
    emit_side_channel = adapter.name == "agui"
    side_channel_events = frozenset({"add_message", "token", "remove_message", "error", "end"})
    terminal_error_type = getattr(adapter, "terminal_error_type", None)
    terminal_error_seen = False
    stream_paused = False
    _stream_completed = False
    _stream_cancelled = False

    seq = 0
    _run_start = time.perf_counter()
    run_task = asyncio.create_task(drive())
    try:
        for event in adapter.initial_events():
            yield _frame(event, seq)
            seq += 1
        while True:
            _, value, _ = await queue.get()
            if value is None:
                break
            payload = json.loads(value.decode("utf-8"))
            event_type = payload.get("event", "")
            event_data = payload.get("data") or {}
            if emit_side_channel and event_type in side_channel_events:
                yield _frame(
                    StreamEvent(
                        type="CUSTOM",
                        data_json=CustomEvent(
                            name="langflow.event",
                            value={"event_type": event_type, "data": event_data},
                        ).model_dump_json(by_alias=True, exclude_none=True),
                    ),
                    seq,
                )
                seq += 1
            # Off-wire terminal-output capture for ``Job.result`` (background only).
            # Synthesized from the RAW ``end_vertex`` here — before ``adapter.translate``
            # — so it is protocol-neutral: the ``agui`` adapter emits no wire ``output``
            # event, so without this its background GET-status would carry no outputs.
            # The runner captures this frame in-memory only (never persisted to
            # ``job_events``, never published), so the wire is unchanged for every
            # protocol and the capture is independent of durable-event storage.
            if emit_output_capture and event_type == "end_vertex":
                output = build_terminal_output_event(event_data)
                if output is not None:
                    capture_payload = {"event": "output", "data": output.model_dump(mode="json")}
                    yield _frame(
                        StreamEvent(
                            type=WORKFLOW_OUTPUT_CAPTURE_EVENT,
                            data_json=json.dumps(capture_payload, default=str),
                        ),
                        seq,
                    )
                    seq += 1

            for event in adapter.translate(event_type, event_data):
                if terminal_error_type is not None and event.type == terminal_error_type:
                    terminal_error_seen = True
                frame_bytes, frame_type = _frame(event, seq)
                # Runner detects a pause by the langflow-side type; agui maps it to CUSTOM.
                if event_type == "human_input_required":
                    stream_paused = True
                    frame_type = "human_input_required"
                yield (frame_bytes, frame_type)
                seq += 1
        for event in adapter.final_events():
            if terminal_error_type is not None and event.type == terminal_error_type:
                terminal_error_seen = True
            yield _frame(event, seq)
            seq += 1
        # Guaranteed-fallback layer (see drive_error block above). If drive()
        # captured an exception and no cooperative terminal error reached the
        # stream, emit the adapter's terminal error event(s) here.
        if drive_error is not None and not terminal_error_seen:
            client_error = (
                drive_error
                if isinstance(drive_error, WorkflowTimeoutError)
                else error_for_client(drive_error, expose_details=expose_error_details)
            )
            for event in adapter.error_events(client_error):
                if terminal_error_type is not None and event.type == terminal_error_type:
                    terminal_error_seen = True
                yield _frame(event, seq)
                seq += 1
        # Reached only when the try body exits normally (no cancellation or exception).
        _stream_completed = True
    except asyncio.CancelledError:
        # Client disconnected (or server shutdown). Not a workflow failure — suppress
        # telemetry so a tab-close is never recorded as a failed run.
        _stream_cancelled = True
        raise
    finally:
        if not run_task.done():
            run_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await run_task
        await queue.aclose()
        # Emit a RunPayload so Enterprise metering (run_event_store) and the
        # Scarf telemetry pipeline both see every v2 workflow run.
        # Mirrors the v1 endpoints.py instrumentation for the streaming path.
        # Skip on: pause (run is resumable), client disconnect (not a failure).
        if not stream_paused and not _stream_cancelled:
            try:
                from langflow.services.deps import get_telemetry_service
                from langflow.services.telemetry.schema import RunPayload

                _telemetry = get_telemetry_service()
                if _telemetry is not None:
                    _run_success = _stream_completed and not terminal_error_seen
                    await _telemetry.log_package_run(
                        RunPayload(
                            run_is_webhook=False,
                            run_seconds=int(time.perf_counter() - _run_start),
                            run_success=_run_success,
                            run_error_message="" if _run_success else str(drive_error or "workflow error"),
                            run_id=run_id,
                        )
                    )
            except Exception:  # noqa: BLE001
                await logger.awarning("Telemetry hook failed for streaming run %s", run_id or flow_id, exc_info=True)


def _execute_streaming_workflow(
    *,
    adapter: StreamAdapter,
    run_id: str,
    parsed: ParsedWorkflowRun,
    flow: FlowRead,
    current_user: UserRead,
    background_tasks: BackgroundTasks,
) -> EventSourceResponse:
    """Run a workflow live and stream events via ``adapter`` over server-sent events.

    The graph is built inside ``generate_flow_events`` (the v1 build-vertex
    loop) so the same per-vertex events the canvas already knows flow through
    the adapter. A failure during the run becomes a terminal protocol event
    routed through the adapter rather than an HTTP error.
    """

    async def _frames_only() -> AsyncIterator[bytes]:
        async for frame, _event_type in _stream_event_frames(
            adapter=adapter,
            flow_id=flow.id,
            flow_name=flow.name,
            background_tasks=background_tasks,
            parsed=parsed,
            current_user=current_user,
            provider_policy_flow=flow,
            source_flow_owner_id=flow.user_id,
            run_id=run_id,
            # The live v2 stream. Which client sent it is a separate attribute, read from the
            # X-Langflow-Client header, because the playground calls this same public endpoint.
            protocol="v2",
            expose_error_details=caller_owns_flow(flow, current_user),
        ):
            yield frame

    return EventSourceResponse(
        _frames_only(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def execute_sync_workflow_with_timeout(
    parsed: ParsedWorkflowRun,
    flow: FlowRead,
    job_id: UUID,
    current_user: UserRead,
    background_tasks: BackgroundTasks,
    http_request: Request,
    checkpoint_store: CheckpointStore | None = None,
    *,
    expose_error_details: bool | None = None,
) -> WorkflowExecutionResponse:
    """Execute workflow with timeout protection.

    Args:
        parsed: The parsed AG-UI run parameters
        flow: The flow to execute
        job_id: Generated job ID for tracking
        current_user: Authenticated user
        background_tasks: FastAPI background tasks
        http_request: The HTTP request object for extracting headers
        checkpoint_store: When provided, enables HITL checkpointing so a flow that
            pauses for human input returns a ``suspended`` response instead of failing.
        expose_error_details: Override the owner-derived client error policy.

    Returns:
        WorkflowExecutionResponse with complete results

    Raises:
        WorkflowTimeoutError: If execution exceeds timeout
        WorkflowValidationError: If flow validation fails
    """
    try:
        return await asyncio.wait_for(
            execute_sync_workflow(
                parsed=parsed,
                flow=flow,
                job_id=job_id,
                current_user=current_user,
                background_tasks=background_tasks,
                http_request=http_request,
                checkpoint_store=checkpoint_store,
                expose_error_details=expose_error_details,
            ),
            timeout=_resolve_execution_timeout(),
        )
    except asyncio.TimeoutError as e:
        raise WorkflowTimeoutError from e


async def _persist_sync_result(job_service, job_id: UUID, workflow_response, request_blob: dict, flow_id) -> None:
    """Best-effort cache of a completed sync run's outputs + request for GET status.

    Writes two things so a later GET status on this sync job_id rebuilds the SAME
    response the caller received inline:

    * ``job_metadata["request"]`` — the submit request (mirrors what the background
      service persists). The GET completed-status path resolves the session from it
      (``persisted_request.get("session_id")``); only the background service writes
      this blob, so without it a sync GET would degrade ``session_id`` to the flow id.
    * ``Job.result`` — the ``{component_id, ...ComponentOutput}`` list shape the
      background runner stores, rebuilt by ``workflow_response_from_output_events``.

    The request blob is written FIRST so the GET completed-status invariant holds: a
    persisted ``Job.result`` always has its session alongside it. If the result write
    then fails, GET falls back to vertex-build reconstruction (which resolves the
    session independently) instead of serving a result with a flow-id session.

    The caller gates this on ``sync_result_storage_enabled``. The run has already
    executed and succeeded upstream, so EVERY exception this can raise (serialization
    or a DB write — e.g. a SQLite ``OperationalError`` under lock contention) is a
    persistence failure, never a workflow failure. Catch broadly so such an error
    cannot escape to the caller's terminal ``except Exception`` and be misreported as
    a failed run. ``asyncio.CancelledError`` is a ``BaseException`` and still
    propagates, so timeouts/disconnects are unaffected.
    """
    try:
        await job_service.update_job_metadata(job_id, {"request": request_blob})
        output_events = [
            {"component_id": component_id, **output.model_dump(mode="json")}
            for component_id, output in (workflow_response.outputs or {}).items()
        ]
        await job_service.set_result(job_id, {"status": "completed", "outputs": output_events})
    except Exception:  # noqa: BLE001 — best-effort cache; the response is already built inline
        await logger.awarning("Sync result persistence failed for flow %s", flow_id, exc_info=True)


async def execute_sync_workflow(
    parsed: ParsedWorkflowRun,
    flow: FlowRead,
    job_id: UUID,
    current_user: UserRead,
    background_tasks: BackgroundTasks,  # noqa: ARG001
    http_request: Request,
    checkpoint_store: CheckpointStore | None = None,
    *,
    expose_error_details: bool | None = None,
) -> WorkflowExecutionResponse:
    """Execute workflow synchronously and return complete results.

    This function implements a two-tier error handling strategy:
        1. System-level errors (validation, graph build): Raised as exceptions
        2. Component execution errors: Returned in response body with HTTP 200

    This approach allows clients to receive partial results even when some
    components fail, which is useful for debugging and incremental processing.

    Execution Flow:
        1. Apply tweaks and chat input from the parsed AG-UI request
        2. Validate flow data exists
        3. Extract context from HTTP headers
        4. Build graph from flow data with tweaks applied
        5. Identify terminal nodes for execution
        6. Execute graph and collect results
        7. Convert V1 RunResponse to V2 WorkflowExecutionResponse

    Args:
        parsed: The parsed AG-UI run parameters with tweaks and chat input
        flow: The flow model from database
        job_id: Generated job ID for tracking this execution
        current_user: Authenticated user for permission checks
        background_tasks: FastAPI background tasks (unused in sync mode)
        http_request: The HTTP request object for extracting headers
        checkpoint_store: When provided, enables HITL checkpointing so a pausing flow
            returns a ``suspended`` response (carrying the human-input request) instead of
            running through. Off by default, so non-HITL callers are unchanged.
        expose_error_details: Override the owner-derived client error policy.

    Returns:
        WorkflowExecutionResponse: Complete execution results with outputs and metadata

    Raises:
        WorkflowValidationError: If flow data is None or graph build fails
    """
    if expose_error_details is None:
        expose_error_details = caller_owns_flow(flow, current_user)

    # Tweaks and chat input come straight from the parsed AG-UI request
    tweaks = parsed.tweaks
    session_id = parsed.session_id

    # Validate flow data - this is a system error, not execution error
    if flow.data is None:
        msg = f"Flow {flow.id} has no data. The flow may be corrupted."
        validation_error = WorkflowValidationError(msg)
        if expose_error_details:
            raise validation_error
        client_error = error_for_client(validation_error, expose_details=False)
        raise WorkflowValidationError(str(client_error)) from validation_error

    # Resolve request-level variables: body ``globals`` plus the legacy
    # X-LANGFLOW-GLOBAL-VAR-* headers (still used by the Responses API).
    # Body globals win on conflict.
    request_variables = _resolve_request_variables(parsed.globals, http_request)

    # Build context from request variables (similar to V1's _run_flow_internal)
    context = {"request_variables": request_variables} if request_variables else None

    # Build graph - system error if this fails
    try:
        flow_id_str = str(flow.id)
        user_id = str(current_user.id)
        # Caller-supplied ``data`` is rejected for sync mode before the execution gates run,
        # so a value here is the server-sanitized stored graph produced by the caller-aware
        # component policy. It must win over ``flow.data``, and it must bypass the warm
        # template — which is built from the unsanitized stored row.
        sanitized_flow_data = parsed.data
        # Opt-in warm fast-path: serve a deepcopy of the pre-built template
        # instead of rebuilding. Cold-fall-back (None) for tweaks, request context/globals,
        # or a HITL/checkpointed run — none of which fit a shared user-agnostic template.
        graph = None
        with scoped_model_provider_policy_for_flow(
            flow,
            user_id=current_user.id,
            is_superuser=bool(getattr(current_user, "is_superuser", False)),
        ):
            if sanitized_flow_data is None and not tweaks and context is None and checkpoint_store is None:
                graph = await warm_deepcopy(
                    flow_id_str,
                    expected_version=flow_version(flow.updated_at),
                    user_id=user_id,
                    session_id=session_id,
                    stream=False,
                )
            if graph is None:
                # Use deepcopy to prevent mutation of the original flow.data
                # process_tweaks modifies nested dictionaries in-place
                graph_data = deepcopy(sanitized_flow_data if sanitized_flow_data is not None else flow.data)
                graph_data = process_tweaks(graph_data, tweaks, stream=False)
                # Pass context to graph (similar to V1's simple_run_flow)
                # This allows components to access request metadata via graph.context
                graph = Graph.from_payload(
                    graph_data,
                    flow_id=flow_id_str,
                    user_id=user_id,
                    flow_name=flow.name,
                    context=context,
                )
        # Serving-plane end-user scoping: an anonymous run is ephemeral, so mark the
        # graph non-persisting (astore_message honors this per component). Defaults
        # True for every other run.
        graph.persist_messages = parsed.persist_messages
        # Carry the end-user identity onto the graph so services (chat memory) scope
        # per-user state to the end user. None for anonymous / feature-off / editor runs.
        graph.end_user_id = parsed.end_user_id
        # Set run_id for tracing/logging (similar to V1's simple_run_flow)
        graph.set_run_id(job_id)
        # HITL: when a checkpoint store is supplied, a pausing node (HumanInput) durably
        # checkpoints and suspends instead of running straight through. Off by default,
        # so non-HITL callers are unchanged.
        if checkpoint_store is not None:
            graph.checkpointing_enabled = True
            graph.checkpoint_store = checkpoint_store
    except TweakRefusedError:
        # A refused tweak is a caller error, not a malformed flow. Wrapping it as
        # a validation failure discards the structured body naming the refused
        # keys, so let the app-level handler answer with 422.
        raise
    except Exception as e:
        client_error = error_for_client(e, expose_details=expose_error_details)
        msg = f"Failed to build graph from flow data: {client_error!s}"
        raise WorkflowValidationError(msg) from e

    # Get terminal nodes - these are the outputs we want
    terminal_node_ids = graph.get_terminal_nodes()

    # Validate request-side output selection BEFORE executing: a bad id must cost
    # no compute. Raised outside the component-error try/except below, so it
    # surfaces as a real 422 rather than a 200-with-failed body.
    _validate_output_ids(parsed.output_ids, terminal_node_ids)

    # Execute graph - component errors are caught and returned in response body
    job_service = get_job_service()
    # user_id stays the executing service account (flow fetch / resume rely on it); the end
    # user is recorded in job_metadata so status/stop isolate to it. See F8 / create_job.
    await job_service.create_job(
        job_id=job_id, flow_id=flow_id_str, user_id=current_user.id, end_user_id=parsed.end_user_id
    )
    _sync_run_paused = False
    _sync_run_success = False
    _sync_run_error: str = ""
    _run_start = time.perf_counter()
    try:
        with (
            scoped_model_provider_policy_for_flow(
                flow,
                user_id=current_user.id,
                is_superuser=bool(getattr(current_user, "is_superuser", False)),
            ),
            execution_protocol("v2"),
        ):
            task_result, execution_session_id = await job_service.execute_with_status(
                job_id=job_id,
                run_coro_func=run_graph_internal,
                graph=graph,
                flow_id=flow_id_str,
                session_id=session_id,
                inputs=_build_run_inputs(parsed),
                outputs=terminal_node_ids,
                stream=False,
            )

        # MemoryBase auto-capture resolves the watching owner's embedding and
        # preprocessing credentials by ``flow_id``. Only an owner-equivalent
        # execution principal may trigger that owner-scoped side effect. This
        # shared executor is also used by PUBLIC/A2A and delegated-share runs;
        # letting either caller schedule this hook would spend another user's
        # credentials and persist into their private knowledge base.
        if caller_owns_flow(flow, current_user):
            try:
                _run_id_uuid = UUID(graph.run_id) if graph.run_id else None  # type-cast only; same run_id set on graph
                await get_task_service().fire_and_forget_task(
                    get_memory_base_service().on_flow_output,
                    flow_id=flow.id,
                    session_id=execution_session_id,
                    job_id=_run_id_uuid,
                )
            except (RuntimeError, ValueError, OSError):
                await logger.awarning("Memory base hook scheduling failed for flow %s", flow.id, exc_info=True)

        # Build RunResponse
        run_response = RunResponse(outputs=task_result, session_id=execution_session_id)
        # Convert to WorkflowExecutionResponse
        workflow_response = run_response_to_workflow_response(
            run_response=run_response,
            flow_id=parsed.flow_id,
            job_id=str(job_id),
            inputs=parsed.tweaks,
            graph=graph,
            effective_globals=request_variables,
            selected_ids=parsed.output_ids,
        )
        # Optionally cache the completed run's outputs + request to the job row so a
        # later GET status returns the same response. Off by default: sync callers
        # already hold the full response inline, so this is an opt-in per-request
        # write for consumers that poll GET status for a sync job. The request blob
        # mirrors the background service's shape (identifying fields only, no tweaks/
        # globals — those may carry secrets); GET resolves the session from it.
        if get_settings_service().settings.sync_result_storage_enabled:
            request_blob = {
                "flow_id": str(flow.id),
                "mode": "sync",
                "session_id": execution_session_id,
                "input_value": parsed.input_value,
                "output_ids": parsed.output_ids,
            }
            await _persist_sync_result(job_service, job_id, workflow_response, request_blob, flow.id)
        _sync_run_success = True
        return workflow_response  # noqa: TRY300 — keep response-building under the broad except below

    except GraphPausedException as exc:
        # HITL: a pausing node suspended the run for human input. The checkpoint is already
        # persisted in checkpoint_store; surface a suspended response carrying the request so
        # the caller can resume. Only reachable when a checkpoint_store was supplied.
        # execute_with_status left the Job row IN_PROGRESS on the pause (it re-raises without a
        # terminal write). Flip it to SUSPENDED like the background runner does, or the orphan sweep
        # reaps this parked run to FAILED (worker_lost) once its heartbeat goes stale, and resume
        # (WHERE status=SUSPENDED) could never re-claim it.
        await job_service.update_job_status(job_id, JobStatus.SUSPENDED)
        suspended_response = WorkflowExecutionResponse(
            flow_id=parsed.flow_id,
            session_id=session_id,
            job_id=str(job_id),
            status=JobStatus.SUSPENDED,
            human_request=exc.data or {},
        )
        _sync_run_paused = True
        return suspended_response
    except asyncio.CancelledError:
        # Re-raise CancelledError to allow timeout mechanism to work properly
        # This ensures asyncio.wait_for() can properly cancel and raise TimeoutError
        raise
    except asyncio.TimeoutError as e:
        # Re-raise TimeoutError to allow timeout mechanism to work properly
        # This ensures asyncio.wait_for() can properly cancel and raise TimeoutError
        raise WorkflowTimeoutError from e
    except Exception as exc:  # noqa: BLE001
        # Component execution errors - return in response body with HTTP 200
        # This allows partial results and detailed error information per component
        _sync_run_error = str(exc)
        return create_error_response(
            flow_id=parsed.flow_id,
            job_id=job_id,
            inputs=parsed.tweaks,
            error=error_for_client(exc, expose_details=expose_error_details),
            effective_globals=request_variables,
        )
    finally:
        # Emit a RunPayload so Enterprise metering (run_event_store) and the
        # Scarf telemetry pipeline both see every v2 sync workflow run.
        # Mirrors the _stream_event_frames instrumentation for the SSE path.
        if not _sync_run_paused:
            try:
                from langflow.services.deps import get_telemetry_service
                from langflow.services.telemetry.schema import RunPayload

                _telemetry = get_telemetry_service()
                if _telemetry is not None:
                    await _telemetry.log_package_run(
                        RunPayload(
                            run_is_webhook=False,
                            run_seconds=int(time.perf_counter() - _run_start),
                            run_success=_sync_run_success,
                            run_error_message="" if _sync_run_success else (_sync_run_error or "workflow error"),
                            run_id=str(job_id),
                        )
                    )
            except Exception:  # noqa: BLE001
                await logger.awarning("Telemetry hook failed for sync run %s", job_id, exc_info=True)
