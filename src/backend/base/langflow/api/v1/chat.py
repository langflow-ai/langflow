import time
import uuid
from typing import TYPE_CHECKING, Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from langflow.api.utils import (
    build_and_cache_graph_from_data,
    build_and_cache_graph_from_db,
    format_elapsed_time,
    format_exception_message,
    get_top_level_vertices,
    parse_exception,
)
from langflow.api.v1.schemas import (
    FlowDataRequest,
    InputValueRequest,
    ResultDataResponse,
    StreamData,
    VertexBuildResponse,
    VerticesOrderResponse,
)
from langflow.schema.schema import Log
from langflow.services.auth.utils import get_current_active_user
from langflow.services.chat.service import ChatService
from langflow.services.deps import get_chat_service, get_session, get_session_service
from langflow.services.monitor.utils import log_vertex_build

if TYPE_CHECKING:
    from langflow.graph.vertex.types import InterfaceVertex
    from langflow.services.session.service import SessionService

router = APIRouter(tags=["Chat"])


async def try_running_celery_task(vertex, user_id):
    # Try running the task in celery
    # and set the task_id to the local vertex
    # if it fails, run the task locally
    try:
        from langflow.worker import build_vertex

        task = build_vertex.delay(vertex)
        vertex.task_id = task.id
    except Exception as exc:
        logger.debug(f"Error running task in celery: {exc}")
        vertex.task_id = None
        await vertex.build(user_id=user_id)
    return vertex


@router.post("/build/{flow_id}/vertices", response_model=VerticesOrderResponse)
async def retrieve_vertices_order(
    flow_id: uuid.UUID,
    data: Optional[Annotated[Optional[FlowDataRequest], Body(embed=True)]] = None,
    stop_component_id: Optional[str] = None,
    start_component_id: Optional[str] = None,
    chat_service: "ChatService" = Depends(get_chat_service),
    session=Depends(get_session),
):
    """
    Retrieve the vertices order for a given flow.

    Args:
        flow_id (str): The ID of the flow.
        data (Optional[FlowDataRequest], optional): The flow data. Defaults to None.
        stop_component_id (str, optional): The ID of the stop component. Defaults to None.
        start_component_id (str, optional): The ID of the start component. Defaults to None.
        chat_service (ChatService, optional): The chat service dependency. Defaults to Depends(get_chat_service).
        session (Session, optional): The session dependency. Defaults to Depends(get_session).

    Returns:
        VerticesOrderResponse: The response containing the ordered vertex IDs and the run ID.

    Raises:
        HTTPException: If there is an error checking the build status.
    """
    try:
        flow_id_str = str(flow_id)
        # First, we need to check if the flow_id is in the cache
        if not data:
            graph = await build_and_cache_graph_from_db(flow_id=flow_id_str, session=session, chat_service=chat_service)
        else:
            graph = await build_and_cache_graph_from_data(
                flow_id=flow_id_str, graph_data=data.model_dump(), chat_service=chat_service
            )
        graph.validate_stream()
        if stop_component_id or start_component_id:
            try:
                first_layer = graph.sort_vertices(stop_component_id, start_component_id)
            except Exception as exc:
                logger.error(exc)
                first_layer = graph.sort_vertices()
        else:
            first_layer = graph.sort_vertices()
        # When we send vertices to the frontend
        # we need to remove them from the predecessors
        # so they are not considered for building again
        # which duplicates the results
        for vertex_id in first_layer:
            graph.remove_from_predecessors(vertex_id)

        # Now vertices is a list of lists
        # We need to get the id of each vertex
        # and return the same structure but only with the ids
        run_id = uuid.uuid4()
        graph.set_run_id(run_id)
        vertices_to_run = list(graph.vertices_to_run) + get_top_level_vertices(graph, graph.vertices_to_run)
        return VerticesOrderResponse(ids=first_layer, run_id=run_id, vertices_to_run=vertices_to_run)

    except Exception as exc:
        if "stream or streaming set to True" in str(exc):
            raise HTTPException(status_code=400, detail=str(exc))
        logger.error(f"Error checking build status: {exc}")
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/build/{flow_id}/vertices/{vertex_id}")
async def build_vertex(
    flow_id: uuid.UUID,
    vertex_id: str,
    background_tasks: BackgroundTasks,
    inputs: Annotated[Optional[InputValueRequest], Body(embed=True)] = None,
    files: Optional[list[str]] = None,
    chat_service: "ChatService" = Depends(get_chat_service),
    current_user=Depends(get_current_active_user),
):
    """Build a vertex instead of the entire graph.

    Args:
        flow_id (str): The ID of the flow.
        vertex_id (str): The ID of the vertex to build.
        background_tasks (BackgroundTasks): The background tasks object for logging.
        inputs (Optional[InputValueRequest], optional): The input values for the vertex. Defaults to None.
        chat_service (ChatService, optional): The chat service dependency. Defaults to Depends(get_chat_service).
        current_user (Any, optional): The current user dependency. Defaults to Depends(get_current_active_user).

    Returns:
        VertexBuildResponse: The response containing the built vertex information.

    Raises:
        HTTPException: If there is an error building the vertex.

    """
    flow_id_str = str(flow_id)

    next_runnable_vertices = []
    top_level_vertices = []
    try:
        start_time = time.perf_counter()
        cache = await chat_service.get_cache(flow_id_str)
        if not cache:
            # If there's no cache
            logger.warning(f"No cache found for {flow_id_str}. Building graph starting at {vertex_id}")
            graph = await build_and_cache_graph_from_db(
                flow_id=flow_id_str, session=next(get_session()), chat_service=chat_service
            )
        else:
            graph = cache.get("result")
        vertex = graph.get_vertex(vertex_id)

        try:
            lock = chat_service._cache_locks[flow_id_str]
            (
                next_runnable_vertices,
                top_level_vertices,
                result_dict,
                params,
                valid,
                artifacts,
                vertex,
            ) = await graph.build_vertex(
                lock=lock,
                chat_service=chat_service,
                vertex_id=vertex_id,
                user_id=current_user.id,
                inputs_dict=inputs.model_dump() if inputs else {},
                files=files,
            )
            log_obj = Log(message=vertex.artifacts_raw, type=vertex.artifacts_type)
            result_data_response = ResultDataResponse(**result_dict.model_dump())

        except Exception as exc:
            logger.exception(f"Error building vertex: {exc}")
            params = format_exception_message(exc)
            valid = False
            log_obj = Log(message=params, type="error")
            result_data_response = ResultDataResponse(results={})
            artifacts = {}
            # If there's an error building the vertex
            # we need to clear the cache
            await chat_service.clear_cache(flow_id_str)

        result_data_response.message = artifacts
        result_data_response.logs.append(log_obj)

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
        inactivated_vertices = None
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

        build_response = VertexBuildResponse(
            inactivated_vertices=inactivated_vertices,
            next_vertices_ids=next_runnable_vertices,
            top_level_vertices=top_level_vertices,
            valid=valid,
            params=params,
            id=vertex.id,
            data=result_data_response,
        )
        return build_response
    except Exception as exc:
        logger.error(f"Error building vertex: {exc}")
        logger.exception(exc)
        message = parse_exception(exc)
        raise HTTPException(status_code=500, detail=message) from exc


