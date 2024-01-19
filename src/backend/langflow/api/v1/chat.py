import time

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketException, status,Body
from fastapi.responses import StreamingResponse
from langflow.api.utils import build_input_keys_response, format_elapsed_time
from langflow.api.v1.schemas import BuildStatus, BuiltResponse, InitResponse, ResultDict, StreamData, VerticesOrderResponse
from langflow.graph.vertex.base import StatelessVertex
from langflow.processing.process import process_tweaks_on_graph
from langflow.services.database.models.flow.flow import Flow
from langflow.graph.graph.base import Graph
from langflow.services.auth.utils import get_current_active_user, get_current_user_by_jwt
from langflow.services.cache.service import BaseCacheService
from langflow.services.cache.utils import update_build_status
from langflow.services.chat.service import ChatService
from langflow.services.deps import get_cache_service, get_chat_service, get_session
from loguru import logger
from sqlmodel import Session

router = APIRouter(tags=["Chat"])


@router.websocket("/chat/{client_id}")
async def chat(
    client_id: str,
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_session),
    chat_service: "ChatService" = Depends(get_chat_service),
):
    """Websocket endpoint for chat."""
    try:
        user = await get_current_user_by_jwt(token, db)
        await websocket.accept()
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        if not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")

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
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        else:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=messsage)


@router.post("/build/init/{flow_id}", response_model=InitResponse, status_code=201)
async def init_build(
    graph_data: dict,
    flow_id: str,
    current_user=Depends(get_current_active_user),
    chat_service: "ChatService" = Depends(get_chat_service),
    cache_service: "BaseCacheService" = Depends(get_cache_service),
):
    """Initialize the build by storing graph data and returning a unique session ID."""
    try:
        if flow_id is None:
            raise ValueError("No ID provided")
        # Check if already building
        if (
            flow_id in cache_service
            and isinstance(cache_service[flow_id], dict)
            and cache_service[flow_id].get("status") == BuildStatus.IN_PROGRESS
        ):
            return InitResponse(flowId=flow_id)

        # Delete from cache if already exists
        if flow_id in chat_service.cache_service:
            chat_service.cache_service.delete(flow_id)
            logger.debug(f"Deleted flow {flow_id} from cache")
        cache_service[flow_id] = {
            "graph_data": graph_data,
            "status": BuildStatus.STARTED,
            "user_id": current_user.id,
        }

        return InitResponse(flowId=flow_id)
    except Exception as exc:
        logger.error(f"Error initializing build: {exc}")
        return HTTPException(status_code=500, detail=str(exc))


@router.get("/build/{flow_id}/status", response_model=BuiltResponse)
async def build_status(flow_id: str, cache_service: "BaseCacheService" = Depends(get_cache_service)):
    """Check the flow_id is in the cache_service."""
    try:
        built = flow_id in cache_service and cache_service[flow_id]["status"] == BuildStatus.SUCCESS

        return BuiltResponse(
            built=built,
        )

    except Exception as exc:
        logger.error(f"Error checking build status: {exc}")
        return HTTPException(status_code=500, detail=str(exc))


