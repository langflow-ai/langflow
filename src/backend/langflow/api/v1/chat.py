from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketException,
    status,
)
from fastapi.responses import StreamingResponse
from langflow.api.v1.schemas import BuiltResponse, InitResponse, StreamData

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
            message = "Please, build the flow before sending messages"
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=message)
    except WebSocketException as exc:
        logger.error(exc)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(exc))


@router.post("/build/init", response_model=InitResponse, status_code=201)
async def init_build(graph_data: dict):
    """Initialize the build by storing graph data and returning a unique session ID."""

    try:
        flow_id = graph_data.get("id")
        if flow_id is None:
            raise ValueError("No ID provided")
        flow_data_store[flow_id] = graph_data

        return InitResponse(flowId=flow_id)
    except Exception as exc:
        logger.error(exc)
        return HTTPException(status_code=500, detail=str(exc))


@router.get("/build/{flow_id}/status", response_model=BuiltResponse)
async def build_status(flow_id: str):
    """Check the flow_id is in the flow_data_store."""
    try:
        built = flow_id in flow_data_store and not isinstance(
            flow_data_store[flow_id], dict
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
        try:
            if flow_id not in flow_data_store:
                error_message = "Invalid session ID"
                yield str(StreamData(event="error", data={"error": error_message}))
                return

            graph_data = flow_data_store[flow_id].get("data")

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
                        f"Building node {params[:50]}{'...' if len(params) > 50 else ''}"
                    )
                except Exception as exc:
                    params = str(exc)
                    valid = False

                response = {
                    "valid": valid,
                    "params": params,
                    "id": vertex.id,
                    "progress": round(i / number_of_nodes, 2),
                }

                yield str(StreamData(event="message", data=response))

            chat_manager.set_cache(flow_id, graph.build())
        except Exception as exc:
            logger.error("Error while building the flow: %s", exc)
            yield str(StreamData(event="error", data={"error": str(exc)}))
        finally:
            yield str(StreamData(event="message", data=final_response))

    try:
        return StreamingResponse(event_stream(flow_id), media_type="text/event-stream")
    except Exception as exc:
        logger.error(exc)
        raise HTTPException(status_code=500, detail=str(exc))
