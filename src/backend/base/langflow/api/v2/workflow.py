"""V2 Workflow execution endpoints.

This module implements the V2 Workflow API route handlers for executing flows
with enhanced error handling, timeout protection, and structured responses.
The execution machinery itself lives in sibling modules:

    - ``workflow_validation``: request/permission guards.
    - ``workflow_execution``: sync + streaming run-driving.
    - ``workflow_background``: durable, re-attachable background runs.

Endpoints:
    POST /workflows: Execute a workflow (sync, stream, or background modes)
    GET /workflows: Get workflow job status by job_id
    POST /workflows/stop: Stop a running workflow execution
    GET /workflows/{job_id}/events: Re-attach to a background run's event stream

Features:
    - Comprehensive error handling with structured error responses
    - Timeout protection for long-running executions
    - Support for multiple execution modes (sync, stream, background)
    - Session-cookie or API-key authentication
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import EventSourceResponse, StreamingResponse
from lfx.log.logger import logger
from lfx.schema.workflow import (
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
from lfx.workflow.actions import WorkflowAction
from lfx.workflow.adapters import (
    STREAM_ADAPTERS,
    StreamAdapterContext,
    UnknownStreamProtocolError,
    available_protocols,
    get_stream_adapter,
)
from lfx.workflow.converters import parse_workflow_run_request
from pydantic_core import ValidationError as PydanticValidationError
from sqlalchemy.exc import OperationalError

from langflow.api.v2.workflow_background import (
    _BACKGROUND_RUNS,
    _cancel_workflow_queue_job,
    _finish_cancelled_background_run,
    execute_workflow_background,
)
from langflow.api.v2.workflow_execution import (
    _execute_streaming_workflow,
    _resolve_execution_timeout,
    execute_sync_workflow_with_timeout,
)
from langflow.api.v2.workflow_reconstruction import reconstruct_workflow_response_from_job_id
from langflow.api.v2.workflow_validation import (
    _enforce_flow_data_override_owner,
    _flow_not_found_privacy_exception,
    _reject_unsupported_sync_fields,
    _validate_flow_data_for_execution,
)
from langflow.exceptions.api import (
    WorkflowQueueFullError,
    WorkflowResourceError,
    WorkflowServiceUnavailableError,
    WorkflowTimeoutError,
    WorkflowValidationError,
)
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.services.auth.utils import get_current_user_for_workflow
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.database.models.jobs.model import JobType
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_job_service

# The langflow durable background routes (GET status, POST /stop, GET
# /{job_id}/events). The POST run path is contributed by the shared lfx router
# (``lfx.workflow.router.create_workflow_router``) bound to ``LangflowWorkflowHost``;
# only these durable, behaviorally-rich routes stay langflow-owned. Both are
# mounted on the same ``/workflows`` prefix in ``langflow.api.router``.
router = APIRouter(prefix="/workflows", tags=["Workflow"])


def _flow_not_found_http_exception(flow_id: str) -> HTTPException:
    """The structured 404 returned when a flow does not exist."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "Flow not found",
            "code": "FLOW_NOT_FOUND",
            "message": f"Flow '{flow_id}' does not exist. Verify the flow_id and try again.",
            "flow_id": flow_id,
        },
    )


async def resolve_flow_for_execution(flow_id: str, current_user: UserRead):
    """Share-aware fetch with the langflow error-to-HTTP mapping.

    The lookup widens to shared flows when an authorization plugin is
    registered; ``authorize_flow_action`` enforces the action separately so an
    API key with cross-user fetch enabled cannot bypass policy. A missing flow
    becomes 404 FLOW_NOT_FOUND, a DB failure 503 DATABASE_ERROR, and anything
    unexpected a sanitized 500.
    """
    try:
        return await get_flow_by_id_or_endpoint_name(
            str(flow_id),
            current_user.id,
            widen_for_shares=True,
        )
    except HTTPException as e:
        if e.status_code == status.HTTP_404_NOT_FOUND:
            raise _flow_not_found_http_exception(str(flow_id)) from e
        raise
    except OperationalError as e:
        await logger.aexception("Database error fetching flow for workflow execution")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable, Please try again.",
                "code": "DATABASE_ERROR",
                "message": "Failed to fetch flow. Please try again.",
                "flow_id": str(flow_id),
            },
        ) from e
    except Exception as err:
        await logger.aexception("Unexpected error during workflow execution")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "flow_id": str(flow_id),
            },
        ) from err


