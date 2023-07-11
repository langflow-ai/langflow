from fastapi import APIRouter, HTTPException, WebSocket, WebSocketException, status
from fastapi.responses import StreamingResponse
from langflow.api.utils import build_input_keys_response
from langflow.api.v1.schemas import BuildStatus, BuiltResponse, InitResponse, StreamData

from langflow.chat.manager import ChatManager
from langflow.graph.graph.base import Graph
from langflow.utils.logger import logger
from cachetools import LRUCache

router = APIRouter(tags=["Chat"])
chat_manager = ChatManager()
flow_data_store: LRUCache = LRUCache(maxsize=10)


@router.websocket("/chat/{client_id}")
async def chat(client_id: str, websocket: WebSocket):
    """Websocket endpoint for chat."""
    try:
        if client_id in chat_manager.in_memory_cache:
            await chat_manager.handle_websocket(client_id, websocket)
        else:
            # We accept the connection but close it immediately
            # if the flow is not built yet
            await websocket.accept()
            message = "Please, build the flow before sending messages"
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=message)
    except WebSocketException as exc:
        logger.error(exc)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(exc))


@router.post("/build/init/{flow_id}", response_model=InitResponse, status_code=201)
async def init_build(graph_data: dict, flow_id: str):
    """Initialize the build by storing graph data and returning a unique session ID."""

    try:
        if flow_id is None:
            raise ValueError("No ID provided")
        # Check if already building
        if (
            flow_id in flow_data_store
            and flow_data_store[flow_id]["status"] == BuildStatus.IN_PROGRESS
        ):
            return InitResponse(flowId=flow_id)

        # Delete from cache if already exists
        if flow_id in chat_manager.in_memory_cache:
            with chat_manager.in_memory_cache._lock:
                chat_manager.in_memory_cache.delete(flow_id)
                logger.debug(f"Deleted flow {flow_id} from cache")
        flow_data_store[flow_id] = {
            "graph_data": graph_data,
            "status": BuildStatus.STARTED,
        }

        return InitResponse(flowId=flow_id)
    except Exception as exc:
        logger.error(exc)
        return HTTPException(status_code=500, detail=str(exc))


@router.get("/build/{flow_id}/status", response_model=BuiltResponse)
async def build_status(flow_id: str):
    """Check the flow_id is in the flow_data_store."""
    try:
        built = (
            flow_id in flow_data_store
            and flow_data_store[flow_id]["status"] == BuildStatus.SUCCESS
        )

        return BuiltResponse(
            built=built,
        )

    except Exception as exc:
        logger.error(exc)
        return HTTPException(status_code=500, detail=str(exc))


@router.get("/build/stream/{flow_id}", response_class=StreamingResponse)
async def stream_build(flow_id: str):
    """Stream the build process based on stored flow data."""

    async def event_stream(flow_id):
        final_response = {"end_of_stream": True}
        artifacts = {}
        try:
            if flow_id not in flow_data_store:
                error_message = "Invalid session ID"
                yield str(StreamData(event="error", data={"error": error_message}))
                return

            if flow_data_store[flow_id].get("status") == BuildStatus.IN_PROGRESS:
                error_message = "Already building"
                yield str(StreamData(event="error", data={"error": error_message}))
                return

            graph_data = flow_data_store[flow_id].get("graph_data")

            if not graph_data:
                error_message = "No data provided"
                yield str(StreamData(event="error", data={"error": error_message}))
                return

            logger.debug("Building langchain object")
            try:
                # Some error could happen when building the graph
                graph = Graph.from_payload(graph_data)
            except Exception as exc:
                logger.exception(exc)
                error_message = str(exc)
                yield str(StreamData(event="error", data={"error": error_message}))
                return

            number_of_nodes = len(graph.nodes)
            flow_data_store[flow_id]["status"] = BuildStatus.IN_PROGRESS

            for i, vertex in enumerate(graph.generator_build(), 1):
                try:
                    log_dict = {
                        "log": f"Building node {vertex.vertex_type}",
                    }
                    yield str(StreamData(event="log", data=log_dict))
                    vertex.build()
                    params = vertex._built_object_repr()
                    valid = True
                    logger.debug(
                        f"Building node {str(params)[:50]}{'...' if len(str(params)) > 50 else ''}"
                    )
                    if vertex.artifacts:
                        # The artifacts will be prompt variables
                        # passed to build_input_keys_response
                        # to set the input_keys values
                        artifacts.update(vertex.artifacts)
                except Exception as exc:
                    params = str(exc)
                    valid = False
                    flow_data_store[flow_id]["status"] = BuildStatus.FAILURE

                response = {
                    "valid": valid,
                    "params": params,
                    "id": vertex.id,
                    "progress": round(i / number_of_nodes, 2),
                }

                yield str(StreamData(event="message", data=response))

            langchain_object = graph.build()
            # Now we  need to check the input_keys to send them to the client
            if hasattr(langchain_object, "input_keys"):
                input_keys_response = build_input_keys_response(
                    langchain_object, artifacts
                )
            else:
                input_keys_response = {
                    "input_keys": {},
                    "memory_keys": [],
                    "handle_keys": [],
                }
            yield str(StreamData(event="message", data=input_keys_response))

            chat_manager.set_cache(flow_id, langchain_object)
            # We need to reset the chat history
            chat_manager.chat_history.empty_history(flow_id)
            flow_data_store[flow_id]["status"] = BuildStatus.SUCCESS
        except Exception as exc:
            logger.exception(exc)
            logger.error("Error while building the flow: %s", exc)
            flow_data_store[flow_id]["status"] = BuildStatus.FAILURE
            yield str(StreamData(event="error", data={"error": str(exc)}))
        finally:
            yield str(StreamData(event="message", data=final_response))

    try:
        return StreamingResponse(event_stream(flow_id), media_type="text/event-stream")
    except Exception as exc:
        logger.error(exc)
        raise HTTPException(status_code=500, detail=str(exc))
