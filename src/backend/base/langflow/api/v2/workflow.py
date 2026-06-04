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
from langflow.services.deps import (
    get_background_execution_service,
    get_job_service,
    get_memory_base_service,
    get_task_service,
)
from langflow.services.jobs.exceptions import DuplicateJobError

# Configuration constants
EXECUTION_TIMEOUT = 300  # 5 minutes default timeout for sync execution

# Finished states a late /stop must not rewrite (CANCELLED is handled separately
# with its own idempotent early return).
_TERMINAL_JOB_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMED_OUT})


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


def _validate_output_ids(output_ids: list[str] | None, terminal_node_ids: list[str]) -> None:
    """Reject ``output_ids`` that aren't outputs of this flow, BEFORE it runs.

    Checks against the terminal node ids known after graph build but before
    execution, so a typo or wrong id costs no compute. ``available`` lists the
    flow's real output ids so callers can self-correct. None/empty means "no
    selection" and never raises.
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
            # Background runs are delegated to BackgroundExecutionService via
            # ``execute_workflow_background``. The facade creates the durable job
            # row, persists the request, enqueues the work, and owns ownership /
            # IDOR. The name-only check above already covered the 422 contract.
            return await execute_workflow_background(
                parsed=parsed,
                flow=flow,
                job_id=job_id,
                current_user=current_user,
                http_request=http_request,
                stream_protocol=request.stream_protocol,
                idempotency_key=request.idempotency_key,
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


# Inline stream queue between the build loop and the SSE consumer. Bounded
# so a slow consumer applies backpressure to the build loop instead of
# letting frames accumulate without bound when the network is slow.
_EVENT_QUEUE_MAX_SIZE = 256


def _default_frame_source_factory(*, request, flow_id, user, adapter, **_extra):
    """Bind the v1 build loop (``_stream_event_frames``) as the runner's source.

    Returns a zero-extra-kwargs async-generator callable so the runner can call
    it with ``**source_kwargs``. The flow row is re-fetched lazily inside the
    closure so ``submit()`` stays cheap and the build happens on the worker.

    The memory-base ``on_flow_output`` hook is fired on a clean run (no terminal
    error event) so background mode keeps the auto-capture wiring sync mode and
    the v1 build pipeline have; without it every background run would silently
    miss it.
    """
    parsed = parse_workflow_run_request(WorkflowRunRequest(**request))
    terminal_error_type = adapter.terminal_error_type

    async def _source(*, job_id=None, **_kwargs):
        flow = await get_flow_by_id_or_endpoint_name(str(flow_id), user.id, widen_for_shares=True)
        fresh_background_tasks = BackgroundTasks()
        errored = False
        try:
            async for frame, event_type in _stream_event_frames(
                adapter=adapter,
                flow_id=flow.id,
                flow_name=flow.name,
                background_tasks=fresh_background_tasks,
                parsed=parsed,
                current_user=user,
            ):
                if terminal_error_type is not None and event_type == terminal_error_type:
                    errored = True
                yield frame, event_type
        finally:
            # ``generate_flow_events`` queues telemetry / tracing teardown on
            # this ``BackgroundTasks``; the background path has no response to
            # carry them, so drain explicitly. Suppressed so one failing
            # callback cannot derail the run.
            with contextlib.suppress(Exception):
                await fresh_background_tasks()
            if not errored:
                try:
                    await get_task_service().fire_and_forget_task(
                        get_memory_base_service().on_flow_output,
                        flow_id=flow.id,
                        session_id=parsed.session_id or str(flow.id),
                        job_id=job_id,
                    )
                except (RuntimeError, ValueError, OSError):
                    await logger.awarning("Memory base hook scheduling failed for flow %s", flow.id, exc_info=True)

    return _source


async def execute_workflow_background(
    parsed: ParsedWorkflowRun,
    flow: FlowRead,
    job_id: JobId,  # noqa: ARG001
    current_user: UserRead,
    http_request: Request,  # noqa: ARG001
    stream_protocol: str,
    idempotency_key: str | None = None,
) -> WorkflowJobResponse:
    """Queue a background run through the BackgroundExecutionService facade.

    The facade owns job-row creation, durable event persistence, the live bus,
    and terminal-state finalization. We pass the original request fields so the
    runner re-parses them on the worker (the build happens off the request
    path) and replays durable milestones from ``job_events`` on re-attach.

    An optional ``idempotency_key`` dedupes submits: a retried POST with the
    same key returns the existing job_id rather than queuing duplicate work.
    """
    try:
        service = get_background_execution_service()
        if service._frame_source_factory is None:  # noqa: SLF001
            service._frame_source_factory = _default_frame_source_factory  # noqa: SLF001
        request_dict = {
            "flow_id": str(flow.id),
            "mode": "background",
            "stream_protocol": stream_protocol,
            "input_value": parsed.input_value,
            "session_id": parsed.session_id,
            "tweaks": parsed.tweaks,
            "globals": parsed.globals,
            "output_ids": parsed.output_ids,
            "data": parsed.data,
            "files": parsed.files,
            "start_component_id": parsed.start_component_id,
            "stop_component_id": parsed.stop_component_id,
            "idempotency_key": idempotency_key,
        }
        job_id_new = await service.submit(flow_id=flow.id, request=request_dict, user=current_user)
        return WorkflowJobResponse(job_id=str(job_id_new), flow_id=parsed.flow_id, status=JobStatus.QUEUED)

    except (WorkflowResourceError, WorkflowServiceUnavailableError, WorkflowQueueFullError):
        raise
    except MemoryError as exc:
        raise WorkflowResourceError from exc
    except DuplicateJobError as exc:
        # Defense-in-depth for the residual create/lookup race: a still-active
        # job already exists for this user's idempotency_key. Map to a 409 with a
        # generic body so the key is not echoed back (no existence leak) instead
        # of bubbling to the outer 500 handler.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Duplicate request",
                "code": "DUPLICATE_REQUEST",
                "message": "A job with this idempotency_key is already in progress.",
                "flow_id": parsed.flow_id,
            },
        ) from exc


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

            # Reconstruct response from vertex_build table (sync path persists
            # those keyed by job_id). Background runs do not write vertex_builds
            # keyed by job_id, so reconstruction finds nothing and raises
            # ValueError — fall back to the durable Job.result the runner wrote
            # so a completed background run reports completed instead of 500ing.
            try:
                return await reconstruct_workflow_response_from_job_id(
                    session=session,
                    flow=flow,
                    job_id=job_id_str,
                    user_id=str(current_user.id),
                )
            except ValueError:
                return WorkflowExecutionResponse(
                    flow_id=flow_id_str,
                    job_id=job_id_str,
                    status=JobStatus.COMPLETED,
                )

        if job.status == JobStatus.FAILED:
            # Surface the durable error JSON the runner persisted, additively.
            # The error column is nullable (a crash before the runner could write
            # one leaves it None); the static detail still applies in that case.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Job failed",
                    "code": "JOB_FAILED",
                    "message": f"Job {job_id_str} has failed execution.",
                    "job_id": job_id_str,
                    "error_detail": job.error,
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
    # A late stop on a job that already finished must not rewrite its terminal
    # status: flipping a COMPLETED/FAILED/TIMED_OUT row to CANCELLED would strand
    # the result/error blob the run already wrote. Report the existing state.
    if job.status in _TERMINAL_JOB_STATUSES:
        return WorkflowStopResponse(job_id=str(job_id), message=f"Job {job_id} already finished ({job.status.value}).")

    try:
        revoked = await task_service.revoke_task(job_id)
        # Write the durable STOP signal + cancel the in-flight executor task
        # BEFORE flipping the row to CANCELLED. The signal is the marker the
        # runner's terminal reconcile keys off, so persisting it first means an
        # in-flight runner racing to a terminal state reliably observes the stop
        # and finalizes CANCELLED rather than overwriting it with COMPLETED/FAILED.
        with contextlib.suppress(Exception):
            await get_background_execution_service().stop_job(job_id, current_user)
        await job_service.update_job_status(job_id, JobStatus.CANCELLED)

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
    description="Replay durable events for a background run from Last-Event-ID and tail until it ends.",
)
async def reattach_workflow_events(
    job_id: str,
    http_request: Request,
    current_user: Annotated[UserRead, Depends(get_current_user_for_workflow)],
) -> EventSourceResponse:
    """Re-attach to a background run.

    Replays durable milestones from the ``job_events`` log (after
    ``Last-Event-ID``) then tails the live bus until the run ends.

    Ownership is enforced by the facade; a cross-user or unknown job maps to a
    404 to avoid leaking the existence of other users' runs. The pre-check runs
    before streaming starts so the error body is a clean JSON 404 rather than a
    half-open SSE stream.
    """
    service = get_background_execution_service()
    last_event_id = http_request.headers.get("Last-Event-ID")

    try:
        # Pre-validate ownership/existence so a deny surfaces as a 404 before
        # the SSE stream opens. ``events`` re-validates as defense-in-depth.
        await service.status(UUID(job_id), current_user)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Background run not found",
                "code": "JOB_NOT_FOUND",
                "message": f"No background run for job {job_id}.",
                "job_id": job_id,
            },
        ) from exc

    return EventSourceResponse(
        service.events(UUID(job_id), last_event_id=last_event_id, user=current_user),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