async def authorize_flow_action(current_user: UserRead, flow, action: WorkflowAction) -> None:
    """Map a ``WorkflowAction`` to a ``FlowAction`` and enforce it.

    A denied share-aware fetch is reframed to 404 so flow existence is not
    leaked through a raw 403.
    """
    flow_action = FlowAction.READ if action == WorkflowAction.READ else FlowAction.EXECUTE
    try:
        await ensure_flow_permission(
            current_user,
            flow_action,
            flow_id=flow.id,
            flow_user_id=flow.user_id,
            workspace_id=getattr(flow, "workspace_id", None),
            folder_id=getattr(flow, "folder_id", None),
        )
    except HTTPException as exc:
        privacy = _flow_not_found_privacy_exception(exc, str(flow.id))
        # Preserve the legacy contract: any 404 on this path surfaces as the
        # structured FLOW_NOT_FOUND body, not the privacy-reframe's string detail.
        if privacy.status_code == status.HTTP_404_NOT_FOUND:
            raise _flow_not_found_http_exception(str(flow.id)) from exc
        raise privacy from exc


def _apply_execution_gates(parsed, flow, current_user: UserRead) -> None:
    """The langflow request gates that run before a flow executes."""
    _reject_unsupported_sync_fields(parsed)
    try:
        _enforce_flow_data_override_owner(parsed, flow, current_user)
    except HTTPException as exc:
        # The owner-override deny is a privacy 404 (string detail); re-wrap to the
        # structured FLOW_NOT_FOUND body to match the legacy single-try contract.
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise _flow_not_found_http_exception(str(flow.id)) from exc
        raise
    _validate_flow_data_for_execution(parsed, flow)


async def run_sync_with_mapping(
    parsed,
    flow,
    current_user: UserRead,
    *,
    http_request: Request,
    background_tasks: BackgroundTasks,
) -> WorkflowExecutionResponse:
    """Inline sync run with the langflow timeout/validation error mapping."""
    _apply_execution_gates(parsed, flow, current_user)
    job_id = uuid4()
    try:
        return await execute_sync_workflow_with_timeout(
            parsed=parsed,
            flow=flow,
            job_id=job_id,
            current_user=current_user,
            background_tasks=background_tasks,
            http_request=http_request,
        )
    except WorkflowTimeoutError:
        timeout_seconds = _resolve_execution_timeout()
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail={
                "error": "Execution timeout",
                "code": "EXECUTION_TIMEOUT",
                "message": f"Workflow execution exceeded {timeout_seconds} seconds",
                "job_id": str(job_id),
                "flow_id": str(parsed.flow_id),
                "timeout_seconds": timeout_seconds,
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
    except HTTPException:
        raise
    except Exception as err:
        await logger.aexception("Unexpected error during workflow execution")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "flow_id": parsed.flow_id,
            },
        ) from err


def build_stream_response(
    parsed,
    flow,
    current_user: UserRead,
    *,
    stream_protocol: str,
    background_tasks: BackgroundTasks,
) -> StreamingResponse:
    """Live-stream a run via the v1 build-vertex loop (agui side-channel + persistence).

    The langflow stream path is NOT lfx's leaner ``stream_workflow_frames``: it
    drives ``generate_flow_events`` so per-vertex events, the agui ``CUSTOM``
    side-channel, and vertex-build persistence all survive. Validation gates run
    before the response is constructed so a bad request fails before streaming.
    """
    _apply_execution_gates(parsed, flow, current_user)
    adapter = get_stream_adapter(
        stream_protocol,
        StreamAdapterContext(
            run_id=str(uuid4()),
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


async def submit_background_with_mapping(
    parsed,
    flow,
    current_user: UserRead,
    *,
    stream_protocol: str,
) -> WorkflowJobResponse:
    """Queue a durable background run with the langflow service error mapping."""
    _apply_execution_gates(parsed, flow, current_user)
    try:
        return await execute_workflow_background(
            parsed=parsed,
            flow=flow,
            job_id=uuid4(),
            current_user=current_user,
            http_request=None,
            stream_protocol=stream_protocol,
        )
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
    except HTTPException:
        raise
    except Exception as err:
        await logger.aexception("Unexpected error during workflow execution")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "flow_id": parsed.flow_id,
            },
        ) from err


