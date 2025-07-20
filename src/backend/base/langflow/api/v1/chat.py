from __future__ import annotations

import asyncio
import time
import traceback
import uuid
from typing import TYPE_CHECKING, Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from loguru import logger

from langflow.api.build import (
    cancel_flow_build,
    get_flow_events_response,
    start_flow_build,
)
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
    verify_public_flow_and_get_user,
)
from langflow.api.v1.schemas import (
    CancelFlowResponse,
    FlowDataRequest,
    InputValueRequest,
    ResultDataResponse,
    StreamData,
    VertexBuildResponse,
    VerticesOrderResponse,
)
from langflow.exceptions.component import ComponentBuildError
from langflow.graph.graph.base import Graph
from langflow.graph.utils import log_vertex_build
from langflow.schema.schema import OutputValue
from langflow.services.cache.utils import CacheMiss
from langflow.services.chat.service import ChatService
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import (
    get_chat_service,
    get_queue_service,
    get_session,
    get_telemetry_service,
    session_scope,
)
from langflow.services.job_queue.service import JobQueueNotFoundError, JobQueueService
from langflow.services.telemetry.schema import ComponentPayload, PlaygroundPayload

if TYPE_CHECKING:
    from langflow.graph.vertex.vertex_types import InterfaceVertex

router = APIRouter(tags=["Chat"])


@router.post("/build/{flow_id}/vertices", deprecated=True)
async def retrieve_vertices_order(
    *,
    flow_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    data: Annotated[FlowDataRequest | None, Body(embed=True)] | None = None,
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    session: DbSession,
) -> VerticesOrderResponse:
    """Retrieve the vertices order for a given flow.

    Args:
        flow_id (str): The ID of the flow.
        background_tasks (BackgroundTasks): The background tasks.
        data (Optional[FlowDataRequest], optional): The flow data. Defaults to None.
        stop_component_id (str, optional): The ID of the stop component. Defaults to None.
        start_component_id (str, optional): The ID of the start component. Defaults to None.
        session (AsyncSession, optional): The session dependency.

    Returns:
        VerticesOrderResponse: The response containing the ordered vertex IDs and the run ID.

    Raises:
        HTTPException: If there is an error checking the build status.
    """
    chat_service = get_chat_service()
    telemetry_service = get_telemetry_service()
    start_time = time.perf_counter()
    components_count = None
    try:
        # First, we need to check if the flow_id is in the cache
        if not data:
            graph = await build_graph_from_db(flow_id=flow_id, session=session, chat_service=chat_service)
        else:
            graph = await build_and_cache_graph_from_data(
                flow_id=flow_id, graph_data=data.model_dump(), chat_service=chat_service
            )
        graph = graph.prepare(stop_component_id, start_component_id)

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
            ),
        )
        if "stream or streaming set to True" in str(exc):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        logger.exception("Error checking build status")
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
    # First verify the flow exists
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail=f"Flow with id {flow_id} not found")

    job_id = await start_flow_build(
        flow_id=flow_id,
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
    )

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
    *,
    event_delivery: EventDeliveryType = EventDeliveryType.STREAMING,
):
    """Get events for a specific build job."""
    return await get_flow_events_response(
        job_id=job_id,
        queue_service=queue_service,
        event_delivery=event_delivery,
    )


@router.post("/build/{job_id}/cancel", response_model=CancelFlowResponse)
async def cancel_build(
    job_id: str,
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
):
    """Cancel a specific build job."""
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
        logger.error(f"Failed to cancel flow build for job_id {job_id} (CancelledError caught)")
        return CancelFlowResponse(success=False, message="Failed to cancel flow build")
    except ValueError as exc:
        # Job not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobQueueNotFoundError as exc:
        logger.error(f"Job not found: {job_id}. Error: {exc!s}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {exc!s}") from exc
    except Exception as exc:
        # Any other unexpected error
        logger.exception(f"Error cancelling flow build for job_id {job_id}: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/build/{flow_id}/vertices/{vertex_id}", deprecated=True)
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
    chat_service = get_chat_service()
    telemetry_service = get_telemetry_service()
    flow_id_str = str(flow_id)

    next_runnable_vertices = []
    top_level_vertices = []
    start_time = time.perf_counter()
    error_message = None
    try:
        graph: Graph = await chat_service.get_cache(flow_id_str)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Graph not found") from exc

    try:
        cache = await chat_service.get_cache(flow_id_str)
        if isinstance(cache, CacheMiss):
            # If there's no cache
            logger.warning(f"No cache found for {flow_id_str}. Building graph starting at {vertex_id}")
            graph = await build_graph_from_db(
                flow_id=flow_id,
                session=await anext(get_session()),
                chat_service=chat_service,
            )
        else:
            graph = cache.get("result")
            await graph.initialize_run()
        vertex = graph.get_vertex(vertex_id)

        try:
            lock = chat_service.async_cache_locks[flow_id_str]
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
                logger.exception("Error building Component")
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
                component_seconds=int(time.perf_counter() - start_time),
                component_success=valid,
                component_error_message=error_message,
            ),
        )
    except Exception as exc:
        background_tasks.add_task(
            telemetry_service.log_package_component,
            ComponentPayload(
                component_name=vertex_id.split("-")[0],
                component_seconds=int(time.perf_counter() - start_time),
                component_success=False,
                component_error_message=str(exc),
            ),
        )
        logger.exception("Error building Component")
        message = parse_exception(exc)
        raise HTTPException(status_code=500, detail=message) from exc

    return build_response