@router.get("/build/stream/{flow_id}", response_class=StreamingResponse)
async def stream_build(
    flow_id: str,
    chat_service: "ChatService" = Depends(get_chat_service),
    cache_service: "BaseCacheService" = Depends(get_cache_service),
):
    """Stream the build process based on stored flow data."""

    async def event_stream(flow_id):
        final_response = {"end_of_stream": True}
        artifacts = {}
        flow_cache = cache_service[flow_id]
        flow_cache = flow_cache if isinstance(flow_cache, dict) else {}
        try:
            if flow_id not in cache_service:
                error_message = "Invalid session ID"
                yield str(StreamData(event="error", data={"error": error_message}))
                return

            if flow_cache.get("status") == BuildStatus.IN_PROGRESS:
                error_message = "Already building"
                yield str(StreamData(event="error", data={"error": error_message}))
                return

            graph_data = flow_cache.get("graph_data")

            if not graph_data:
                error_message = "No data provided"
                yield str(StreamData(event="error", data={"error": error_message}))
                return

            logger.debug("Building langchain object")

            # Some error could happen when building the graph
            graph = Graph.from_payload(graph_data)

            number_of_nodes = len(graph.vertices)
            update_build_status(cache_service, flow_id, BuildStatus.IN_PROGRESS)
            time_elapsed = ""
            try:
                user_id = flow_cache["user_id"]
            except KeyError:
                logger.debug("No user_id found in cache_service")
                user_id = None
            for i, vertex in enumerate(graph.generator_build(), 1):
                start_time = time.perf_counter()
                try:
                    log_dict = {
                        "log": f"Building node {vertex.vertex_type}",
                    }
                    yield str(StreamData(event="log", data=log_dict))
                    if vertex.is_task:
                        vertex = await try_running_celery_task(vertex, user_id)
                    else:
                        await vertex.build(user_id=user_id)
                    time_elapsed = format_elapsed_time(time.perf_counter() - start_time)
                    params = vertex._built_object_repr()
                    valid = True

                    logger.debug(f"Building node {str(vertex.vertex_type)}")
                    logger.debug(f"Output: {params[:100]}{'...' if len(params) > 100 else ''}")
                    if vertex.artifacts:
                        # The artifacts will be prompt variables
                        # passed to build_input_keys_response
                        # to set the input_keys values
                        artifacts.update(vertex.artifacts)
                except Exception as exc:
                    logger.exception(exc)
                    params = str(exc)
                    valid = False
                    time_elapsed = format_elapsed_time(time.perf_counter() - start_time)
                    update_build_status(cache_service, flow_id, BuildStatus.FAILURE)

                vertex_id = vertex.parent_node_id if vertex.parent_is_top_level else vertex.id
                if vertex_id in graph.top_level_vertices:
                    response = {
                        "valid": valid,
                        "params": params,
                        "id": vertex_id,
                        "progress": round(i / number_of_nodes, 2),
                        "duration": time_elapsed,
                    }

                    yield str(StreamData(event="message", data=response))

            langchain_object = await graph.build()
            # Now we  need to check the input_keys to send them to the client
            if hasattr(langchain_object, "input_keys"):
                input_keys_response = build_input_keys_response(langchain_object, artifacts)
            else:
                input_keys_response = {
                    "input_keys": None,
                    "memory_keys": [],
                    "handle_keys": [],
                }
            yield str(StreamData(event="message", data=input_keys_response))
            chat_service.set_cache(flow_id, langchain_object)
            # We need to reset the chat history
            chat_service.chat_history.empty_history(flow_id)
            update_build_status(cache_service, flow_id, BuildStatus.SUCCESS)
        except Exception as exc:
            logger.exception(exc)
            logger.error("Error while building the flow: %s", exc)

            update_build_status(cache_service, flow_id, BuildStatus.FAILURE)
            yield str(StreamData(event="error", data={"error": str(exc)}))
        finally:
            yield str(StreamData(event="message", data=final_response))

    try:
        return StreamingResponse(event_stream(flow_id), media_type="text/event-stream")
    except Exception as exc:
        logger.error(f"Error streaming build: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


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
    chat_service: "ChatService" = Depends(get_chat_service),
    session=Depends(get_session),
):
    """Check the flow_id is in the flow_data_store."""
    try:
        flow: Flow = session.get(Flow, flow_id)
        if not flow:
            raise ValueError("Invalid flow ID")
        graph = Graph.from_payload(flow.data)
        chat_service.set_cache(flow_id, graph)
        vertices = graph.layered_topological_sort()
        # Now vertices is a list of lists
        # We need to get the id of each vertex
        # and return the same structure but only with the ids
        return VerticesOrderResponse(ids=vertices)

    except Exception as exc:
        logger.error(f"Error checking build status: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/build/{flow_id}/vertices/{vertex_id}")
async def build_vertex(
    flow_id: str,
    vertex_id: str,
    chat_service: "ChatService" = Depends(get_chat_service),
    # current_user=Depends(get_current_active_user),
    tweaks: dict = Body(None),
    inputs: dict = Body(None),
):
    """Build a vertex instead of the entire graph."""
    try:
        cache = chat_service.get_cache(flow_id)
        graph = cache.get("result")
        result_dict = {}
        if tweaks:
            graph = process_tweaks_on_graph(graph, tweaks)
        if not isinstance(graph, Graph):
            raise ValueError("Invalid graph")
        if not (vertex := graph.get_vertex(vertex_id)):
            raise ValueError("Invalid vertex")
        try:
            if isinstance(vertex, StatelessVertex) or not vertex._built:
                await vertex.build(user_id=None)
            params = vertex._built_object_repr()
            valid = True
            result_dict = vertex.get_built_result()
            # We need to set the artifacts to pass information
            # to the frontend
            vertex.set_artifacts()
            artifacts = vertex.artifacts
            result_dict = ResultDict(results=result_dict, artifacts=artifacts)
        except Exception as exc:
            params = str(exc)
            valid = False
            result_dict = ResultDict(results={})
            artifacts = {}
        chat_service.set_cache(flow_id, graph)

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
