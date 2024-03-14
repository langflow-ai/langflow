from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketException, status
from fastapi.responses import StreamingResponse
from langflow_base.api.utils import build_input_keys_response
from langflow_base.api.v1.schemas import BuildStatus, BuiltResponse, InitResponse, StreamData
from langflow_base.graph.graph.base import Graph
from langflow_base.services.auth.utils import get_current_active_user, get_current_user_by_jwt
from langflow_base.services.cache.service import BaseCacheService
from langflow_base.services.cache.utils import update_build_status
from langflow_base.services.chat.service import ChatService
from langflow_base.services.deps import get_cache_service, get_chat_service, get_session
from loguru import logger

router = APIRouter(tags=["Chat"])


async def try_running_celery_task(vertex, user_id):
    # Try running the task in celery
    # and set the task_id to the local vertex
    # if it fails, run the task locally
    try:
        from langflow_base.worker import build_vertex

        task = build_vertex.delay(vertex)
        vertex.task_id = task.id
    except Exception as exc:
        logger.debug(f"Error running task in celery: {exc}")
        vertex.task_id = None
        await vertex.build(user_id=user_id)
    return vertex


@router.get("/build/{flow_id}/vertices", response_model=VerticesOrderResponse)
async def get_vertices(
    flow_id: str,
    stop_component_id: Optional[str] = None,
    start_component_id: Optional[str] = None,
    chat_service: "ChatService" = Depends(get_chat_service),
    session=Depends(get_session),
):
    """Check the flow_id is in the flow_data_store."""
    try:
        # First, we need to check if the flow_id is in the cache
        graph = None
        if cache := await chat_service.get_cache(flow_id):
            graph = cache.get("result")
        graph = await build_and_cache_graph(flow_id, session, chat_service, graph)
        if stop_component_id or start_component_id:
            try:
                vertices = graph.sort_vertices(stop_component_id, start_component_id)
            except Exception as exc:
                logger.error(exc)
                vertices = graph.sort_vertices()
        else:
            vertices = graph.sort_vertices()

        # Now vertices is a list of lists
        # We need to get the id of each vertex
        # and return the same structure but only with the ids
        run_id = uuid.uuid4()
        graph.set_run_id(run_id)
        return VerticesOrderResponse(ids=vertices, run_id=run_id)

    except Exception as exc:
        logger.error(f"Error checking build status: {exc}")
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/build/{flow_id}/vertices/{vertex_id}")
async def build_vertex(
    flow_id: str,
    vertex_id: str,
    background_tasks: BackgroundTasks,
    inputs: Annotated[Optional[InputValueRequest], Body(embed=True)] = None,
    chat_service: "ChatService" = Depends(get_chat_service),
    current_user=Depends(get_current_active_user),
):
    """Build a vertex instead of the entire graph."""

    start_time = time.perf_counter()
    next_vertices_ids = []
    try:
        start_time = time.perf_counter()
        cache = await chat_service.get_cache(flow_id)
        if not cache:
            # If there's no cache
            logger.warning(f"No cache found for {flow_id}. Building graph starting at {vertex_id}")
            graph = await build_and_cache_graph(flow_id=flow_id, session=next(get_session()), chat_service=chat_service)
        else:
            graph = cache.get("result")
        result_data_response = ResultDataResponse(results={})
        duration = ""

        vertex = graph.get_vertex(vertex_id)
        try:
            if not vertex.frozen or not vertex._built:
                inputs_dict = inputs.model_dump() if inputs else {}
                await vertex.build(user_id=current_user.id, inputs=inputs_dict)

            if vertex.result is not None:
                params = vertex._built_object_repr()
                valid = True
                result_dict = vertex.result
                artifacts = vertex.artifacts
            else:
                raise ValueError(f"No result found for vertex {vertex_id}")
            async with chat_service._cache_locks[flow_id] as lock:
                graph.remove_from_predecessors(vertex_id)
                next_vertices_ids = vertex.successors_ids
                next_vertices_ids = [v for v in next_vertices_ids if graph.should_run_vertex(v)]
                await chat_service.set_cache(flow_id=flow_id, data=graph, lock=lock)

            result_data_response = ResultDataResponse(**result_dict.model_dump())

        except Exception as exc:
            logger.exception(f"Error building vertex: {exc}")
            params = format_exception_message(exc)
            valid = False
            result_data_response = ResultDataResponse(results={})
            artifacts = {}
            # If there's an error building the vertex
            # we need to clear the cache
            await chat_service.clear_cache(flow_id)

        # Log the vertex build
        if not vertex.will_stream:
            background_tasks.add_task(
                log_vertex_build,
                flow_id=flow_id,
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
        await chat_service.set_cache(flow_id, graph)

        # graph.stop_vertex tells us if the user asked
        # to stop the build of the graph at a certain vertex
        # if it is in next_vertices_ids, we need to remove other
        # vertices from next_vertices_ids
        if graph.stop_vertex and graph.stop_vertex in next_vertices_ids:
            next_vertices_ids = [graph.stop_vertex]

        build_response = VertexBuildResponse(
            inactivated_vertices=inactivated_vertices,
            next_vertices_ids=next_vertices_ids,
            valid=valid,
            params=params,
            id=vertex.id,
            data=result_data_response,
        )
        return build_response
    except Exception as exc:
        logger.error(f"Error building vertex: {exc}")
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Now onto an endpoint that is an SSE endpoint
# it will receive a component_id and a flow_id
#
@router.get("/build/{flow_id}/{vertex_id}/stream", response_class=StreamingResponse)
async def build_vertex_stream(
    flow_id: str,
    vertex_id: str,
    session_id: Optional[str] = None,
    chat_service: "ChatService" = Depends(get_chat_service),
    session_service: "SessionService" = Depends(get_session_service),
):
    """Build a vertex instead of the entire graph."""
    try:

        async def stream_vertex():
            try:
                if not session_id:
                    cache = chat_service.get_cache(flow_id)
                    if not cache:
                        # If there's no cache
                        raise ValueError(f"No cache found for {flow_id}.")
                    else:
                        graph = cache.get("result")
                else:
                    session_data = await session_service.load_session(session_id, flow_id=flow_id)
                    graph, artifacts = session_data if session_data else (None, None)
                    if not graph:
                        raise ValueError(f"No graph found for {flow_id}.")

                vertex: "ChatVertex" = graph.get_vertex(vertex_id)
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
                logger.error(f"Error building vertex: {exc}")
                yield str(StreamData(event="error", data={"error": str(exc)}))
            finally:
                logger.debug("Closing stream")
                yield str(StreamData(event="close", data={"message": "Stream closed"}))

        return StreamingResponse(stream_vertex(), media_type="text/event-stream")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error building vertex") from exc
