"""V2 Workflow execution endpoints.

This module implements the V2 Workflow API route handlers for executing flows
with enhanced error handling, timeout protection, and structured responses.
The execution machinery itself lives in sibling modules:

    - ``workflow_validation``: request/permission guards.
    - ``workflow_execution``: sync + streaming run-driving.
    - ``services/background_execution``: durable, re-attachable background runs.

Endpoints:
    POST /workflows: Execute a workflow (sync, stream, or background modes)
    GET /workflows: Get workflow job status by job_id
    POST /workflows/stop: Stop a running workflow execution
    GET /workflows/pending: List suspended HITL jobs for a flow
    POST /workflows/{job_id}/resume: Resume a suspended (HITL) workflow
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
from dataclasses import replace
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import EventSourceResponse, StreamingResponse
from lfx.exceptions.tweaks import TweakRefusedError
from lfx.log.logger import logger
from lfx.memory.flow_context import derive_message_owner_uuid
from lfx.schema.workflow import (
    WORKFLOW_STATUS_RESPONSES,
    JobId,
    JobStatus,
    WorkflowExecutionResponse,
    WorkflowJobResponse,
    WorkflowResumeRequest,
    WorkflowResumeResponse,
    WorkflowRunRequest,
    WorkflowStopRequest,
    WorkflowStopResponse,
)
from lfx.services.deps import injectable_session_scope_readonly
from lfx.workflow.actions import WorkflowAction
from lfx.workflow.adapters import (
    StreamAdapterContext,
    UnknownStreamProtocolError,
    get_stream_adapter,
)
from lfx.workflow.converters import (
    ParsedWorkflowRun,
    parse_workflow_run_request,
    workflow_response_from_output_events,
)
from lfx.workflow.end_user_identity import resolve_serving_end_user_id, serving_end_user_enabled
from pydantic_core import ValidationError as PydanticValidationError
from sqlalchemy.exc import OperationalError

from langflow.api.utils.execution_errors import caller_owns_flow
from langflow.api.v2.workflow_execution import (
    _execute_streaming_workflow,
    _resolve_execution_timeout,
    _stream_event_frames,
    execute_sync_workflow_with_timeout,
)
from langflow.api.v2.workflow_reconstruction import reconstruct_workflow_response_from_job_id
from langflow.api.v2.workflow_validation import (
    _apply_flow_data_override_policy,
    _flow_not_found_privacy_exception,
    _reject_sync_only_fields,
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
from langflow.services.authorization.fetch import deny_to_404_unless_readable
from langflow.services.authorization.flow_data_override import resolve_flow_data_override
from langflow.services.background_execution.service import (
    InvalidRequestOverridesError,
    RequestOverridesUnavailableError,
)
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.jobs.model import Job, JobType
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import (
    get_background_execution_service,
    get_job_service,
    get_memory_base_service,
    get_task_service,
)
from langflow.services.jobs.exceptions import DuplicateJobError
from langflow.services.warm_registry.resolver import resolve_warm_flow_for_execution

# Finished states a late /stop must not rewrite (CANCELLED is handled separately
# with its own idempotent early return).
_TERMINAL_JOB_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMED_OUT})


def _workflow_job_mode(job: Job) -> str | None:
    """Return the persisted execution mode for a workflow job, if recognized.

    Durable background submissions store their sanitized request under
    ``job_metadata["request"]``. Sync and live-stream rows do not have that
    durable execution handle, so missing or malformed metadata intentionally
    resolves to ``None`` and is treated as non-cancellable.
    """
    metadata = job.job_metadata if isinstance(job.job_metadata, dict) else {}
    request = metadata.get("request")
    if not isinstance(request, dict):
        return None
    mode = request.get("mode")
    return mode if mode in {"background", "stream", "sync"} else None


# The langflow durable background routes (GET status, POST /stop, GET /pending,
# POST /{job_id}/resume, GET /{job_id}/events). The POST run path is contributed
# by the shared lfx router (``lfx.workflow.router.create_workflow_router``)
# bound to ``LangflowWorkflowHost``; only these durable, behaviorally-rich
# routes stay langflow-owned. Both are mounted on the same ``/workflows``
# prefix in ``langflow.api.router``.
router = APIRouter(prefix="/workflows", tags=["Workflow"])

FLOW_EXECUTE_DENIED_DETAIL = "You don't have permission to execute this flow."


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
        warm_flow = await resolve_warm_flow_for_execution(
            str(flow_id),
            current_user.id,
            widen_for_shares=True,
        )
        if warm_flow is not None:
            return warm_flow
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


async def authorize_flow_action(
    current_user: UserRead, flow, action: WorkflowAction, *, requested_id: str | None = None
) -> None:
    """Map a ``WorkflowAction`` to a ``FlowAction`` and enforce it.

    A denied share-aware fetch is reframed to 404 so flow existence is not
    leaked through a raw 403. ``requested_id`` is the identifier the caller sent
    (an endpoint name or a UUID); the reframed body echoes it instead of the
    resolved internal UUID. Falls back to ``flow.id`` when not provided.

    The 404 reframe is skipped when the caller can read the flow: they already
    know it exists, and "verify the flow_id and try again" sends them to debug
    an identifier that is correct. Those callers get an execute denial instead.
    """
    flow_action = FlowAction.READ if action == WorkflowAction.READ else FlowAction.EXECUTE
    # Echo the identifier the caller requested (which may be an endpoint name),
    # not the resolved internal UUID, so a denial does not leak the canonical id.
    echo_id = requested_id if requested_id is not None else str(flow.id)
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
        if flow_action == FlowAction.EXECUTE:
            resolved = await deny_to_404_unless_readable(
                exc,
                lambda: ensure_flow_permission(
                    current_user,
                    FlowAction.READ,
                    flow_id=flow.id,
                    flow_user_id=flow.user_id,
                    workspace_id=getattr(flow, "workspace_id", None),
                    folder_id=getattr(flow, "folder_id", None),
                ),
                denied_detail=FLOW_EXECUTE_DENIED_DETAIL,
            )
            if resolved.status_code == status.HTTP_403_FORBIDDEN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "Permission denied",
                        "code": "FLOW_EXECUTE_FORBIDDEN",
                        "message": FLOW_EXECUTE_DENIED_DETAIL,
                        "flow_id": echo_id,
                    },
                ) from exc
        privacy = _flow_not_found_privacy_exception(exc, echo_id)
        # Preserve the legacy contract: any 404 on this path surfaces as the
        # structured FLOW_NOT_FOUND body, not the privacy-reframe's string detail.
        if privacy.status_code == status.HTTP_404_NOT_FOUND:
            raise _flow_not_found_http_exception(echo_id) from exc
        raise privacy from exc
    # ensure_flow_permission's audit write + owner-override lookup touch the DB, so a
    # transient lock raises a non-HTTPException. Map it the same way the fetch path does
    # (503 DATABASE_ERROR, retryable) instead of leaking a bare 500.
    except OperationalError as e:
        await logger.aexception("Database error enforcing flow permission for workflow execution")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable, Please try again.",
                "code": "DATABASE_ERROR",
                "message": "Failed to enforce flow permission. Please try again.",
                "flow_id": echo_id,
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
                "flow_id": echo_id,
            },
        ) from err

    # Resolve the graph-override verdict here, where we can await the policy
    # plugin. The sync gates below run in all three execution modes and read
    # the resolved value; without this they fall back to owner-only.
    if flow_action == FlowAction.EXECUTE:
        await resolve_flow_data_override(current_user, flow)


def _apply_execution_gates(parsed, flow, current_user: UserRead):
    """Run request gates and return any server-sanitized execution payload."""
    expose_error_details = caller_owns_flow(flow, current_user)
    _reject_unsupported_sync_fields(parsed)
    _reject_sync_only_fields(parsed)
    # An execute-only caller keeps running: their override is dropped and the
    # stored graph runs, instead of the flow reading as non-existent (LE-1905).
    parsed = _apply_flow_data_override_policy(parsed, flow, current_user)
    return _validate_flow_data_for_execution(
        parsed,
        flow,
        current_user,
        expose_error_details=expose_error_details,
    )


async def run_sync_with_mapping(
    parsed,
    flow,
    current_user: UserRead,
    *,
    http_request: Request,
    background_tasks: BackgroundTasks,
) -> WorkflowExecutionResponse:
    """Inline sync run with the langflow timeout/validation error mapping."""
    parsed = _apply_execution_gates(parsed, flow, current_user)
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
    except TweakRefusedError:
        raise
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
    except OperationalError as e:
        await logger.aexception("Database error during workflow execution")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable, Please try again.",
                "code": "DATABASE_ERROR",
                "message": "Failed to fetch flow. Please try again.",
                "flow_id": parsed.flow_id,
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
    parsed = _apply_execution_gates(parsed, flow, current_user)
    run_id = str(uuid4())
    adapter = get_stream_adapter(
        stream_protocol,
        StreamAdapterContext(
            run_id=run_id,
            thread_id=parsed.session_id or str(flow.id),
        ),
    )
    return _execute_streaming_workflow(
        adapter=adapter,
        run_id=run_id,
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
    parsed = _apply_execution_gates(parsed, flow, current_user)
    try:
        return await execute_workflow_background(
            parsed=parsed,
            flow=flow,
            job_id=uuid4(),
            current_user=current_user,
            http_request=None,
            stream_protocol=stream_protocol,
            idempotency_key=getattr(parsed, "idempotency_key", None),
        )
    except InvalidRequestOverridesError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": "Invalid request overrides",
                "code": "INVALID_REQUEST_OVERRIDES",
                "message": "globals and tweaks must contain JSON-compatible values.",
                "field": err.field,
                "flow_id": parsed.flow_id,
            },
        ) from err
    except RequestOverridesUnavailableError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable",
                "code": "REQUEST_OVERRIDES_UNAVAILABLE",
                "message": "Background request overrides are temporarily unavailable. Please try again.",
                "flow_id": parsed.flow_id,
            },
        ) from err
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
    except OperationalError as e:
        await logger.aexception("Database error during workflow execution")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable, Please try again.",
                "code": "DATABASE_ERROR",
                "message": "Failed to fetch flow. Please try again.",
                "flow_id": parsed.flow_id,
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
                "flow_id": parsed.flow_id,
            },
        ) from err


def _unknown_protocol_http_exception(exc: UnknownStreamProtocolError) -> HTTPException:
    """Build the 422 response for an unknown ``stream_protocol``.

    Used by the public workflow router (``workflow_public.py``) so its error body
    matches the shared lfx router's: ``available`` lists the registered protocol
    names so clients can self-correct.
    """
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "error": "Unknown stream_protocol",
            "code": "UNKNOWN_STREAM_PROTOCOL",
            "message": f"Unknown stream_protocol {exc.name!r}.",
            "available": exc.available,
        },
    )


def _end_user_matches(request_end_user_id: str | None, job_metadata: object) -> bool:
    """The pure serving-plane end-user ownership rule, shared by every jobs endpoint.

    Given a request's resolved end-user id and a job's ``job_metadata``, decide whether they name
    the same end user (superuser / feature gating is the caller's job). Used by the single-job guard
    (``_caller_owns_job_end_user`` for status/stop/resume) AND the enumerating pending list, so the
    isolation rule lives in exactly one place:

    * ``job_metadata`` is coerced to ``{}`` unless it is a real dict — a security guard must never
      decide from a malformed/legacy value (a JSON string, list, or test mock).
    * No request end user (feature off / anonymous): matches ONLY a job that also has none.
    * Both present: the derived owner ids must be equal, so a raw-string vs UUID-form gateway id
      compares canonically (D6), exactly as message ownership keys it.
    """
    metadata = job_metadata if isinstance(job_metadata, dict) else {}
    job_end_user = metadata.get("end_user_id")
    if request_end_user_id is None:
        return job_end_user is None
    if job_end_user is None:
        return False
    return derive_message_owner_uuid(request_end_user_id) == derive_message_owner_uuid(job_end_user)


def _caller_owns_job_end_user(job: Job, http_request: Request, current_user: UserRead) -> bool:
    """Whether the caller may act on ``job`` under serving-plane end-user isolation.

    On the serving plane every end user shares the one service account (SID), so SID-level
    ownership (already applied by ``get_job_by_job_id(user_id=SID)``) cannot tell two end
    users apart. This layers the end-user check on top: the request's trusted end-user id
    (the gateway header) must resolve to the same owner the job was created under
    (``job_metadata['end_user_id']``). A mismatch means it is another end user's job.

    Because ``job.user_id`` stays the SID (so re-enqueue/resume can still fetch the SID-owned
    flow — F8), the end-user identity lives only in ``job_metadata``; this is the sole place
    it gates access. Decisions:

    * Superuser bypass applies ONLY when the serving feature is off. On the serving plane the
      shared service account (SID) is itself a superuser, so an unconditional bypass would let
      any end user (all riding that one SID) read/stop/resume any other's run — defeating the
      whole isolation layer for the exact deployment it exists for. When serving is on the
      bypass is suppressed and even the SID is scoped to the request's end user.
    * Feature off / anonymous request (``resolve_serving_end_user_id`` -> None): there is no
      end-user scope to enforce, so a job created without an end user passes and one created
      under an end user does not (an anonymous caller must not reach an identified run).
    * Identified request: the derived request owner must equal the derived job owner. Both
      sides derive through :func:`derive_message_owner_uuid` so the raw-string vs UUID-form
      gateway id compares canonically, exactly as message ownership keys it.
    """
    if current_user.is_superuser and not serving_end_user_enabled():
        return True
    return _end_user_matches(resolve_serving_end_user_id(http_request=http_request), job.job_metadata)


def _parse_persisted_workflow_request(request: dict) -> ParsedWorkflowRun:
    """Re-parse a persisted background/resume request into a ``ParsedWorkflowRun``.

    ``persist_messages`` and ``end_user_id`` are internal serving-plane decisions
    (anonymous runs are ephemeral; identified runs carry the end user), not client
    wire fields — ``WorkflowRunRequest`` forbids extras, so they are popped before
    constructing the request and re-applied to the parsed run. Without this, the
    worker re-parse would reset ``persist_messages`` to the ``True`` default (an
    anonymous background/resume run would persist memory it must not) and drop
    ``end_user_id`` (an identified run would stamp memory to the SID, not the end
    user). Legacy rows that predate the fields fall back to persist=True /
    end_user_id=None, matching prior behavior.
    """
    internal = {"persist_messages", "end_user_id"}
    persist_messages = request.get("persist_messages", True)
    end_user_id = request.get("end_user_id")
    request_fields = {k: v for k, v in request.items() if k not in internal}
    return replace(
        parse_workflow_run_request(WorkflowRunRequest(**request_fields)),
        persist_messages=persist_messages,
        end_user_id=end_user_id,
    )


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
    parsed = _parse_persisted_workflow_request(request)
    terminal_error_type = adapter.terminal_error_type

    async def _source(*, job_id=None, resume=None, **_kwargs):
        flow = await resolve_flow_for_execution(str(flow_id), user)
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
                provider_policy_flow=flow,
                source_flow_owner_id=flow.user_id,
                expose_error_details=caller_owns_flow(flow, user),
                job_id=job_id,
                resume=resume,
                # Key the persisted vertex builds by the durable job_id so a completed run's GET
                # status can reconstruct its outputs (and recover the session_id it ran under)
                # instead of falling back to the leaner Job.result rebuild.
                run_id=str(job_id) if job_id else None,
                # The durable runner already owns this run's WORKFLOW job row (keyed by the durable
                # job_id) and fires the memory-base hook below with that id, so the build pipeline
                # must not mint its own run_id-keyed WORKFLOW row + hook (it would double both).
                track_job_status=False,
                # This factory is the runner the v2 background route actually reaches, so the label
                # belongs here; without it a background run is indistinguishable from a live stream.
                protocol="v2.background",
                # Emit the off-wire terminal-output capture the runner records into
                # ``Job.result`` — protocol-neutral, so agui-protocol runs get a
                # populated GET-status result too (not just langflow).
                emit_output_capture=True,
                # No client is waiting on a background run, so the sync HTTP ceiling is the wrong
                # budget for it: nesting it inside the runner's asyncio.wait_for capped every
                # background job at workflow_execution_timeout and made the documented
                # background_job_timeout=None ("no timeout") unreachable. JobRunner owns it.
                execution_timeout=None,
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
            if not errored and caller_owns_flow(flow, user):
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
            # Serving-plane ephemeral decision must survive the worker re-parse so an
            # anonymous background/resume run does not persist memory (see the pop in
            # _default_frame_source_factory).
            "persist_messages": parsed.persist_messages,
            # The end-user identity is likewise an internal decision, not a wire field:
            # it must survive the round-trip so an identified background/resume run
            # stamps memory to the end user on the worker, not the SID.
            "end_user_id": parsed.end_user_id,
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
    http_request: Request,
    current_user: Annotated[UserRead, Depends(get_current_user_for_workflow)],
    job_id: Annotated[JobId | None, Query(description="Job ID to query")] = None,
    session: Annotated[object, Depends(injectable_session_scope_readonly)] = None,
) -> WorkflowExecutionResponse | WorkflowJobResponse:
    """Get workflow job status and results.

    Args:
        http_request: The FastAPI request, for serving-plane end-user isolation.
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

    # Serving-plane end-user isolation: a different end user (sharing the SID) must not read
    # this run. 404 (not 403) so the job's existence is not leaked. See F8.
    if not _caller_owns_job_end_user(job, http_request, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Workflow job not found",
                "code": "JOB_NOT_FOUND",
                "message": f"Workflow job {job_id} not found",
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

            # The session the run executed under, resolved exactly as the runner's
            # frame source did (``parsed.session_id or str(flow.id)``): the submit
            # request is persisted on ``job_metadata["request"]``, so a completed
            # background GET echoes the same chat/memory thread sync returns. The
            # terminal output's ``content`` is a rendered string, so it can't be
            # searched structurally — the persisted request is the source of truth.
            persisted_request = (job.job_metadata or {}).get("request") or {}
            effective_session_id = persisted_request.get("session_id") or flow_id_str

            # Default GET-status path: rebuild from the protocol-neutral terminal
            # captures the runner stored in ``Job.result``. This needs no
            # ``vertex_build`` rows, so it works with vertex-build storage off
            # (headless) and skips graph reconstruction.
            result = job.result if isinstance(job.result, dict) else {}
            output_events = result.get("outputs") or []
            partial_stored_response: WorkflowExecutionResponse | None = None
            if isinstance(output_events, list) and output_events:
                try:
                    return workflow_response_from_output_events(
                        output_events,
                        flow_id=flow_id_str,
                        job_id=job_id_str,
                        session_id=effective_session_id,
                        fail_on_rejected=True,
                    )
                except ValueError:
                    # Preserve every decodable capture in case the legacy
                    # vertex-build fallback is also unavailable.
                    partial_stored_response = workflow_response_from_output_events(
                        output_events,
                        flow_id=flow_id_str,
                        job_id=job_id_str,
                        session_id=effective_session_id,
                    )

            # Fallback: ``Job.result`` carried no outputs, has an invalid shape,
            # contains rejected/version-skewed entries, or predates capture.
            # Reconstruct from ``vertex_build`` rows keyed by job_id when present.
            try:
                reconstructed = await reconstruct_workflow_response_from_job_id(
                    session=session,
                    flow=flow,
                    job_id=job_id_str,
                    user_id=str(current_user.id),
                    is_superuser=bool(getattr(current_user, "is_superuser", False)),
                )
            except ValueError:
                if partial_stored_response is not None:
                    return partial_stored_response
                return workflow_response_from_output_events(
                    [],
                    flow_id=flow_id_str,
                    job_id=job_id_str,
                    session_id=effective_session_id,
                )
            else:
                if reconstructed.session_id is None:
                    reconstructed = reconstructed.model_copy(update={"session_id": effective_session_id})
                return reconstructed

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
    description="Stop a running background workflow execution",
)
async def stop_workflow(
    request: WorkflowStopRequest,
    http_request: Request,
    current_user: Annotated[UserRead, Depends(get_current_user_for_workflow)],
) -> WorkflowStopResponse:
    """Stop a running background workflow execution by job_id.

    Sync and live-stream runs execute inside their caller's request and cannot be
    interrupted by the durable background executor. Those modes are rejected
    instead of reporting a cancellation that did not happen.

    Args:
        request: Stop request containing job_id and optional force flag
        http_request: The FastAPI request, for serving-plane end-user isolation.
        current_user: Authenticated user (session cookie or API key)

    Returns:
        WorkflowStopResponse: Confirmation of stop request with final job status

    Raises:
        HTTPException:
            - 403: Developer API disabled or unauthorized
            - 404: Job ID not found
            - 409: Job is not a cancellable background run
            - 500: Internal server error
    """
    job_id = request.job_id
    job_service = get_job_service()
    task_service = get_task_service()

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

    # Serving-plane end-user isolation: a different end user (sharing the SID) must not stop
    # this run. 404 (not 403) so the job's existence is not leaked. See F8.
    if not _caller_owns_job_end_user(job, http_request, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Job not found",
                "code": "JOB_NOT_FOUND",
                "message": f"Job {job_id} not found",
                "job_id": str(job_id),
            },
        )

    job_mode = _workflow_job_mode(job)
    if job_mode != "background":
        display_mode = job_mode or "unknown"
        await logger.ainfo("Rejected stop for workflow job %s in non-cancellable mode %s", job_id, display_mode)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Job cannot be stopped",
                "code": "JOB_NOT_CANCELLABLE",
                "message": "Only background workflow jobs can be stopped.",
                "job_id": str(job_id),
                "mode": display_mode,
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
        # Best-effort: a backend that cannot take the signal must not block the
        # cancel, but swallowing it silently would hide the one failure that lets
        # a run keep going after we report CANCELLED. Log, do not suppress quietly.
        try:
            await get_background_execution_service().stop_job(job_id, current_user)
        except Exception:  # noqa: BLE001
            await logger.aexception("Failed to signal stop for workflow job %s; cancelling row anyway", job_id)
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
    "/pending",
    summary="List pending human-input requests",
    description="Suspended HITL jobs for a flow plus their pending request, for the Traces overlay.",
)
async def list_pending_workflows(
    http_request: Request,
    current_user: Annotated[UserRead, Depends(get_current_user_for_workflow)],
    flow_id: Annotated[UUID, Query(description="Flow ID to list pending HITL requests for")],
) -> list[dict]:
    from langflow.api.v2.hitl import list_pending_human_requests

    # Serving-plane end-user isolation: this endpoint ENUMERATES suspended runs by flow_id (no job
    # id needed), and each row exposes the merged session_id + the HITL prompt — so a scope check is
    # even more load-bearing here than on status/stop/resume. Filter to the caller's own end user.
    # The superuser "see all" bypass applies only when serving is off; on the serving plane the SID
    # is a superuser, so an unconditional bypass would leak every end user's suspended run to every
    # other. Feature off / anonymous -> only end-user-less jobs, unchanged. See F8 / B1.
    return await list_pending_human_requests(
        flow_id,
        current_user.id,
        request_end_user_id=resolve_serving_end_user_id(http_request=http_request),
        include_all_end_users=current_user.is_superuser and not serving_end_user_enabled(),
    )