async def execute_workflow(
    request: WorkflowRunRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    current_user: Annotated[UserRead, Depends(get_current_user_for_workflow)],
) -> WorkflowExecutionResponse | WorkflowJobResponse | StreamingResponse:
    """Execute a flow from a native ``WorkflowRunRequest`` body.

    The HTTP ``POST /workflows`` route is served by the shared lfx router (bound
    to :class:`~langflow.api.v2.workflow_host.LangflowWorkflowHost`), which calls
    the same ``resolve_flow_for_execution`` / ``authorize_flow_action`` /
    ``run_sync_with_mapping`` / ``build_stream_response`` /
    ``submit_background_with_mapping`` helpers this function does. This function
    is retained as the langflow-signature entry the direct-call tests exercise so
    the admission path stays single-sourced.

    ``mode`` selects the execution path:
        - **sync** (default): run inline, return ``WorkflowExecutionResponse``.
        - **stream**: SSE in ``stream_protocol`` (``langflow`` default, ``agui``).
        - **background**: queue a job, return ``WorkflowJobResponse``.
    """
    if request.stream_protocol not in STREAM_ADAPTERS:
        raise _unknown_protocol_http_exception(
            UnknownStreamProtocolError(request.stream_protocol, available_protocols())
        )

    parsed = parse_workflow_run_request(request)
    flow = await resolve_flow_for_execution(parsed.flow_id, current_user)
    await authorize_flow_action(current_user, flow, WorkflowAction.EXECUTE)

    if parsed.mode == "background":
        return await submit_background_with_mapping(parsed, flow, current_user, stream_protocol=request.stream_protocol)
    if parsed.mode == "stream":
        return build_stream_response(
            parsed,
            flow,
            current_user,
            stream_protocol=request.stream_protocol,
            background_tasks=background_tasks,
        )
    return await run_sync_with_mapping(
        parsed, flow, current_user, http_request=http_request, background_tasks=background_tasks
    )


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
        await logger.aexception("Database error retrieving workflow job %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to retrieve job. Please try again.",
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
        timeout_seconds = _resolve_execution_timeout()
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail={
                "error": "Execution timeout",
                "code": "EXECUTION_TIMEOUT",
                "message": f"Workflow execution exceeded {timeout_seconds} seconds",
                "job_id": job_id_str,
                "flow_id": flow_id_str,
                "timeout_seconds": timeout_seconds,
            },
        ) from err
    except Exception as exc:
        await logger.aexception("Unexpected error processing workflow job status for %s", job_id_str)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to process job status.",
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

    try:
        # 1. Fetch Job
        job = await job_service.get_job_by_job_id(job_id, user_id=current_user.id)
    except Exception as exc:
        await logger.aexception("Database error retrieving workflow job %s for stop", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to retrieve job status. Please try again.",
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
        try:
            cancelled = await _cancel_workflow_queue_job(str(job_id))
        except asyncio.CancelledError as exc:
            message_code = exc.args[0] if exc.args else "UNKNOWN"
            if message_code != "LANGFLOW_USER_CANCELLED":
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": "Task cancellation error",
                        "code": message_code,
                        "message": f"Job {job_id} was cancelled unexpectedly by the system",
                        "job_id": str(job_id),
                    },
                ) from exc
            cancelled = True
        if not cancelled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "Cancellation unavailable",
                    "code": "WORKFLOW_CANCEL_UNAVAILABLE",
                    "message": f"Unable to confirm cancellation for job {job_id}",
                    "job_id": str(job_id),
                },
            )
        await job_service.update_job_status(job_id, JobStatus.CANCELLED)
        # The owning buffer task appends the protocol-native cancellation
        # terminal event before marking replay done. This is only a fallback
        # for races where a local buffer exists but no owner task is running.
        await _finish_cancelled_background_run(str(job_id))

        message = f"Job {job_id} cancelled successfully."
        return WorkflowStopResponse(job_id=str(job_id), message=message)
    except HTTPException:
        raise
    except Exception as exc:
        await logger.aexception("Unexpected error stopping workflow job %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"Failed to stop job {job_id}.",
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
    # Live stream re-attach is intentionally owner-only and does not consult the
    # authorization plugin: the replay buffer is process-local and keyed by the
    # originating user, matching stop_workflow and the active-status path. Only
    # the COMPLETED-status reconstruction branch is share-aware (it reloads the
    # flow); a share-holder tails via the status endpoint, not this live stream.
    if bg_run is not None and bg_run.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Background run not found",
                "code": "JOB_NOT_FOUND",
                "message": f"No buffered events for job {job_id}.",
                "job_id": job_id,
            },
        )

    if bg_run is None:
        try:
            job_uuid = UUID(job_id)
        except ValueError:
            job_uuid = None

        job = None
        if job_uuid is not None:
            with contextlib.suppress(Exception):
                job = await get_job_service().get_job_by_job_id(job_uuid, user_id=current_user.id)

        if job is None or job.type != JobType.WORKFLOW:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Background run not found",
                    "code": "JOB_NOT_FOUND",
                    "message": f"No buffered events for job {job_id}.",
                    "job_id": job_id,
                },
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Background event buffer unavailable",
                "code": "BACKGROUND_EVENTS_UNAVAILABLE",
                "message": (
                    f"Buffered events for job {job_id} are not available here. "
                    "Use the workflow status endpoint for this job."
                ),
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
