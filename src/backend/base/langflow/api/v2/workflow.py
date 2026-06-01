"""V2 Workflow execution endpoints.

This module implements the V2 Workflow API endpoints for executing flows with
enhanced error handling, timeout protection, and structured responses.

Endpoints:
    POST /workflow: Execute a workflow (sync, stream, or background modes)
    GET /workflow: Get workflow job status by job_id
    POST /workflow/stop: Stop a running workflow execution

Features:
    - Comprehensive error handling with structured error responses
    - Timeout protection for long-running executions
    - Support for multiple execution modes (sync, stream, background)
    - Session-cookie or API-key authentication

Configuration:
    EXECUTION_TIMEOUT: Maximum execution time for synchronous workflows (300 seconds)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Annotated
from uuid import UUID, uuid4

from ag_ui.core import CustomEvent
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import EventSourceResponse, StreamingResponse
from fastapi.sse import format_sse_event
from lfx.events.event_manager import create_default_event_manager
from lfx.graph.graph.base import Graph
from lfx.log.logger import logger
from lfx.schema.schema import InputValueRequest
from lfx.schema.workflow import (
    WORKFLOW_EXECUTION_RESPONSES,
    WORKFLOW_STATUS_RESPONSES,
    JobId,
    JobStatus,
    WorkflowExecutionResponse,
    WorkflowJobResponse,
    WorkflowRunRequest,
    WorkflowStopRequest,
    WorkflowStopResponse,
)
from lfx.services.deps import injectable_session_scope_readonly
from pydantic_core import ValidationError as PydanticValidationError
from sqlalchemy.exc import OperationalError

from langflow.api.build import generate_flow_events
from langflow.api.utils import extract_global_variables_from_headers
from langflow.api.v1.schemas import FlowDataRequest, RunResponse
from langflow.api.v2.adapters import (
    STREAM_ADAPTERS,
    StreamAdapter,
    StreamAdapterContext,
    StreamEvent,
    UnknownStreamProtocolError,
    available_protocols,
    get_stream_adapter,
)
from langflow.api.v2.converters import (
    ParsedWorkflowRun,
    create_error_response,
    parse_workflow_run_request,
    run_response_to_workflow_response,
)
from langflow.api.v2.workflow_reconstruction import reconstruct_workflow_response_from_job_id
from langflow.exceptions.api import (
    WorkflowQueueFullError,
    WorkflowResourceError,
    WorkflowServiceUnavailableError,
    WorkflowTimeoutError,
    WorkflowValidationError,
)
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.services.auth.utils import get_current_user_for_workflow
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.jobs.model import JobType
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_job_service, get_memory_base_service, get_queue_service, get_task_service

# Configuration constants
EXECUTION_TIMEOUT = 300  # 5 minutes default timeout for sync execution


router = APIRouter(prefix="/workflows", tags=["Workflow"])


def _unknown_protocol_http_exception(exc: UnknownStreamProtocolError) -> HTTPException:
    """Build the 422 response shared by ``stream`` and ``background`` paths.

    Both branches validate ``stream_protocol`` against the live adapter registry
    so the error body is identical: callers can switch ``mode`` without
    learning a second error shape. ``available`` lists the registered protocol
    names so clients can self-correct.
    """
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "Unknown stream_protocol",
            "code": "UNKNOWN_STREAM_PROTOCOL",
            "message": f"Unknown stream_protocol {exc.name!r}.",
            "available": exc.available,
        },
    )


def _build_run_inputs(parsed: ParsedWorkflowRun) -> list[InputValueRequest] | None:
    """Build the graph input list from the AG-UI chat message, if any.

    The last user message becomes a single chat input; an empty message means
    the flow runs with no chat input (parameters arrive via tweaks instead).
    """
    if not parsed.input_value:
        return None
    return [InputValueRequest(components=[], input_value=parsed.input_value, type="chat")]


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


@router.post(
    "",
    response_model=None,
    response_model_exclude_none=True,
    responses=WORKFLOW_EXECUTION_RESPONSES,
    summary="Execute Workflow",
    description="Execute a workflow with support for sync, stream, and background modes",
)
async def execute_workflow(
    request: WorkflowRunRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    current_user: Annotated[UserRead, Depends(get_current_user_for_workflow)],
) -> WorkflowExecutionResponse | WorkflowJobResponse | StreamingResponse:
    """Execute a flow from a native ``WorkflowRunRequest`` body.

    ``mode`` selects the execution path:
        - **sync** (default): run inline, return ``WorkflowExecutionResponse``.
        - **stream**: return an SSE stream in the protocol named by
          ``stream_protocol`` (``langflow`` default, ``agui`` opt-in).
        - **background**: queue a job, return ``WorkflowJobResponse`` with a
          ``links.events`` URL for re-attach.

    Error Handling:
        - System errors (404, 500, 503, 504): HTTP error responses.
        - Component execution errors: HTTP 200 with errors in the body.
        - Unknown ``stream_protocol``: 422 with the available list.

    Raises:
        HTTPException:
            - 404: Flow not found or user lacks access.
            - 400: Invalid flow data or validation error.
            - 422: Unknown ``stream_protocol``.
            - 500: Internal server error.
            - 503: Database unavailable.
            - 408: Execution timeout exceeded.
    """
    parsed = parse_workflow_run_request(request)
    job_id = uuid4()

    # Validate ``stream_protocol`` for every mode, even ``sync``: the field is
    # part of the request contract regardless of which path runs. A name-only
    # membership check here avoids instantiating an adapter the sync path will
    # never use.
    if request.stream_protocol not in STREAM_ADAPTERS:
        raise _unknown_protocol_http_exception(
            UnknownStreamProtocolError(request.stream_protocol, available_protocols())
        )

    try:
        # Share-aware fetch + RBAC: resolve the flow and enforce flow:execute.
        # The lookup widens to shared flows when an authorization plugin is
        # registered, so we enforce the action explicitly — otherwise an API
        # key with cross-user fetch enabled would bypass policy here.
        flow = await get_flow_by_id_or_endpoint_name(
            parsed.flow_id,
            current_user.id,
            widen_for_shares=True,
        )
        await ensure_flow_permission(
            current_user,
            FlowAction.EXECUTE,
            flow_id=flow.id,
            flow_user_id=flow.user_id,
            workspace_id=getattr(flow, "workspace_id", None),
            folder_id=getattr(flow, "folder_id", None),
        )

        if parsed.mode == "sync":
            return await execute_sync_workflow_with_timeout(
                parsed=parsed,
                flow=flow,
                job_id=job_id,
                current_user=current_user,
                background_tasks=background_tasks,
                http_request=http_request,
            )

        if parsed.mode == "background":
            # Background owns its own adapter construction inside
            # ``_buffer_background_run`` because the fire-and-forget coroutine
            # needs its own ``StreamAdapterContext`` (different ``run_id``).
            # The name-only check above already covered the 422 contract.
            return await execute_workflow_background(
                parsed=parsed,
                flow=flow,
                job_id=job_id,
                current_user=current_user,
                http_request=http_request,
                stream_protocol=request.stream_protocol,
            )

        # Stream mode: the adapter instance drives the SSE frame loop, so we
        # construct it here. ``get_stream_adapter`` can no longer raise
        # ``UnknownStreamProtocolError`` on this path unless the registry
        # mutates mid-request.
        adapter = get_stream_adapter(
            request.stream_protocol,
            StreamAdapterContext(
                run_id=str(job_id),
                thread_id=parsed.session_id or str(flow.id),
            ),
        )
        return _execute_streaming_workflow(
            adapter=adapter,
            parsed=parsed,
            flow=flow,
            current_user=current_user,
            background_tasks=background_tasks,
        )

    except HTTPException as e:
        # Reformat 404 from get_flow_by_id_or_endpoint_name to structured format
        if e.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Flow not found",
                    "code": "FLOW_NOT_FOUND",
                    "message": f"Flow '{parsed.flow_id}' does not exist. Verify the flow_id and try again.",
                    "flow_id": parsed.flow_id,
                },
            ) from e
        raise
    except OperationalError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable, Please try again.",
                "code": "DATABASE_ERROR",
                "message": f"Failed to fetch flow: {e!s}",
                "flow_id": parsed.flow_id,
            },
        ) from e
    except WorkflowTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail={
                "error": "Execution timeout",
                "code": "EXECUTION_TIMEOUT",
                "message": f"Workflow execution exceeded {EXECUTION_TIMEOUT} seconds",
                "job_id": str(job_id),
                "flow_id": str(parsed.flow_id),
                "timeout_seconds": EXECUTION_TIMEOUT,
            },
        ) from None
    except (PydanticValidationError, WorkflowValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Workflow validation error",
                "code": "INVALID_FLOW_DATA",
                "message": str(e),
                "flow_id": parsed.flow_id,
            },
        ) from e
    except WorkflowServiceUnavailableError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable",
                "code": "QUEUE_SERVICE_UNAVAILABLE",
                "message": str(err),
                "flow_id": parsed.flow_id,
            },
        ) from err
    except (WorkflowResourceError, WorkflowQueueFullError, MemoryError) as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service busy",
                "code": "SERVICE_BUSY",
                "message": "The service is currently unable to handle the request due to resource limits.",
                "flow_id": parsed.flow_id,
            },
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"An unexpected error occurred: {err!s}",
                "flow_id": parsed.flow_id,
            },
        ) from err


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
            timeout=EXECUTION_TIMEOUT,
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


async def _stream_event_frames(
    *,
    adapter: StreamAdapter,
    flow_id: UUID,
    flow_name: str | None,
    background_tasks: BackgroundTasks,
    parsed: ParsedWorkflowRun,
    current_user: UserRead,
    source_flow_id: UUID | None = None,
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
    # Bounded so a slow consumer can apply backpressure on the build loop
    # instead of growing without bound. The build loop awaits ``queue.put``
    # which yields control back to the consumer between frames.
    queue: asyncio.Queue = asyncio.Queue(maxsize=_EVENT_QUEUE_MAX_SIZE)
    event_manager = create_default_event_manager(queue)
    input_request = _single_input_value_request(parsed)
    flow_data = FlowDataRequest(**parsed.data) if parsed.data else None

    # Captured from drive()'s exception path so the consumer can yield a
    # guaranteed adapter.error_events(...) fallback after the queue loop ends.
    # Layered error handling, by design:
    #   1. ``event_manager.on_error(...)`` is the cooperative path: the
    #      translator turns it into the protocol's terminal-error event (e.g.
    #      RUN_ERROR for AG-UI, ``error`` for langflow) so the buffer's
    #      structural detector flips the job to FAILED.
    #   2. ``adapter.error_events(exc)`` is the dispatcher's guaranteed
    #      fallback: emitted from the consumer side even when on_error itself
    #      raises (its body and the sentinel-put are wrapped in suppress so
    #      they cannot prevent shutdown but can fail silently). Without this
    #      yield, an on_error failure would leave the stream with no terminal
    #      error event at all and the buffer would mark the job COMPLETED.
    #   3. The buffer task's ``terminal_error_type`` check fires on either
    #      RUN_ERROR source, so a single drive() failure cannot result in a
    #      job marked COMPLETED.
    drive_error: BaseException | None = None

    async def drive() -> None:
        nonlocal drive_error
        try:
            await generate_flow_events(
                flow_id=flow_id,
                background_tasks=background_tasks,
                event_manager=event_manager,
                inputs=input_request,
                data=flow_data,
                files=parsed.files,
                stop_component_id=parsed.stop_component_id,
                start_component_id=parsed.start_component_id,
                log_builds=False,
                current_user=current_user,
                flow_name=flow_name,
                source_flow_id=source_flow_id,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            drive_error = exc
            with contextlib.suppress(Exception):
                event_manager.on_error(data={"error": str(exc)})
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
    side_channel_events = frozenset({"add_message", "token", "remove_message", "error"})

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
                yield _frame(event, seq)
                seq += 1
        for event in adapter.final_events():
            yield _frame(event, seq)
            seq += 1
        # Guaranteed-fallback layer (see drive_error block above). If drive()
        # captured an exception, emit the adapter's terminal error event(s)
        # here even if on_error already produced one: an extra RUN_ERROR is
        # cheap and only a hard error path will hit this. The duplicate is
        # the cost of guaranteeing the consumer sees a terminal error event
        # even when the cooperative on_error layer failed.
        if drive_error is not None:
            for event in adapter.error_events(drive_error):
                yield _frame(event, seq)
                seq += 1
    finally:
        if not run_task.done():
            run_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await run_task


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


class _BackgroundRun:
    """In-memory buffer of a background run's protocol-native SSE frames for re-attach.

    The buffer lives in the process; restarts drop it. Multiple readers can
    re-attach concurrently and tail until the run ends. The frames are
    already serialized in the protocol the original POST requested via
    ``stream_protocol``; re-attach replays them as-is. Mixing protocols
    across a single run is not supported.

    Per-run frame count is bounded by ``_MAX_FRAMES_PER_BACKGROUND_RUN`` so a
    long verbose run (token-by-token streams, repeated tool calls) cannot
    exhaust process memory while ``_MAX_BACKGROUND_RUNS`` only caps the
    number of buffers. When the cap is reached the oldest frames are
    evicted; re-attach with ``Last-Event-ID`` past that point will start
    from the new buffer head (replay loss is preferred over OOM).
    """

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.frames: list[bytes] = []
        # Index of the first frame still in ``frames`` (monotonic across the
        # life of the buffer). Once eviction starts, ``frames[i]`` corresponds
        # to logical event id ``base_index + i``.
        self.base_index = 0
        self.done = False
        self._cond = asyncio.Condition()

    async def append(self, frame: bytes) -> None:
        async with self._cond:
            self.frames.append(frame)
            overflow = len(self.frames) - _MAX_FRAMES_PER_BACKGROUND_RUN
            if overflow > 0:
                del self.frames[:overflow]
                self.base_index += overflow
            self._cond.notify_all()

    async def finish(self) -> None:
        async with self._cond:
            self.done = True
            self._cond.notify_all()

    async def replay(self, start_index: int) -> AsyncIterator[bytes]:
        """Yield buffered frames from ``start_index`` and tail until done.

        ``start_index`` is in logical event-id space (matches what was emitted
        on ``id:`` lines). If the caller's ``Last-Event-ID`` points before the
        buffer's current head (frames evicted under memory pressure), we
        replay from the head and the caller observes a gap.
        """
        idx = max(start_index, 0)
        while True:
            async with self._cond:
                head = self.base_index
                tail = head + len(self.frames)
                idx = max(idx, head)
                while idx >= tail and not self.done:
                    await self._cond.wait()
                    head = self.base_index
                    tail = head + len(self.frames)
                    idx = max(idx, head)
                snapshot = self.frames[idx - head :]
                finished = self.done
            for frame in snapshot:
                yield frame
            idx += len(snapshot)
            if finished and idx >= self.base_index + len(self.frames):
                return


# Process-local registry of background runs keyed by job_id, bounded by
# ``_MAX_BACKGROUND_RUNS`` (oldest evicted first). Re-attach reads this.
_MAX_BACKGROUND_RUNS = 100
# Per-run frame ceiling. Caps memory for a single long/verbose run so a
# token-streaming flow can't exhaust the process. 10k frames covers minutes
# of dense token streams with room to spare; beyond that we evict oldest.
_MAX_FRAMES_PER_BACKGROUND_RUN = 10_000
# Inline stream queue between the build loop and the SSE consumer. Bounded
# so a slow consumer applies backpressure to the build loop instead of
# letting frames accumulate without bound when the network is slow.
_EVENT_QUEUE_MAX_SIZE = 256
_BACKGROUND_RUNS: dict[str, _BackgroundRun] = {}


async def _finalize_job_status(job_uuid: UUID, terminal_status: JobStatus) -> None:
    """Update job status to a terminal value, but never overwrite CANCELLED.

    ``stop_workflow`` sets the job to CANCELLED. The buffer task runs in
    parallel and reaches its ``finally`` block shortly after; if it
    unconditionally wrote COMPLETED/FAILED it would race with the cancellation
    and silently overwrite the user's stop intent. Re-read the row first and
    skip the update if a cancellation already landed.
    """
    job_service = get_job_service()
    try:
        job = await job_service.get_job_by_job_id(job_id=job_uuid)
    except Exception:  # noqa: BLE001
        job = None
    if job is not None and job.status == JobStatus.CANCELLED:
        return
    with contextlib.suppress(Exception):
        await job_service.update_job_status(
            job_uuid,
            terminal_status,
            finished_timestamp=True,
        )


async def _clear_background_run(job_id: str) -> None:
    """Pop the background run registry entry and wake any re-attach waiters.

    Called from ``stop_workflow`` after revoking the buffer task. Without
    this, ``_cond.wait()`` inside ``_BackgroundRun.replay`` can hang
    indefinitely (the buffer is never marked done because the task that
    would have called ``finish()`` was cancelled mid-execution), and the
    cancelled ``_BackgroundRun`` lingers in memory until LRU evicts it.
    """
    bg_run = _BACKGROUND_RUNS.pop(job_id, None)
    if bg_run is not None:
        await bg_run.finish()


def _register_background_run(job_id: str, bg_run: _BackgroundRun) -> None:
    """Register a background run, evicting a completed entry when full.

    Prefer evicting the oldest *completed* run so a long-running job's
    re-attach handle survives. If every slot is still active, evict the
    oldest one anyway to keep the registry bounded, and log a warning.
    """
    if len(_BACKGROUND_RUNS) >= _MAX_BACKGROUND_RUNS:
        evict_key = next(
            (key for key, run in _BACKGROUND_RUNS.items() if run.done),
            None,
        )
        if evict_key is None:
            evict_key = next(iter(_BACKGROUND_RUNS))
            logger.warning(
                "Background run registry full with no completed entries; "
                "evicting still-running job %s to make room for %s",
                evict_key,
                job_id,
            )
        _BACKGROUND_RUNS.pop(evict_key, None)
    _BACKGROUND_RUNS[job_id] = bg_run


async def _buffer_background_run(
    *,
    bg_run: _BackgroundRun,
    flow: FlowRead,
    parsed: ParsedWorkflowRun,
    job_id: str,
    current_user: UserRead,
    stream_protocol: str,
) -> None:
    """Run a background flow, buffer its frames, and finalize job status.

    The adapter is resolved from ``stream_protocol`` so re-attach replays
    frames in the protocol the caller requested. Validation of
    ``stream_protocol`` happens at the route handler; this function still
    guards against ``UnknownStreamProtocolError`` because it runs as a
    fire-and-forget background coroutine. If adapter registration breaks
    between the route's check and this call (e.g. a registry mutation), we
    flip the job to FAILED and exit cleanly rather than dying silently and
    leaving the job stuck at QUEUED.

    The buffer's terminal-status detection keys off
    ``adapter.terminal_error_type``.
    """
    try:
        adapter = get_stream_adapter(
            stream_protocol,
            StreamAdapterContext(
                run_id=parsed.run_id or job_id,
                thread_id=parsed.session_id or str(flow.id),
            ),
        )
    except UnknownStreamProtocolError:
        # Fire-and-forget coroutine: do not raise, the route already returned.
        await bg_run.finish()
        job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
        await _finalize_job_status(job_uuid, JobStatus.FAILED)
        return

    terminal_error_type = adapter.terminal_error_type
    fresh_background_tasks = BackgroundTasks()
    errored = False
    try:
        async for frame, event_type in _stream_event_frames(
            adapter=adapter,
            flow_id=flow.id,
            flow_name=flow.name,
            background_tasks=fresh_background_tasks,
            parsed=parsed,
            current_user=current_user,
        ):
            if terminal_error_type is not None and event_type == terminal_error_type:
                errored = True
            await bg_run.append(frame)
    finally:
        await bg_run.finish()
        # ``generate_flow_events`` queues telemetry, tracing teardown, and
        # other callbacks on this ``BackgroundTasks`` instance. In FastAPI's
        # request lifecycle those run after the response is sent; the
        # background path has no response carrying them, so drain the queue
        # explicitly. Suppressed so a single failing telemetry callback does
        # not derail job-status finalization.
        with contextlib.suppress(Exception):
            await fresh_background_tasks()
        # ``update_job_status`` queries the Job table by its UUID primary key;
        # passing the raw string would silently miss every row.
        job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
        await _finalize_job_status(job_uuid, JobStatus.FAILED if errored else JobStatus.COMPLETED)
        # Fire memory-base auto-capture hook on successful runs only. Matches
        # the sync mode wiring above and the v1 build-pipeline wiring in
        # ``api/build.py``. ``fire_and_forget_task`` because we are already a
        # background coroutine and the hook must not block job finalization.
        if not errored:
            try:
                await get_task_service().fire_and_forget_task(
                    get_memory_base_service().on_flow_output,
                    flow_id=flow.id,
                    session_id=parsed.session_id or str(flow.id),
                    job_id=job_uuid,
                )
            except (RuntimeError, ValueError, OSError):
                await logger.awarning("Memory base hook scheduling failed for flow %s", flow.id, exc_info=True)


async def execute_workflow_background(
    parsed: ParsedWorkflowRun,
    flow: FlowRead,
    job_id: JobId,
    current_user: UserRead,
    http_request: Request,  # noqa: ARG001
    stream_protocol: str,
) -> WorkflowJobResponse:
    """Run a workflow in the background, buffering protocol-native events for re-attach.

    A job row is created so ``GET /workflows`` and ``POST /workflows/stop`` keep
    working. The buffer task is scheduled through the queue service under
    ``job_id`` so ``/stop`` can revoke it. Graph construction happens inside
    the v1 build-vertex loop driven by ``_stream_event_frames`` with the
    adapter selected by ``stream_protocol``; re-attach replays the frames in
    that same protocol's wire shape.
    """
    try:
        flow_id_str = str(flow.id)
        job_id_str = str(job_id)

        await get_job_service().create_job(
            job_id=job_id,
            flow_id=flow_id_str,
            user_id=current_user.id,
        )

        bg_run = _BackgroundRun(user_id=str(current_user.id))
        _register_background_run(job_id_str, bg_run)

        try:
            queue_service = get_queue_service()
            queue_service.create_queue(job_id_str)
            queue_service.start_job(
                job_id_str,
                _buffer_background_run(
                    bg_run=bg_run,
                    flow=flow,
                    parsed=parsed,
                    job_id=job_id_str,
                    current_user=current_user,
                    stream_protocol=stream_protocol,
                ),
            )
        except BaseException:
            # If queue creation or scheduling fails after the bg_run is
            # registered, the buffer would stay live with ``done=False`` and
            # any re-attach client would block on ``_cond.wait()`` forever
            # (the task that would call ``finish()`` was never scheduled).
            # Clear the registry, mark the job FAILED, then re-raise.
            await _clear_background_run(job_id_str)
            await _finalize_job_status(job_id, JobStatus.FAILED)
            raise
        return WorkflowJobResponse(job_id=job_id_str, flow_id=parsed.flow_id, status=JobStatus.QUEUED)

    except (WorkflowResourceError, WorkflowServiceUnavailableError, WorkflowQueueFullError):
        raise
    except MemoryError as exc:
        raise WorkflowResourceError from exc


@router.get(
    "",
    response_model=None,
    response_model_exclude_none=True,
    responses=WORKFLOW_STATUS_RESPONSES,
    summary="Get Workflow Status",
    description="Get status of workflow job by job ID",
)
async def get_workflow_status(
    current_user: Annotated[UserRead, Depends(get_current_user_for_workflow)],
    job_id: Annotated[JobId | None, Query(description="Job ID to query")] = None,
    session: Annotated[object, Depends(injectable_session_scope_readonly)] = None,
) -> WorkflowExecutionResponse | WorkflowJobResponse:
    """Get workflow job status and results.

    Args:
        current_user: Authenticated user (session cookie or API key)
        job_id: Optional job ID to query specific job
        session: Database session for querying vertex builds

    Returns:
        WorkflowExecutionResponse or reconstructed results

    Raises:
        HTTPException:
            - 400: Job ID not provided
            - 403: Developer API disabled or unauthorized
            - 404: Job not found
            - 408: Execution timeout
            - 500: Internal server error or Job failure
    """
    if not job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Missing required parameter",
                "code": "MISSING_PARAMETER",
                "message": "Job ID must be provided",
            },
        )

    job_service = get_job_service()
    try:
        job = await job_service.get_job_by_job_id(job_id=job_id, user_id=current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"Failed to retrieve job from database: {exc!s}",
            },
        ) from exc

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Workflow job not found",
                "code": "JOB_NOT_FOUND",
                "message": f"Workflow job {job_id} not found",
                "job_id": str(job_id),
            },
        )

    # Verify this is a workflow job
    if job.type != JobType.WORKFLOW:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Workflow job not found",
                "code": "JOB_NOT_FOUND",
                "message": f"Job {job_id} is not a workflow job (type: {job.type})",
                "job_id": str(job_id),
            },
        )

    # Store context for exception handling scope
    flow_id_str = str(job.flow_id)
    job_id_str = str(job_id)
    try:
        # If job is completed, reconstruct full workflow response from vertex_builds
        if job.status == JobStatus.COMPLETED:
            # Share-aware fetch + RBAC: enforce flow:read so an API key with
            # cross-user fetch cannot read another user's job output.
            flow = await get_flow_by_id_or_endpoint_name(
                flow_id_str,
                current_user.id,
                widen_for_shares=True,
            )
            await ensure_flow_permission(
                current_user,
                FlowAction.READ,
                flow_id=flow.id,
                flow_user_id=flow.user_id,
                workspace_id=getattr(flow, "workspace_id", None),
                folder_id=getattr(flow, "folder_id", None),
            )

            # Reconstruct response from vertex_build table
            return await reconstruct_workflow_response_from_job_id(
                session=session,
                flow=flow,
                job_id=job_id_str,
                user_id=str(current_user.id),
            )

        if job.status == JobStatus.FAILED:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Job failed",
                    "code": "JOB_FAILED",
                    "message": f"Job {job_id_str} has failed execution.",
                    "job_id": job_id_str,
                },
            )

        if job.status == JobStatus.TIMED_OUT:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail={
                    "error": "Execution timeout",
                    "code": "EXECUTION_TIMEOUT",
                    "message": "Workflow execution timed out",
                    "job_id": job_id_str,
                    "flow_id": flow_id_str,
                },
            )

        # Default response for active statuses (QUEUED, IN_PROGRESS, etc.)
        return WorkflowJobResponse(
            flow_id=flow_id_str,
            job_id=job_id_str,
            status=job.status,
        )

    except HTTPException:
        raise
    except WorkflowTimeoutError as err:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail={
                "error": "Execution timeout",
                "code": "EXECUTION_TIMEOUT",
                "message": f"Workflow execution exceeded {EXECUTION_TIMEOUT} seconds",
                "job_id": job_id_str,
                "flow_id": flow_id_str,
                "timeout_seconds": EXECUTION_TIMEOUT,
            },
        ) from err
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"Failed to process job status: {exc!s}",
            },
        ) from exc


@router.post(
    "/stop",
    summary="Stop Workflow",
    description="Stop a running workflow execution",
)
async def stop_workflow(
    request: WorkflowStopRequest,
    current_user: Annotated[UserRead, Depends(get_current_user_for_workflow)],
) -> WorkflowStopResponse:
    """Stop a running workflow execution by job_id.

    This endpoint allows clients to gracefully or forcefully stop a running workflow.

    Args:
        request: Stop request containing job_id and optional force flag
        current_user: Authenticated user (session cookie or API key)

    Returns:
        WorkflowStopResponse: Confirmation of stop request with final job status

    Raises:
        HTTPException:
            - 403: Developer API disabled or unauthorized
            - 404: Job ID not found
            - 500: Internal server error
    """
    job_id = request.job_id
    job_service = get_job_service()
    task_service = get_task_service()

    try:
        # 1. Fetch Job
        job = await job_service.get_job_by_job_id(job_id, user_id=current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"Failed to retrieve job status: {exc!s}",
            },
        ) from exc

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Job not found",
                "code": "JOB_NOT_FOUND",
                "message": f"Job {job_id} not found",
                "job_id": str(job_id),
            },
        )

    # Verify this is a workflow job
    if job.type != JobType.WORKFLOW:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Job not found",
                "code": "JOB_NOT_FOUND",
                "message": f"Job {job_id} is not a workflow job (type: {job.type})",
                "job_id": str(job_id),
            },
        )

    if job.status == JobStatus.CANCELLED:
        return WorkflowStopResponse(job_id=str(job_id), message=f"Job {job_id} is already cancelled.")

    try:
        revoked = await task_service.revoke_task(job_id)
        await job_service.update_job_status(job_id, JobStatus.CANCELLED)
        # Release the in-memory buffer and wake any re-attach waiters so they
        # see a clean stream-end instead of hanging on ``_cond.wait()``.
        await _clear_background_run(str(job_id))

        message = f"Job {job_id} cancelled successfully." if revoked else f"Job {job_id} is already cancelled."
        return WorkflowStopResponse(job_id=str(job_id), message=message)
    except asyncio.CancelledError as exc:
        # Handle system-initiated cancellations that were re-raised
        # The job status has already been updated to FAILED in jobs/service.py
        message_code = exc.args[0] if exc.args else "UNKNOWN"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Task cancellation error",
                "code": message_code,
                "message": f"Job {job_id} was cancelled unexpectedly by the system",
                "job_id": str(job_id),
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"Failed to stop job: {job_id} - {exc!s}",
            },
        ) from exc


@router.get(
    "/{job_id}/events",
    response_model=None,
    summary="Re-attach to a background run",
    description="Replay the buffered protocol-native events for a background run and tail until it ends.",
)
async def reattach_workflow_events(
    job_id: str,
    http_request: Request,
    current_user: Annotated[UserRead, Depends(get_current_user_for_workflow)],
) -> EventSourceResponse:
    """Stream a background run's buffered events, replaying from ``Last-Event-ID``.

    The buffer is process-local and frames are already serialized in the
    protocol the original POST requested via ``stream_protocol``; this handler
    replays them as-is. Cross-user access is rejected with 404 to avoid
    leaking the existence of other users' runs.
    """
    bg_run = _BACKGROUND_RUNS.get(job_id)
    if bg_run is None or bg_run.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Background run not found",
                "code": "JOB_NOT_FOUND",
                "message": f"No buffered events for job {job_id}.",
                "job_id": job_id,
            },
        )

    last_event_id = http_request.headers.get("Last-Event-ID")
    start_index = 0
    if last_event_id:
        try:
            start_index = int(last_event_id) + 1
        except ValueError:
            start_index = 0

    return EventSourceResponse(
        bg_run.replay(start_index),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