@router.post(
    "/{job_id}/resume",
    summary="Resume Workflow",
    description="Resume a suspended (human-in-the-loop) workflow with a decision.",
)
async def resume_workflow(
    job_id: str,
    request: WorkflowResumeRequest,
    http_request: Request,
    current_user: Annotated[UserRead, Depends(get_current_user_for_workflow)],
) -> WorkflowResumeResponse:
    """Resume a SUSPENDED workflow run with a human decision.

    Owner-or-superuser; a non-owner non-superuser (or unknown/non-workflow job)
    maps to 404 to avoid leaking other users' runs. A stale/duplicate request_id
    or a non-suspended job maps to 409 (single-use enforced behind ``resume_job``).
    Resuming executes the remainder of the flow, so flow:execute is re-enforced —
    access revoked while the run was suspended must not let the decision through.
    """

    def _not_found() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Workflow job not found", "code": "JOB_NOT_FOUND", "job_id": job_id},
        )

    try:
        parsed_job_id = UUID(job_id)
    except ValueError as exc:
        raise _not_found() from exc

    job = await get_job_service().get_job_by_job_id(parsed_job_id)
    is_owner = job is not None and job.user_id is not None and job.user_id == current_user.id
    if job is None or job.type != JobType.WORKFLOW or not (is_owner or current_user.is_superuser):
        raise _not_found()
    # Serving-plane end-user isolation: a different end user (sharing the SID) must not resume
    # another's suspended run. Layered on the SID owner/superuser check above. See F8.
    if not _caller_owns_job_end_user(job, http_request, current_user):
        raise _not_found()

    from langflow.api.v2.hitl import ensure_resume_execute_permission, is_decision_allowed, mark_card_answered

    await ensure_resume_execute_permission(current_user, job.flow_id)

    if not await is_decision_allowed(parsed_job_id, request.decision or {}):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": "Invalid decision",
                "code": "INVALID_DECISION",
                "message": "decision.action_id is not one of the pending request's allowed_decisions.",
                "job_id": job_id,
            },
        )

    service = get_background_execution_service()
    if service._frame_source_factory is None:  # noqa: SLF001
        service._frame_source_factory = _default_frame_source_factory  # noqa: SLF001
    # Snapshot the card id before the continuation runs: it may reach another pause and
    # overwrite job metadata, and this decision must never stamp that later card.
    card_message_id = (job.job_metadata or {}).get("card_message_id")
    try:
        accepted = await service.resume_job(
            parsed_job_id,
            current_user,
            request_id=request.request_id,
            decision=request.decision or {},
        )
    except RequestOverridesUnavailableError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service unavailable",
                "code": "REQUEST_OVERRIDES_UNAVAILABLE",
                "message": "Background request overrides are temporarily unavailable. Please try again.",
                "job_id": job_id,
            },
        ) from err
    if not accepted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Job is not resumable",
                "code": "NOT_RESUMABLE",
                "message": "Job is not suspended, already resumed, or the request_id is stale.",
                "job_id": job_id,
            },
        )
    await mark_card_answered(parsed_job_id, request.request_id, request.decision or {}, card_message_id=card_message_id)
    return WorkflowResumeResponse(job_id=job_id, status="resuming", message="Resume accepted")


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

    def _not_found() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Background run not found",
                "code": "JOB_NOT_FOUND",
                "message": f"No background run for job {job_id}.",
                "job_id": job_id,
            },
        )

    try:
        # Pre-validate ownership/existence so a deny surfaces as a 404 before
        # the SSE stream opens. ``events`` re-validates as defense-in-depth.
        await service.status(UUID(job_id), current_user)
        job = await get_job_service().get_job_by_job_id(UUID(job_id), user_id=current_user.id)
    except (PermissionError, ValueError) as exc:
        raise _not_found() from exc

    # Serving-plane end-user isolation: a different end user (sharing the SID) must not reattach
    # to another's live event stream — the same rule the status/stop/resume paths enforce. See F8.
    if job is None or not _caller_owns_job_end_user(job, http_request, current_user):
        raise _not_found()

    return EventSourceResponse(
        service.events(UUID(job_id), last_event_id=last_event_id, user=current_user),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
