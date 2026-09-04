from __future__ import annotations

import asyncio
import time
import traceback
import uuid
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from lfx.exceptions.tweaks import TweakRefusedError
from lfx.graph.graph.base import Graph
from lfx.graph.utils import log_vertex_build
from lfx.log.logger import logger
from lfx.observability import execution_protocol
from lfx.schema.schema import InputValueRequest, OutputValue
from lfx.services.cache.utils import CacheMiss
from lfx.utils.flow_validation import (
    PUBLIC_CATALOG_POLICY_UNAVAILABLE_MESSAGE,
    CatalogPolicyIdentityUnavailableError,
    CustomComponentValidationError,
    prepare_flow_build_for_user,
    prepare_public_flow_build,
    validate_catalog_policy_for_flow,
    validate_flow_for_current_settings,
    validate_public_flow_no_code_execution,
)
from sqlmodel import select

from langflow.api.build import cancel_flow_build, get_flow_events_response, start_flow_build
from langflow.api.limited_background_tasks import LimitVertexBuildBackgroundTasks
from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    EventDeliveryType,
    build_and_cache_graph_from_data,
    build_graph_from_db,
    format_elapsed_time,
    format_exception_message,
    get_top_level_vertices,
    parse_exception,
    scope_session_to_namespace,
    validate_public_files,
    verify_public_flow_and_get_user,
)
from langflow.api.utils.core import strip_secret_field_values
from langflow.api.v1.schemas import (
    CancelFlowResponse,
    FlowDataRequest,
    ResultDataResponse,
    StreamData,
    VertexBuildResponse,
    VerticesOrderResponse,
)
from langflow.exceptions.component import ComponentBuildError
from langflow.services.auth.utils import get_current_user_optional
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.fetch import deny_to_404_unless_readable
from langflow.services.authorization.flow_data_override import resolve_flow_data_override
from langflow.services.authorization.public_access import (
    PUBLIC_FLOW_NOT_FOUND_DETAIL,
    PublicResourceAction,
    authorize_public_flow_access,
)
from langflow.services.chat.service import ChatService
from langflow.services.database.models.flow.model import AccessTypeEnum, Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import (
    get_chat_service,
    get_queue_service,
    get_settings_service,
    get_telemetry_service,
    session_scope,
)
from langflow.services.job_queue.service import (
    JobQueueBackendUnavailableError,
    JobQueueNotFoundError,
    JobQueueService,
)
from langflow.services.model_provider_policy_scope import scoped_model_provider_policy_for_flow
from langflow.services.rate_limit import check_rate_limit
from langflow.services.telemetry.schema import ComponentPayload, PlaygroundPayload

if TYPE_CHECKING:
    from lfx.graph.vertex.vertex_types import InterfaceVertex

router = APIRouter(tags=["Chat"])

FLOW_EXECUTE_DENIED_DETAIL = "You don't have permission to execute this flow."


def _validate_graph_for_execution(graph: Graph) -> None:
    """Validate the effective cached graph against the current runtime policy."""
    try:
        validate_flow_for_current_settings(graph)
    except CatalogPolicyIdentityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CustomComponentValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _clear_invalid_graph_cache(chat_service: ChatService, flow_id: str) -> None:
    """Best-effort eviction for a graph rejected by current runtime policy."""
    try:
        await chat_service.clear_cache(flow_id)
    except Exception:  # noqa: BLE001
        await logger.aexception("Failed to evict a graph rejected by runtime policy")


async def _verify_job_ownership(job_id: str, current_user: CurrentActiveUser, queue_service: JobQueueService) -> None:
    """Raise HTTP 404 if the requesting user does not own the job.

    Jobs with no registered owner (build_public_tmp) are accessible to any authenticated user.
    """
    try:
        job_owner = await queue_service.get_job_owner(job_id)
    except JobQueueBackendUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if job_owner is not None and job_owner != current_user.id:
        await logger.awarning(
            "Ownership check failed: user %s tried to access job %s owned by %s",
            current_user.id,
            job_id,
            job_owner,
        )
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")