@router.get("/build/{flow_id}/{vertex_id}/stream", response_class=StreamingResponse)
async def build_vertex_stream(
    flow_id: uuid.UUID,
    vertex_id: str,
    session_id: Optional[str] = None,
    chat_service: "ChatService" = Depends(get_chat_service),
    session_service: "SessionService" = Depends(get_session_service),
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
        flow_id_str = str(flow_id)

        async def stream_vertex():
            try:
                if not session_id:
                    cache = await chat_service.get_cache(flow_id_str)
                    if not cache:
                        # If there's no cache
                        raise ValueError(f"No cache found for {flow_id_str}.")
                    else:
                        graph = cache.get("result")
                else:
                    session_data = await session_service.load_session(session_id, flow_id=flow_id_str)
                    graph, artifacts = session_data if session_data else (None, None)
                    if not graph:
                        raise ValueError(f"No graph found for {flow_id_str}.")

                vertex: "InterfaceVertex" = graph.get_vertex(vertex_id)
                if not hasattr(vertex, "stream"):
                    raise ValueError(f"Vertex {vertex_id} does not support streaming")
                if isinstance(vertex._built_result, str) and vertex._built_result:
                    stream_data = StreamData(
                        event="message",
                        data={"message": f"Streaming vertex {vertex_id}"},
                    )
                    yield str(stream_data)
                    stream_data = StreamData(
                        event="message",
                        data={"chunk": vertex._built_result},
                    )
                    yield str(stream_data)

                elif not vertex.frozen or not vertex._built:
                    logger.debug(f"Streaming vertex {vertex_id}")
                    stream_data = StreamData(
                        event="message",
                        data={"message": f"Streaming vertex {vertex_id}"},
                    )
                    yield str(stream_data)
                    async for chunk in vertex.stream():
                        stream_data = StreamData(
                            event="message",
                            data={"chunk": chunk},
                        )
                        yield str(stream_data)
                elif vertex.result is not None:
                    stream_data = StreamData(
                        event="message",
                        data={"chunk": vertex._built_result},
                    )
                    yield str(stream_data)
                else:
                    raise ValueError(f"No result found for vertex {vertex_id}")

            except Exception as exc:
                logger.exception(f"Error building vertex: {exc}")
                exc_message = parse_exception(exc)
                if exc_message == "The message must be an iterator or an async iterator.":
                    exc_message = "This stream has already been closed."
                yield str(StreamData(event="error", data={"error": exc_message}))
            finally:
                logger.debug("Closing stream")
                yield str(StreamData(event="close", data={"message": "Stream closed"}))

        return StreamingResponse(stream_vertex(), media_type="text/event-stream")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error building vertex") from exc
