import time
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketException,
    status,
)
from loguru import logger
from sqlmodel import Session

from langflow.api.utils import build_and_cache_graph, format_elapsed_time
from langflow.api.v1.schemas import (
    ResultData,
    VertexBuildResponse,
    VerticesOrderResponse,
)
from langflow.graph.graph.base import Graph
from langflow.services.auth.utils import (
    get_current_active_user,
    get_current_user_for_websocket,
)
from langflow.services.chat.service import ChatService
from langflow.services.deps import get_chat_service, get_session
from langflow.services.monitor.utils import log_vertex_build

router = APIRouter(tags=["Chat"])


@router.websocket("/chat/{client_id}")
async def chat(
    client_id: str,
    websocket: WebSocket,
    db: Session = Depends(get_session),
    chat_service: "ChatService" = Depends(get_chat_service),
):
    """Websocket endpoint for chat."""
    try:
        user = await get_current_user_for_websocket(websocket, db)
        await websocket.accept()
        if not user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized"
            )
        elif not user.is_active:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized"
            )

        if client_id in chat_service.cache_service:
            await chat_service.handle_websocket(client_id, websocket)
        else:
            # We accept the connection but close it immediately
            # if the flow is not built yet
            message = "Please, build the flow before sending messages"
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=message)
    except WebSocketException as exc:
        logger.error(f"Websocket exrror: {exc}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(exc))
    except Exception as exc:
        logger.error(f"Error in chat websocket: {exc}")
        messsage = exc.detail if isinstance(exc, HTTPException) else str(exc)
        if "Could not validate credentials" in str(exc):
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized"
            )
        else:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=messsage)


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


@router.get("/build/{flow_id}/vertices", response_model=VerticesOrderResponse)
async def get_vertices(
    flow_id: str,
    component_id: Optional[str] = None,
    chat_service: "ChatService" = Depends(get_chat_service),
    session=Depends(get_session),
):
    """Check the flow_id is in the flow_data_store."""
    try:
        # First, we need to check if the flow_id is in the cache
        graph = None
        if cache := chat_service.get_cache(flow_id):
            graph: Graph = cache.get("result")
        graph = build_and_cache_graph(flow_id, session, chat_service, graph)
        if component_id:
            try:
                vertices = graph.sort_vertices(component_id)
            except Exception as exc:
                logger.error(exc)
                vertices = graph.sort_vertices()
        else:
            vertices = graph.sort_vertices()

        # Now vertices is a list of lists
        # We need to get the id of each vertex
        # and return the same structure but only with the ids
        return VerticesOrderResponse(ids=vertices)

    except Exception as exc:
        logger.error(f"Error checking build status: {exc}")
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/build/{flow_id}/vertices/{vertex_id}")
async def build_vertex(
    flow_id: str,
    vertex_id: str,
    background_tasks: BackgroundTasks,
    chat_service: "ChatService" = Depends(get_chat_service),
    current_user=Depends(get_current_active_user),
):
    """Build a vertex instead of the entire graph."""
    start_time = time.perf_counter()
    try:
        start_time = time.perf_counter()
        cache = chat_service.get_cache(flow_id)
        if not cache:
            # If there's no cache
            logger.warning(
                f"No cache found for {flow_id}. Building graph starting at {vertex_id}"
            )
            graph = build_and_cache_graph(
                flow_id=flow_id, session=next(get_session()), chat_service=chat_service
            )
        else:
            graph = cache.get("result")
        result_dict = {}
        duration = ""

        vertex = graph.get_vertex(vertex_id)
        try:
            if not vertex.pinned or not vertex._built:
                await vertex.build(user_id=current_user.id)
                params = vertex._built_object_repr()
                valid = True
                result_dict = vertex.get_built_result()
                # We need to set the artifacts to pass information
                # to the frontend
                vertex.set_artifacts()
                artifacts = vertex.artifacts
                result_dict = ResultData(
                    results=result_dict,
                    artifacts=artifacts,
                )
                vertex.set_result(result_dict)
            elif vertex.result is not None:
                params = vertex._built_object_repr()
                valid = True
                result_dict = vertex.result
                artifacts = vertex.artifacts
            else:
                raise ValueError(f"No result found for vertex {vertex_id}")
            chat_service.set_cache(flow_id, graph)
        except Exception as exc:
            params = str(exc)
            valid = False
            result_dict = ResultData(results={})
            artifacts = {}
            # If there's an error building the vertex
            # we need to clear the cache
            chat_service.clear_cache(flow_id)

        # Log the vertex build
        background_tasks.add_task(
            log_vertex_build,
            flow_id=flow_id,
            vertex_id=vertex_id,
            valid=valid,
            params=params,
            data=result_dict,
            artifacts=artifacts,
        )

        timedelta = time.perf_counter() - start_time
        duration = format_elapsed_time(timedelta)
        result_dict.duration = duration
        result_dict.timedelta = timedelta
        vertex.add_build_time(timedelta)

        return VertexBuildResponse(
            valid=valid,
            params=params,
            id=vertex.id,
            data=result_dict,
        )
    except Exception as exc:
        logger.error(f"Error building vertex: {exc}")
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