async def _register_job_owner_or_cancel(queue_service: JobQueueService, job_id: str, user_id: uuid.UUID) -> None:
    """Register the build's owner, cancelling the just-started build on backend outage.

    By the time this runs, start_flow_build has already launched the build task.
    If the Redis-backed queue is unreachable, the client never receives the
    job_id, so cancel the build (best-effort) instead of leaving an unreachable
    build running, then surface a clean 503 instead of a raw redis
    ConnectionError 500.
    """
    try:
        await queue_service.register_job_owner(job_id, user_id)
    except JobQueueBackendUnavailableError as exc:
        try:
            await queue_service.cancel_job(job_id)
        except Exception as cancel_exc:  # noqa: BLE001
            await logger.awarning(f"Failed to cancel job {job_id} after owner registration failed: {cancel_exc!r}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _compiled_from(graph: object, graph_data: dict) -> bool:
    """Whether this compilation was produced from exactly this payload.

    ``raw_graph_data`` is part of ``Graph.__getstate__``, so this survives a serialized
    cache — a marker attribute would be dropped there and silently reintroduce the
    rebuild-per-request behaviour on Redis-backed deployments only.
    """
    raw = getattr(graph, "raw_graph_data", None)
    if not isinstance(raw, dict):
        return False
    return raw.get("nodes") == graph_data.get("nodes") and raw.get("edges") == graph_data.get("edges")


async def _trusted_stored_graph(flow_data, *, is_superuser: bool) -> dict | None:
    """Run the caller-aware component policy over a STORED graph.

    The stored graph is caller-controlled -- any user who can write a flow can persist
    component source through the ordinary flow API -- and the global validator does not
    know who is asking, so it cannot enforce ``custom_component_admin_only`` on its own.
    Returns the trusted copy to build from, or ``None`` when the policy is permissive and
    the stored graph stands. The status mapping matches the whole-flow build seam.
    """
    try:
        return await prepare_flow_build_for_user(flow_data, is_superuser=is_superuser)
    except CatalogPolicyIdentityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CustomComponentValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/build/{flow_id}/vertices",
    deprecated=True,
    include_in_schema=False,
)
async def retrieve_vertices_order(
    *,
    flow_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    data: Annotated[FlowDataRequest | None, Body(embed=True)] | None = None,
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> VerticesOrderResponse:
    """Retrieve the vertices order for a given flow.

    Args:
        flow_id (str): The ID of the flow.
        background_tasks (BackgroundTasks): The background tasks.
        data (Optional[FlowDataRequest], optional): The flow data. Defaults to None.
        stop_component_id (str, optional): The ID of the stop component. Defaults to None.
        start_component_id (str, optional): The ID of the start component. Defaults to None.
        session (AsyncSession, optional): The session dependency.
        current_user: The authenticated user (required so the handler can
            run the same authorization guard the supported /build/{flow_id}/flow
            route uses).

    Returns:
        VerticesOrderResponse: The response containing the ordered vertex IDs and the run ID.

    Raises:
        HTTPException: If there is an error checking the build status.
    """
    # This deprecated editor route is owner-only. Supported full-flow routes
    # provide public execution without exposing the flow-keyed graph cache.
    stmt = select(Flow).where(Flow.id == flow_id).where(Flow.user_id == current_user.id)
    flow = (await session.exec(stmt)).first()
    if not flow:
        raise HTTPException(status_code=404, detail=f"Flow with id {flow_id} not found")
    await ensure_flow_permission(
        current_user,
        FlowAction.EXECUTE,
        flow_id=flow_id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )

    chat_service = get_chat_service()
    telemetry_service = get_telemetry_service()
    start_time = time.perf_counter()
    components_count = None
    run_id = str(uuid.uuid4())
    try:
        with scoped_model_provider_policy_for_flow(
            flow,
            user_id=current_user.id,
            is_superuser=bool(current_user.is_superuser),
        ):
            if not data:
                trusted_data = await _trusted_stored_graph(flow.data, is_superuser=current_user.is_superuser)
                if trusted_data is not None:
                    graph = await build_and_cache_graph_from_data(
                        flow_id=flow_id, graph_data=trusted_data, chat_service=chat_service
                    )
                else:
                    graph = await build_graph_from_db(flow_id=flow_id, session=session, chat_service=chat_service)
            else:
                sanitized_data = await _trusted_stored_graph(
                    data.model_dump(),
                    is_superuser=current_user.is_superuser,
                )
                if sanitized_data is not None:
                    data = FlowDataRequest.model_validate(sanitized_data)
                graph = await build_and_cache_graph_from_data(
                    flow_id=flow_id, graph_data=data.model_dump(), chat_service=chat_service
                )
            graph = graph.prepare(stop_component_id, start_component_id)
        graph.set_run_id(run_id)

        # Now vertices is a list of lists
        # We need to get the id of each vertex
        # and return the same structure but only with the ids
        components_count = len(graph.vertices)
        vertices_to_run = list(graph.vertices_to_run.union(get_top_level_vertices(graph, graph.vertices_to_run)))
        await chat_service.set_cache(str(flow_id), graph)
        background_tasks.add_task(
            telemetry_service.log_package_playground,
            PlaygroundPayload(
                playground_seconds=int(time.perf_counter() - start_time),
                playground_component_count=components_count,
                playground_success=True,
                playground_run_id=run_id,
            ),
        )
        return VerticesOrderResponse(ids=graph.first_layer, run_id=graph.run_id, vertices_to_run=vertices_to_run)
    except Exception as exc:
        background_tasks.add_task(
            telemetry_service.log_package_playground,
            PlaygroundPayload(
                playground_seconds=int(time.perf_counter() - start_time),
                playground_component_count=components_count,
                playground_success=False,
                playground_error_message=str(exc),
                playground_run_id=run_id,
            ),
        )
        # A policy refusal already carries its status; re-wrapping it as 500 would report
        # an authorization decision as a server fault. Telemetry above still records it.
        if isinstance(exc, HTTPException):
            raise
        if "stream or streaming set to True" in str(exc):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if isinstance(exc, CustomComponentValidationError):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if isinstance(exc, RuntimeError):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        await logger.aexception("Error checking build status")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/build/{flow_id}/flow")
async def build_flow(
    *,
    flow_id: uuid.UUID,
    background_tasks: LimitVertexBuildBackgroundTasks,
    inputs: Annotated[InputValueRequest | None, Body(embed=True)] = None,
    data: Annotated[FlowDataRequest | None, Body(embed=True)] = None,
    files: list[str] | None = None,
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    log_builds: bool = True,
    current_user: CurrentActiveUser,
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
    flow_name: str | None = None,
    event_delivery: EventDeliveryType = EventDeliveryType.POLLING,
):
    """Build and process a flow, returning a job ID for event polling.

    This endpoint requires authentication through the CurrentActiveUser dependency.
    For public flows that don't require authentication, use the /build_public_tmp/flow_id/flow endpoint.

    Args:
        flow_id: UUID of the flow to build
        background_tasks: Background tasks manager
        inputs: Optional input values for the flow
        data: Optional flow data
        files: Optional files to include
        stop_component_id: Optional ID of component to stop at
        start_component_id: Optional ID of component to start from
        log_builds: Whether to log the build process
        current_user: The authenticated user
        queue_service: Queue service for job management
        flow_name: Optional name for the flow
        event_delivery: Optional event delivery type - default is streaming

    Returns:
        Dict with job_id that can be used to poll for build status
    """
    # Share-aware load: when the authorization plugin signals cross-user fetch
    # support, the row loads by id alone and the plugin decides. Otherwise we
    # keep the historical owner-or-PUBLIC scoping so the OSS pass-through
    # default cannot widen visibility. PUBLIC flows stay buildable by any
    # authenticated user in both modes.
    from langflow.api.v1.flows_helpers import _read_flow

    async with session_scope() as session:
        flow = await _read_flow(session, flow_id, current_user.id)
        if flow is None:
            public_stmt = select(Flow).where(
                Flow.id == flow_id,
                Flow.access_type == AccessTypeEnum.PUBLIC,
            )
            flow = (await session.exec(public_stmt)).first()
        if not flow:
            await logger.awarning(
                "Flow access denied for user %s: flow %s not found or not owned",
                current_user.id,
                flow_id,
            )
            raise HTTPException(status_code=404, detail=f"Flow with id {flow_id} not found")

    # Authorize the execute action — runs the authorization plugin if registered,
    # no-op in OSS pass-through. Audited regardless. A plugin deny becomes 404
    # so a caller who cannot see the flow cannot enumerate UUIDs by probing for
    # 403 vs 404. A caller who *can* read it has already seen the flow, so that
    # mask buys nothing and only hides which permission they are missing — the
    # Playground is exactly this case.
    try:
        await ensure_flow_permission(
            current_user,
            FlowAction.EXECUTE,
            flow_id=flow_id,
            flow_user_id=flow.user_id,
            workspace_id=flow.workspace_id,
            folder_id=flow.folder_id,
        )
    except HTTPException as exc:
        raise await deny_to_404_unless_readable(
            exc,
            lambda: ensure_flow_permission(
                current_user,
                FlowAction.READ,
                flow_id=flow_id,
                flow_user_id=flow.user_id,
                workspace_id=flow.workspace_id,
                folder_id=flow.folder_id,
            ),
            denied_detail=FLOW_EXECUTE_DENIED_DETAIL,
            not_found_detail=f"Flow with id {flow_id} not found",
        ) from exc

    # Execute-only callers must run the stored graph — they cannot inject an
    # alternate definition and have it run under the owner's resources. This
    # drops the override rather than denying: the caller holds ``flow:execute``,
    # so the run itself is theirs to make, and denying it reported the flow as
    # non-existent to someone already looking at it (LE-1905). Overriding is an
    # edit expressed at run time, so it is gated on ``flow:write``.
    if data is not None and not await resolve_flow_data_override(current_user, flow):
        await logger.ainfo(
            "Ignoring caller-supplied flow data for flow %s: caller may execute but not edit it.",
            flow_id,
        )
        data = None

    try:
        if data:
            raw_data = data.model_dump()
            sanitized_data = await prepare_flow_build_for_user(
                raw_data,
                is_superuser=current_user.is_superuser,
            )
            if sanitized_data is not None:
                data = FlowDataRequest.model_validate(sanitized_data)
        elif flow and flow.data:
            # Stored graphs are caller-controlled too: any user who can write a flow can
            # persist component source through the ordinary flow API and then execute it by
            # building with an empty body. The global validator does not know the caller, so
            # it cannot enforce ``custom_component_admin_only`` here. Run the same caller-aware
            # policy the inline branch runs, and build from the detached copy it returns so the
            # worker compiles the server's trusted source rather than the stored bytes.
            # A permissive policy returns ``None`` and the build still loads from the DB.
            sanitized_data = await prepare_flow_build_for_user(
                flow.data,
                is_superuser=current_user.is_superuser,
            )
            if sanitized_data is not None:
                data = FlowDataRequest(
                    nodes=sanitized_data.get("nodes", []),
                    edges=sanitized_data.get("edges", []),
                    viewport=sanitized_data.get("viewport"),
                )
    except CatalogPolicyIdentityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CustomComponentValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # v1.build, not "playground": the canvas moved to POST /api/v2/workflows and the frontend
    # has no reference to this route left (15 hits for api/v2/workflows, 0 for api/v1/build).
    # What still arrives here is direct API callers and voice, so labelling it playground would
    # attribute IDE traffic to a route the IDE no longer uses. The playground label is derived
    # from the agui wire protocol on the v2 stream instead.
    #
    # Still a default rather than the truth for every caller: voice reaches this same function
    # through build_flow_and_stream and binds its own protocol first, which wins.
    with execution_protocol("v1.build"):
        job_id = await start_flow_build(
            flow_id=flow_id,
            provider_policy_flow=flow,
            background_tasks=background_tasks,
            inputs=inputs,
            data=data,
            files=files,
            stop_component_id=stop_component_id,
            start_component_id=start_component_id,
            log_builds=log_builds,
            current_user=current_user,
            queue_service=queue_service,
            flow_name=flow_name,
            source_flow_owner_id=flow.user_id,
            expose_error_details=flow.user_id == current_user.id,
        )
    await _register_job_owner_or_cancel(queue_service, job_id, current_user.id)

    # This is required to support FE tests - we need to be able to set the event delivery to direct
    if event_delivery != EventDeliveryType.DIRECT:
        return {"job_id": job_id}
    return await get_flow_events_response(
        job_id=job_id,
        queue_service=queue_service,
        event_delivery=event_delivery,
    )


@router.get("/build/{job_id}/events")
async def get_build_events(
    job_id: str,
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
    current_user: CurrentActiveUser,
    *,
    event_delivery: EventDeliveryType = EventDeliveryType.STREAMING,
):
    """Get events for a specific build job.

    Requires authentication and ownership verification. A job owner is registered
    when build_flow is called; if a registered owner does not match the requesting
    user the endpoint returns 404 to avoid leaking job existence.
    Jobs started via build_public_tmp have no registered owner and remain accessible
    to any authenticated user.
    """
    await _verify_job_ownership(job_id, current_user, queue_service)
    return await get_flow_events_response(
        job_id=job_id,
        queue_service=queue_service,
        event_delivery=event_delivery,
    )


@router.post(
    "/build/{job_id}/cancel",
    response_model=CancelFlowResponse,
)
async def cancel_build(
    job_id: str,
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
    current_user: CurrentActiveUser,
):
    """Cancel a specific build job.

    Requires authentication and ownership verification to prevent a user from
    aborting another user's running build (DoS via job cancellation).
    Jobs with no registered owner (build_public_tmp) are accessible to any
    authenticated user, consistent with get_build_events.
    """
    await _verify_job_ownership(job_id, current_user, queue_service)
    try:
        # Cancel the flow build and check if it was successful
        cancellation_success = await cancel_flow_build(job_id=job_id, queue_service=queue_service)

        if cancellation_success:
            # Cancellation succeeded or wasn't needed
            return CancelFlowResponse(success=True, message="Flow build cancelled successfully")
        # Cancellation was attempted but failed
        return CancelFlowResponse(success=False, message="Failed to cancel flow build")
    except asyncio.CancelledError:
        # If CancelledError reaches here, it means the task was not successfully cancelled
        await logger.aerror(f"Failed to cancel flow build for job_id {job_id} (CancelledError caught)")
        return CancelFlowResponse(success=False, message="Failed to cancel flow build")
    except ValueError as exc:
        # Job not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobQueueNotFoundError as exc:
        await logger.aerror(f"Job not found: {job_id}. Error: {exc!s}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {exc!s}") from exc
    except Exception as exc:
        # Any other unexpected error
        await logger.aexception(f"Error cancelling flow build for job_id {job_id}: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/build/{flow_id}/vertices/{vertex_id}", deprecated=True, include_in_schema=False)
async def build_vertex(
    *,
    flow_id: uuid.UUID,
    vertex_id: str,
    background_tasks: BackgroundTasks,
    inputs: Annotated[InputValueRequest | None, Body(embed=True)] = None,
    files: list[str] | None = None,
    current_user: CurrentActiveUser,
) -> VertexBuildResponse:
    """Build a vertex instead of the entire graph.

    Args:
        flow_id (str): The ID of the flow.
        vertex_id (str): The ID of the vertex to build.
        background_tasks (BackgroundTasks): The background tasks dependency.
        inputs (Optional[InputValueRequest], optional): The input values for the vertex. Defaults to None.
        files (List[str], optional): The files to use. Defaults to None.
        current_user (Any, optional): The current user dependency. Defaults to Depends(get_current_active_user).

    Returns:
        VertexBuildResponse: The response containing the built vertex information.

    Raises:
        HTTPException: If there is an error building the vertex.

    """
    # This deprecated editor route is owner-only because its graph cache is
    # keyed by flow UUID rather than execution principal.
    async with session_scope() as authz_session:
        stmt = select(Flow).where(Flow.id == flow_id).where(Flow.user_id == current_user.id)
        flow = (await authz_session.exec(stmt)).first()
    if not flow:
        raise HTTPException(status_code=404, detail=f"Flow with id {flow_id} not found")
    await ensure_flow_permission(
        current_user,
        FlowAction.EXECUTE,
        flow_id=flow_id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )

    sanitized_data = await _trusted_stored_graph(flow.data, is_superuser=current_user.is_superuser)

    chat_service = get_chat_service()
    telemetry_service = get_telemetry_service()
    flow_id_str = str(flow_id)

    next_runnable_vertices = []
    top_level_vertices = []
    start_time = time.perf_counter()
    error_message = None
    run_id = None
    try:
        graph: Graph = await chat_service.get_cache(flow_id_str)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Graph not found") from exc

    try:
        cache = await chat_service.get_cache(flow_id_str)
        cached_graph = None if isinstance(cache, CacheMiss) else cache.get("result")
        # This seam is incremental: it is called once per vertex and carries built state in
        # the cache between calls. The policy hands back a copy on EVERY request from a
        # non-superuser, so rebuilding on that alone discarded the previous vertex's result
        # and the next one reported its upstream as unbuilt. Rebuild only when the cached
        # compilation did not come from this copy — which still covers the case the rebuild
        # exists for, a graph compiled while the policy was off.
        needs_initialize_run = True
        if sanitized_data is not None and not _compiled_from(cached_graph, sanitized_data):
            # Graph CONSTRUCTION binds the provider scope too, not just execution.
            with scoped_model_provider_policy_for_flow(
                flow,
                user_id=current_user.id,
                is_superuser=bool(current_user.is_superuser),
            ):
                graph = await build_and_cache_graph_from_data(
                    flow_id=flow_id_str,
                    chat_service=chat_service,
                    graph_data=sanitized_data,
                )
            run_id = str(uuid.uuid4())
            graph.set_run_id(run_id)
        elif cached_graph is None:
            # If there's no cache
            await logger.awarning(f"No cache found for {flow_id_str}. Building graph starting at {vertex_id}")
            with scoped_model_provider_policy_for_flow(
                flow,
                user_id=current_user.id,
                is_superuser=bool(current_user.is_superuser),
            ):
                async with session_scope() as session:
                    graph = await build_graph_from_db(
                        flow_id=flow_id,
                        session=session,
                        chat_service=chat_service,
                    )
            run_id = str(uuid.uuid4())
            graph.set_run_id(run_id)
            # build_graph_from_db initializes the run itself.
            needs_initialize_run = False
        else:
            graph = cached_graph
        try:
            _validate_graph_for_execution(graph)
        except HTTPException:
            await _clear_invalid_graph_cache(chat_service, flow_id_str)
            raise
        if needs_initialize_run:
            with scoped_model_provider_policy_for_flow(
                flow,
                user_id=current_user.id,
                is_superuser=bool(current_user.is_superuser),
            ):
                await graph.initialize_run()
            run_id = graph.run_id
        vertex = graph.get_vertex(vertex_id)

        try:
            lock = chat_service.async_cache_locks[flow_id_str]
            with scoped_model_provider_policy_for_flow(
                flow,
                user_id=current_user.id,
                is_superuser=bool(current_user.is_superuser),
            ):
                vertex_build_result = await graph.build_vertex(
                    vertex_id=vertex_id,
                    user_id=str(current_user.id),
                    inputs_dict=inputs.model_dump() if inputs else {},
                    files=files,
                    get_cache=chat_service.get_cache,
                    set_cache=chat_service.set_cache,
                )
            result_dict = vertex_build_result.result_dict
            params = vertex_build_result.params
            valid = vertex_build_result.valid
            artifacts = vertex_build_result.artifacts
            next_runnable_vertices = await graph.get_next_runnable_vertices(lock, vertex=vertex, cache=False)
            top_level_vertices = graph.get_top_level_vertices(next_runnable_vertices)
            result_data_response = ResultDataResponse.model_validate(result_dict, from_attributes=True)
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, ComponentBuildError):
                params = exc.message
                tb = exc.formatted_traceback
            else:
                tb = traceback.format_exc()
                await logger.aexception("Error building Component")
                params = format_exception_message(exc)
            message = {"errorMessage": params, "stackTrace": tb}
            valid = False
            error_message = params
            output_label = vertex.outputs[0]["name"] if vertex.outputs else "output"
            outputs = {output_label: OutputValue(message=message, type="error")}
            result_data_response = ResultDataResponse(results={}, outputs=outputs)
            artifacts = {}
            background_tasks.add_task(graph.end_all_traces_in_context(error=exc))
            # If there's an error building the vertex
            # we need to clear the cache
            await chat_service.clear_cache(flow_id_str)

        result_data_response.message = artifacts

        # Log the vertex build
        if not vertex.will_stream:
            background_tasks.add_task(
                log_vertex_build,
                flow_id=flow_id_str,
                vertex_id=vertex_id,
                valid=valid,
                params=params,
                data=result_data_response,
                artifacts=artifacts,
            )

        timedelta = time.perf_counter() - start_time

        duration = format_elapsed_time(timedelta)
        result_data_response.duration = duration
        result_data_response.timedelta = timedelta
        vertex.add_build_time(timedelta)
        inactivated_vertices = list(graph.inactivated_vertices)
        graph.reset_inactivated_vertices()
        graph.reset_activated_vertices()

        await chat_service.set_cache(flow_id_str, graph)

        # graph.stop_vertex tells us if the user asked
        # to stop the build of the graph at a certain vertex
        # if it is in next_vertices_ids, we need to remove other
        # vertices from next_vertices_ids
        if graph.stop_vertex and graph.stop_vertex in next_runnable_vertices:
            next_runnable_vertices = [graph.stop_vertex]

        if not graph.run_manager.vertices_being_run and not next_runnable_vertices:
            background_tasks.add_task(graph.end_all_traces_in_context())

        build_response = VertexBuildResponse(
            inactivated_vertices=list(set(inactivated_vertices)),
            next_vertices_ids=list(set(next_runnable_vertices)),
            top_level_vertices=list(set(top_level_vertices)),
            valid=valid,
            params=params,
            id=vertex.id,
            data=result_data_response,
        )
        background_tasks.add_task(
            telemetry_service.log_package_component,
            ComponentPayload(
                component_name=vertex_id.split("-")[0],
                component_id=vertex_id,
                component_seconds=int(time.perf_counter() - start_time),
                component_success=valid,
                component_error_message=error_message,
                component_run_id=run_id,
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        background_tasks.add_task(
            telemetry_service.log_package_component,
            ComponentPayload(
                component_name=vertex_id.split("-")[0],
                component_id=vertex_id,
                component_seconds=int(time.perf_counter() - start_time),
                component_success=False,
                component_error_message=str(exc),
                component_run_id=run_id if "run_id" in locals() else None,
            ),
        )
        if isinstance(exc, CustomComponentValidationError):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await logger.aexception("Error building Component")
        message = parse_exception(exc)
        raise HTTPException(status_code=500, detail=message) from exc

    return build_response


async def _stream_vertex(flow_id: str, vertex_id: str, chat_service: ChatService, graph: Graph | None = None):
    try:
        if graph is None:
            try:
                cache = await chat_service.get_cache(flow_id)
            except Exception as exc:  # noqa: BLE001
                await logger.aexception("Error building Component")
                yield str(StreamData(event="error", data={"error": str(exc)}))
                return

            if isinstance(cache, CacheMiss):
                # If there's no cache
                msg = f"No cache found for {flow_id}."
                await logger.aerror(msg)
                yield str(StreamData(event="error", data={"error": msg}))
                return
            graph = cache.get("result")

        try:
            _validate_graph_for_execution(graph)
        except HTTPException as exc:
            await _clear_invalid_graph_cache(chat_service, flow_id)
            graph = None
            yield str(StreamData(event="error", data={"error": exc.detail}))
            return

        try:
            vertex: InterfaceVertex = graph.get_vertex(vertex_id)
        except Exception as exc:  # noqa: BLE001
            await logger.aexception("Error building Component")
            yield str(StreamData(event="error", data={"error": str(exc)}))
            return

        if not hasattr(vertex, "stream"):
            msg = f"Vertex {vertex_id} does not support streaming"
            await logger.aerror(msg)
            yield str(StreamData(event="error", data={"error": msg}))
            return

        if isinstance(vertex.built_result, str) and vertex.built_result:
            stream_data = StreamData(
                event="message",
                data={"message": f"Streaming vertex {vertex_id}"},
            )
            yield str(stream_data)
            stream_data = StreamData(
                event="message",
                data={"chunk": vertex.built_result},
            )
            yield str(stream_data)

        elif not vertex.frozen or not vertex.built:
            await logger.adebug(f"Streaming vertex {vertex_id}")
            stream_data = StreamData(
                event="message",
                data={"message": f"Streaming vertex {vertex_id}"},
            )
            yield str(stream_data)
            try:
                async for chunk in vertex.stream():
                    stream_data = StreamData(
                        event="message",
                        data={"chunk": chunk},
                    )
                    yield str(stream_data)
            except Exception as exc:  # noqa: BLE001
                await logger.aexception("Error building Component")
                exc_message = parse_exception(exc)
                if exc_message == "The message must be an iterator or an async iterator.":
                    exc_message = "This stream has already been closed."
                yield str(StreamData(event="error", data={"error": exc_message}))
        elif vertex.result is not None:
            stream_data = StreamData(
                event="message",
                data={"chunk": vertex.built_result},
            )
            yield str(stream_data)
        else:
            msg = f"No result found for vertex {vertex_id}"
            await logger.aerror(msg)
            yield str(StreamData(event="error", data={"error": msg}))
            return
    finally:
        await logger.adebug("Closing stream")
        if graph:
            await chat_service.set_cache(flow_id, graph)
        yield str(StreamData(event="close", data={"message": "Stream closed"}))


async def _stream_vertex_with_provider_scope(
    flow_id: str,
    vertex_id: str,
    chat_service: ChatService,
    graph: Graph | None,
    flow: Flow,
    current_user: User,
):
    """Retain the trusted flow scope while the response generator is consumed."""
    with scoped_model_provider_policy_for_flow(
        flow,
        user_id=current_user.id,
        is_superuser=bool(current_user.is_superuser),
    ):
        async for event in _stream_vertex(flow_id, vertex_id, chat_service, graph):
            yield event


@router.get(
    "/build/{flow_id}/{vertex_id}/stream",
    response_class=StreamingResponse,
    deprecated=True,
    include_in_schema=False,
)
async def build_vertex_stream(
    flow_id: uuid.UUID,
    vertex_id: str,
    current_user: CurrentActiveUser,
):
    """Build a vertex instead of the entire graph.

    This function is responsible for building a single vertex instead of the entire graph.
    It takes the `flow_id` and `vertex_id` as required parameters, and an optional `session_id`.
    It also depends on the `ChatService` and `SessionService` services.

    If `session_id` is not provided, it retrieves the graph from the cache using the `chat_service`.
    If `session_id` is provided, it loads the session data using the `session_service`.

    Once the graph is obtained, it retrieves the specified vertex using the `vertex_id`.
    If the vertex does not support streaming, an error is raised.
    If the vertex has a built result, it sends the result as a chunk.
    If the vertex is not frozen or not built, it streams the vertex data.
    If the vertex has a result, it sends the result as a chunk.
    If none of the above conditions are met, an error is raised.

    If any exception occurs during the process, an error message is sent.
    Finally, the stream is closed.

    Returns:
        A `StreamingResponse` object with the streamed vertex data in text/event-stream format.

    Raises:
        HTTPException: If an error occurs while building the vertex.
    """
    # This deprecated editor route is owner-only. Authorize before constructing
    # the streaming response because the cache is keyed only by flow UUID.
    async with session_scope() as session:
        stmt = select(Flow).where(Flow.id == flow_id).where(Flow.user_id == current_user.id)
        flow = (await session.exec(stmt)).first()
    if not flow:
        raise HTTPException(status_code=404, detail=f"Flow with id {flow_id} not found")
    await ensure_flow_permission(
        current_user,
        FlowAction.EXECUTE,
        flow_id=flow_id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )

    chat_service = get_chat_service()
    try:
        cache = await chat_service.get_cache(str(flow_id))
        if isinstance(cache, CacheMiss):
            graph = None
        else:
            graph = cache.get("result")
            try:
                _validate_graph_for_execution(graph)
            except HTTPException:
                await _clear_invalid_graph_cache(chat_service, str(flow_id))
                raise
        return StreamingResponse(
            _stream_vertex_with_provider_scope(
                str(flow_id),
                vertex_id,
                chat_service,
                graph,
                flow,
                current_user,
            ),
            media_type="text/event-stream",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error building Component") from exc


async def build_flow_and_stream(flow_id, inputs, background_tasks, current_user):
    queue_service = get_queue_service()
    build_response = await build_flow(
        flow_id=flow_id,
        inputs=inputs,
        background_tasks=background_tasks,
        current_user=current_user,
        queue_service=queue_service,
        event_delivery=EventDeliveryType.STREAMING,
    )
    job_id = build_response["job_id"]
    return await get_flow_events_response(
        job_id=job_id,
        queue_service=queue_service,
        event_delivery=EventDeliveryType.STREAMING,
    )


# NOTE: ``validate_public_files`` (the canonical helper that mitigates
# GHSA-rcjh-r59h-gq37) was moved to ``langflow.api.utils.flow_utils`` so v2's
# public workflow endpoint shares the exact same gate. Keep it imported above.


@router.post("/build_public_tmp/{flow_id}/flow")
async def build_public_tmp(
    *,
    background_tasks: LimitVertexBuildBackgroundTasks,
    flow_id: uuid.UUID,
    inputs: Annotated[InputValueRequest | None, Body(embed=True)] = None,
    files: list[str] | None = None,
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    log_builds: bool | None = True,
    flow_name: str | None = None,
    request: Request,
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
    authenticated_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    event_delivery: EventDeliveryType = EventDeliveryType.POLLING,
):
    """Build a public flow without requiring authentication.

    This endpoint is specifically for public flows that don't require authentication.
    It uses a client_id cookie to create a deterministic flow ID for tracking purposes.

    Security Note:
    - The 'data' parameter is NOT accepted to prevent flow definition tampering
    - Public flows must execute the stored flow definition only
    - The flow definition is always loaded from the database
    - Caller-supplied 'inputs.session' is namespaced under the (client_id,
      flow_id) virtual flow ID so an unauthenticated caller cannot address a
      session that lives outside its own namespace (CVE-2026-33017)

    The endpoint:
    1. Verifies the requested flow is marked as public in the database
    2. Creates a deterministic UUID based on client_id and flow_id
    3. Uses a stable anonymous principal to build the flow
    4. Always loads the flow definition from the database

    Requirements:
    - The flow must be marked as PUBLIC in the database
    - The request must include a client_id cookie

    Args:
        flow_id: UUID of the public flow to build
        background_tasks: Background tasks manager
        inputs: Optional input values for the flow
        files: Optional files to include
        stop_component_id: Optional ID of component to stop at
        start_component_id: Optional ID of component to start from
        log_builds: Whether to log the build process
        flow_name: Optional name for the flow
        request: FastAPI request object (needed for cookie access)
        queue_service: Queue service for job management
        authenticated_user: Optional authenticated user (resolved from cookie/token if present)
        event_delivery: Optional event delivery type - default is streaming

    Returns:
        Dict with job_id that can be used to poll for build status
    """
    settings = get_settings_service().settings
    if settings.rate_limit_enabled:
        check_rate_limit(
            request,
            scope=f"public-build:{flow_id}",
            limit_per_minute=settings.public_flow_rate_limit_per_minute,
        )

    try:
        # Reject caller-supplied file references that aren't scoped to this
        # public flow's own storage namespace. Done before any flow lookup so
        # malformed requests fail fast and don't touch the DB.
        validate_public_files(files, flow_id)

        # Verify the direct-link grant and derive the anonymous runtime principal.
        client_id = request.cookies.get("client_id")
        # Only use authenticated user_id when auto-login is disabled.
        # When AUTO_LOGIN=TRUE, the frontend uses client_id for UUID v5,
        # so the backend must match to avoid flow_id mismatch.
        auth_settings = get_settings_service().auth_settings
        authenticated_user_id = authenticated_user.id if authenticated_user and not auth_settings.AUTO_LOGIN else None
        public_user, new_flow_id = await verify_public_flow_and_get_user(
            flow_id=flow_id,
            client_id=client_id,
            authenticated_user_id=authenticated_user_id,
            request_host=request.url.hostname,
        )

        # Defends CVE-2026-33017: scope caller session into the (client_id, flow_id) namespace.
        if inputs is not None and inputs.session is not None:
            scoped_session = scope_session_to_namespace(inputs.session, str(new_flow_id))
            if scoped_session != inputs.session:
                inputs = inputs.model_copy(update={"session": scoped_session})

        # Validate the stored flow data after the public-access boundary. Public flows never
        # accept client-supplied data; the two checks below harden the unauthenticated build
        # path (report H1-3754930) and only ever run server-trusted code for anonymous visitors.
        sanitized_public_data: dict | None = None
        async with session_scope() as session:
            flow = await session.get(Flow, flow_id)
            if flow is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PUBLIC_FLOW_NOT_FOUND_DETAIL)
            # The admission helper authorizes its own DB snapshot. Reauthorize the
            # exact snapshot detached below so a concurrent revoke/private transition
            # cannot leave us executing a later, unchecked definition.
            await authorize_public_flow_access(
                flow=flow,
                action=PublicResourceAction.EXECUTE,
                request_host=request.url.hostname,
                session=session,
            )
            if flow.data is None:
                msg = "Public flow has no executable data"
                raise ValueError(msg)

            # The default anonymous build path sanitizes component code directly
            # and therefore does not call validate_flow_for_current_settings.
            # Enforce the exact catalog snapshot after the public-access check
            # and before any graph is queued or built. The explicit public-custom
            # opt-in already runs the unified validator inside prepare_public_flow_build.
            if not settings.allow_public_custom_components:
                validate_catalog_policy_for_flow(flow.data)
            # Block unauthenticated builds of flows that run arbitrary code
            # (Python interpreter/REPL, legacy Python Code Structured tool,
            # Smart Transform lambda) or invoke another saved flow (Run Flow,
            # Sub Flow, Flow as Tool — the transitive case). Without this, any
            # public flow containing such a component is an unauthenticated
            # server-side code-execution primitive (report H1-3754930).
            validate_public_flow_no_code_execution(flow.data)
            # Substitute the server's trusted code into every known component and
            # reject unrecognized custom components, so anonymous visitors only ever
            # run server code. The explicit allow_public_custom_components opt-in
            # preserves approved stored code, but the detached graph is still
            # secret-scrubbed below before it reaches the executor.
            prepared_public_data = await prepare_public_flow_build(flow.data)
            sanitized_public_data = strip_secret_field_values(
                prepared_public_data if prepared_public_data is not None else flow.data
            )

        # flow_id=new_flow_id for tracking/sessions/messages (virtual, per-user isolation).
        # source_flow_id=flow_id to load the actual flow data from the database.
        # Anonymous shared-link traffic on the v1 build route. Named for the route rather than
        # the surface, for the same reason as v1.build above; the v2 public stream is v2.public.
        with execution_protocol("v1.build.public"):
            job_id = await start_flow_build(
                flow_id=new_flow_id,
                source_flow_id=flow_id,
                provider_policy_flow=flow,
                background_tasks=background_tasks,
                inputs=inputs,
                # Build from a detached server-sanitized graph. The default path also
                # substitutes trusted code; the explicit custom-component opt-in keeps
                # approved code but still strips every persisted secret-bearing field.
                data=(
                    FlowDataRequest(
                        nodes=sanitized_public_data.get("nodes", []),
                        edges=sanitized_public_data.get("edges", []),
                        viewport=sanitized_public_data.get("viewport"),
                    )
                    if sanitized_public_data is not None
                    else None
                ),
                files=files,
                stop_component_id=stop_component_id,
                start_component_id=start_component_id,
                log_builds=log_builds or False,
                current_user=public_user,
                queue_service=queue_service,
                flow_name=flow_name or f"{authenticated_user_id or client_id}_{flow_id}",
                source_flow_owner_id=flow.user_id,
                expose_error_details=False,
            )
        # Gate the public events/cancel endpoints to jobs that were actually
        # started through this public build path, preventing unauthenticated
        # callers from reading or cancelling private-flow builds by job_id.
        await queue_service.register_public_job(job_id)
    except TweakRefusedError:
        # Let the app-level handler return the documented structured 422.
        raise
    except CatalogPolicyIdentityUnavailableError as exc:
        await logger.awarning("Public flow component identities are temporarily unavailable")
        raise HTTPException(status_code=503, detail=PUBLIC_CATALOG_POLICY_UNAVAILABLE_MESSAGE) from exc
    except CustomComponentValidationError as exc:
        await logger.awarning(f"Public flow validation failed: {exc}")
        raise HTTPException(status_code=400, detail="This flow cannot be executed.") from exc
    except JobQueueBackendUnavailableError as exc:
        # The public marker could not be persisted to the shared (Redis) backend.
        # Returning the job_id anyway would hand back an un-shareable id: on a
        # multi-worker deployment every other worker's public events/cancel
        # endpoints would 404 it. Cancel the just-started build (best-effort) and
        # surface a clean 503 instead of a 500 / an unusable job_id.
        try:
            await queue_service.cancel_job(job_id)
        except Exception as cancel_exc:  # noqa: BLE001
            await logger.awarning(
                f"Failed to cancel public job {job_id} after marker persistence failed: {cancel_exc!r}"
            )
        raise HTTPException(status_code=503, detail="Public flow service is temporarily unavailable.") from exc
    except ValueError as exc:
        await logger.awarning(f"Public flow validation failed: {exc}")
        raise HTTPException(status_code=400, detail="This flow cannot be executed.") from exc
    except Exception as exc:
        await logger.aexception("Error building public flow")
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="Flow execution failed.") from exc
    if event_delivery != EventDeliveryType.DIRECT:
        return {"job_id": job_id}
    return await get_flow_events_response(
        job_id=job_id,
        queue_service=queue_service,
        event_delivery=event_delivery,
    )


async def _assert_public_job(job_id: str, queue_service: JobQueueService) -> None:
    """Raise HTTP 404 if job_id was not registered through the public build endpoint.

    Prevents unauthenticated callers from reading or cancelling private-flow
    builds by guessing or leaking a job_id.

    Why 404 not 403: returning 403 would confirm the job exists under a different
    access tier, leaking information about private builds. 404 is neutral.
    """
    if not await queue_service.is_public_job_async(job_id):
        # Static detail — do not reflect job_id back; avoid confirming which IDs exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


_PUBLIC_JOB_NOT_FOUND_DETAIL = "Job not found"
_PUBLIC_EVENTS_UNAVAILABLE_DETAIL = "Public flow events are unavailable."
_PUBLIC_CANCEL_FAILED_DETAIL = "Public flow cancellation failed."


@router.get("/build_public_tmp/{job_id}/events")
async def get_build_events_public(
    job_id: str,
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
    *,
    event_delivery: EventDeliveryType = EventDeliveryType.STREAMING,
):
    """Get events for a public flow build job.

    This endpoint does not require authentication, matching the public build endpoint.
    It is used by the shareable playground to consume build events.
    """
    await _assert_public_job(job_id, queue_service)
    try:
        return await get_flow_events_response(
            job_id=job_id,
            queue_service=queue_service,
            event_delivery=event_delivery,
        )
    except HTTPException as exc:
        # The shared authenticated helper carries backend exception text in
        # ``detail``. Preserve it in server logs, but public callers get only a
        # fixed response. A 404 stays indistinguishable from the registry gate.
        await logger.aerror(
            f"Public flow events failed for job_id {job_id}: status={exc.status_code} detail={exc.detail!r}"
        )
        detail = (
            _PUBLIC_JOB_NOT_FOUND_DETAIL
            if exc.status_code == status.HTTP_404_NOT_FOUND
            else _PUBLIC_EVENTS_UNAVAILABLE_DETAIL
        )
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc
    except Exception as exc:
        await logger.aexception(f"Public flow events failed for job_id {job_id}: {exc!r}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_PUBLIC_EVENTS_UNAVAILABLE_DETAIL,
        ) from exc


@router.post(
    "/build_public_tmp/{job_id}/cancel",
    response_model=CancelFlowResponse,
)
async def cancel_build_public(
    job_id: str,
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
):
    """Cancel a public flow build job.

    This endpoint does not require authentication, matching the public build endpoint.
    It is used by the shareable playground to cancel builds.
    """
    await _assert_public_job(job_id, queue_service)
    try:
        cancellation_success = await cancel_flow_build(job_id=job_id, queue_service=queue_service)

        if cancellation_success:
            return CancelFlowResponse(success=True, message="Flow build cancelled successfully")
        return CancelFlowResponse(success=False, message="Failed to cancel flow build")
    except asyncio.CancelledError as exc:
        await logger.aerror(f"Failed to cancel public flow build for job_id {job_id}: {exc!r}")
        raise
    except ValueError as exc:
        await logger.awarning(f"Public flow cancellation could not find job_id {job_id}: {exc!r}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_PUBLIC_JOB_NOT_FOUND_DETAIL) from exc
    except JobQueueNotFoundError as exc:
        await logger.aerror(f"Public job not found: {job_id}. Error: {exc!s}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_PUBLIC_JOB_NOT_FOUND_DETAIL) from exc
    except Exception as exc:
        await logger.aexception(f"Error cancelling public flow build for job_id {job_id}: {exc!r}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_PUBLIC_CANCEL_FAILED_DETAIL,
        ) from exc
