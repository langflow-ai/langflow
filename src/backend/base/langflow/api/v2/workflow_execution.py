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
from uuid import UUID, uuid4

from ag_ui.core import CustomEvent
from fastapi import BackgroundTasks, Request
from fastapi.responses import EventSourceResponse
from fastapi.sse import format_sse_event
from lfx.events.event_manager import create_default_event_manager
from lfx.graph.graph.base import Graph
from lfx.log.logger import logger
from lfx.schema.schema import InputValueRequest
from lfx.schema.workflow import WorkflowExecutionResponse
from lfx.workflow.adapters import StreamAdapter, StreamEvent
from lfx.workflow.converters import ParsedWorkflowRun, create_error_response, run_response_to_workflow_response

from langflow.api.utils import extract_global_variables_from_headers
from langflow.api.v1.schemas import FlowDataRequest, RunResponse
from langflow.api.v2.workflow_validation import _validate_output_ids
from langflow.exceptions.api import WorkflowTimeoutError, WorkflowValidationError
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_job_service, get_memory_base_service, get_settings_service, get_task_service

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


async def _stream_event_frames(
    *,
    adapter: StreamAdapter,
    flow_id: UUID,
    flow_name: str | None,
    background_tasks: BackgroundTasks,
    parsed: ParsedWorkflowRun,
    current_user: UserRead,
    source_flow_id: UUID | None = None,
    run_id: str | None = None,
    track_job_status: bool = True,
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
    """
    # EventManager uses put_nowait(), so a plain bounded asyncio.Queue would
    # silently drop frames via QueueFull. This adapter keeps memory bounded and
    # converts overflow into an explicit stream error + sentinel.
    queue = _WorkflowEventQueue(maxsize=_EVENT_QUEUE_MAX_SIZE)
    event_manager = create_default_event_manager(queue)
    input_request = _single_input_value_request(parsed)
    flow_data = FlowDataRequest(**parsed.data) if parsed.data else None
    # Single wall-clock ceiling for every mode that drives this loop (stream,
    # background, public). Sync uses its own asyncio.wait_for upstream.
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
    drive_error: BaseException | None = None

    async def drive() -> None:
        nonlocal drive_error
        try:
            await asyncio.wait_for(
                generate_flow_events(
                    flow_id=flow_id,
                    background_tasks=background_tasks,
                    event_manager=event_manager,
                    inputs=input_request,
                    data=flow_data,
                    files=parsed.files,
                    stop_component_id=parsed.stop_component_id,
                    start_component_id=parsed.start_component_id,
                    # Persist vertex builds (keyed by ``run_id``) only for job-tracked
                    # runs so a background job's status can be reconstructed later. Live
                    # streams pass no ``run_id`` and keep the no-persist behavior.
                    log_builds=run_id is not None,
                    current_user=current_user,
                    flow_name=flow_name,
                    source_flow_id=source_flow_id,
                    run_id=run_id,
                    track_job_status=track_job_status,
                    # The sync path applies tweaks before Graph construction; this loop
                    # builds from the DB (or request data), so without this the streaming
                    # and background paths silently drop request tweaks.
                    tweaks=parsed.tweaks,
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

    seq = 0
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
            for event in adapter.translate(event_type, event_data):
                if terminal_error_type is not None and event.type == terminal_error_type:
                    terminal_error_seen = True
                yield _frame(event, seq)
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
            for event in adapter.error_events(drive_error):
                if terminal_error_type is not None and event.type == terminal_error_type:
                    terminal_error_seen = True
                yield _frame(event, seq)
                seq += 1
    finally:
        if not run_task.done():
            run_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await run_task
        await queue.aclose()


def _execute_streaming_workflow(
    *,
    adapter: StreamAdapter,
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
) -> WorkflowExecutionResponse:
    """Execute workflow with timeout protection.

    Args:
        parsed: The parsed AG-UI run parameters
        flow: The flow to execute
        job_id: Generated job ID for tracking
        current_user: Authenticated user
        background_tasks: FastAPI background tasks
        http_request: The HTTP request object for extracting headers

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
            ),
            timeout=_resolve_execution_timeout(),
        )
    except asyncio.TimeoutError as e:
        raise WorkflowTimeoutError from e


async def execute_sync_workflow(
    parsed: ParsedWorkflowRun,
    flow: FlowRead,
    job_id: UUID,
    current_user: UserRead,
    background_tasks: BackgroundTasks,  # noqa: ARG001
    http_request: Request,
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

    Returns:
        WorkflowExecutionResponse: Complete execution results with outputs and metadata

    Raises:
        WorkflowValidationError: If flow data is None or graph build fails
    """
    # Tweaks and chat input come straight from the parsed AG-UI request
    tweaks = parsed.tweaks
    session_id = parsed.session_id

    # Validate flow data - this is a system error, not execution error
    if flow.data is None:
        msg = f"Flow {flow.id} has no data. The flow may be corrupted."
        raise WorkflowValidationError(msg)

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
        # Use deepcopy to prevent mutation of the original flow.data
        # process_tweaks modifies nested dictionaries in-place
        graph_data = deepcopy(flow.data)
        graph_data = process_tweaks(graph_data, tweaks, stream=False)
        # Pass context to graph (similar to V1's simple_run_flow)
        # This allows components to access request metadata via graph.context
        graph = Graph.from_payload(
            graph_data, flow_id=flow_id_str, user_id=user_id, flow_name=flow.name, context=context
        )
        # Set run_id for tracing/logging (similar to V1's simple_run_flow)
        graph.set_run_id(job_id)
    except Exception as e:
        msg = f"Failed to build graph from flow data: {e!s}"
        raise WorkflowValidationError(msg) from e

    # Get terminal nodes - these are the outputs we want
    terminal_node_ids = graph.get_terminal_nodes()

    # Validate request-side output selection BEFORE executing: a bad id must cost
    # no compute. Raised outside the component-error try/except below, so it
    # surfaces as a real 422 rather than a 200-with-failed body.
    _validate_output_ids(parsed.output_ids, terminal_node_ids)

    # Execute graph - component errors are caught and returned in response body
    job_service = get_job_service()
    await job_service.create_job(job_id=job_id, flow_id=flow_id_str, user_id=current_user.id)
    try:
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

        # Fire memory-base auto-capture hook — non-blocking background effect.
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
        return run_response_to_workflow_response(
            run_response=run_response,
            flow_id=parsed.flow_id,
            job_id=str(job_id),
            inputs=parsed.tweaks,
            graph=graph,
            effective_globals=request_variables,
            selected_ids=parsed.output_ids,
        )

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
        return create_error_response(
            flow_id=parsed.flow_id,
            job_id=job_id,
            inputs=parsed.tweaks,
            error=exc,
            effective_globals=request_variables,
        )