async def _stream_vertex(flow_id: str, vertex_id: str, chat_service: ChatService):
    graph = None
    try:
        try:
            cache = await chat_service.get_cache(flow_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error building Component")
            yield str(StreamData(event="error", data={"error": str(exc)}))
            return

        if isinstance(cache, CacheMiss):
            # If there's no cache
            msg = f"No cache found for {flow_id}."
            logger.error(msg)
            yield str(StreamData(event="error", data={"error": msg}))
            return
        else:
            graph = cache.get("result")

        try:
            vertex: InterfaceVertex = graph.get_vertex(vertex_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error building Component")
            yield str(StreamData(event="error", data={"error": str(exc)}))
            return

        if not hasattr(vertex, "stream"):
            msg = f"Vertex {vertex_id} does not support streaming"
            logger.error(msg)
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
            logger.debug(f"Streaming vertex {vertex_id}")
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
                logger.exception("Error building Component")
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
            logger.error(msg)
            yield str(StreamData(event="error", data={"error": msg}))
            return
    finally:
        logger.debug("Closing stream")
        if graph:
            await chat_service.set_cache(flow_id, graph)
        yield str(StreamData(event="close", data={"message": "Stream closed"}))


@router.get(
    "/build/{flow_id}/{vertex_id}/stream",
    response_class=StreamingResponse,
    deprecated=True,
)
async def build_vertex_stream(
    flow_id: uuid.UUID,
    vertex_id: str,
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
    try:
        return StreamingResponse(
            _stream_vertex(str(flow_id), vertex_id, get_chat_service()),
            media_type="text/event-stream",
        )
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


@router.post("/build_public_tmp/{flow_id}/flow")
async def build_public_tmp(
    *,
    background_tasks: LimitVertexBuildBackgroundTasks,
    flow_id: uuid.UUID,
    inputs: Annotated[InputValueRequest | None, Body(embed=True)] = None,
    data: Annotated[FlowDataRequest | None, Body(embed=True)] = None,
    files: list[str] | None = None,
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    log_builds: bool | None = True,
    flow_name: str | None = None,
    request: Request,
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
    event_delivery: EventDeliveryType = EventDeliveryType.POLLING,
):
    """Build a public flow without requiring authentication.

    This endpoint is specifically for public flows that don't require authentication.
    It uses a client_id cookie to create a deterministic flow ID for tracking purposes.

    The endpoint:
    1. Verifies the requested flow is marked as public in the database
    2. Creates a deterministic UUID based on client_id and flow_id
    3. Uses the flow owner's permissions to build the flow

    Requirements:
    - The flow must be marked as PUBLIC in the database
    - The request must include a client_id cookie

    Args:
        flow_id: UUID of the public flow to build
        background_tasks: Background tasks manager
        inputs: Optional input values for the flow
        data: Optional flow data
        files: Optional files to include
        stop_component_id: Optional ID of component to stop at
        start_component_id: Optional ID of component to start from
        log_builds: Whether to log the build process
        flow_name: Optional name for the flow
        request: FastAPI request object (needed for cookie access)
        queue_service: Queue service for job management
        event_delivery: Optional event delivery type - default is streaming

    Returns:
        Dict with job_id that can be used to poll for build status
    """
    try:
        # Verify this is a public flow and get the associated user
        client_id = request.cookies.get("client_id")
        owner_user, new_flow_id = await verify_public_flow_and_get_user(flow_id=flow_id, client_id=client_id)

        # Start the flow build using the new flow ID
        job_id = await start_flow_build(
            flow_id=new_flow_id,
            background_tasks=background_tasks,
            inputs=inputs,
            data=data,
            files=files,
            stop_component_id=stop_component_id,
            start_component_id=start_component_id,
            log_builds=log_builds or False,
            current_user=owner_user,
            queue_service=queue_service,
            flow_name=flow_name or f"{client_id}_{flow_id}",
        )
    except Exception as exc:
        logger.exception("Error building public flow")
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if event_delivery != EventDeliveryType.DIRECT:
        return {"job_id": job_id}
    return await get_flow_events_response(
        job_id=job_id,
        queue_service=queue_service,
        event_delivery=event_delivery,
    )
