import json
from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketException,
    status,
)
from fastapi.responses import StreamingResponse
from langflow.api.v1.schemas import BuiltResponse, InitResponse

from langflow.chat.manager import ChatManager
from langflow.graph.graph_map import GraphMap
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
                yield f"data: {json.dumps({'error': error_message})}\n\n"
                return

            graph_data = flow_data_store[flow_id].get("data")

            if not graph_data:
                error_message = "No data provided"
                yield f"data: {json.dumps({'error': error_message})}\n\n"
                return

            logger.debug("Building langchain object")
            graph_map = GraphMap(graph_data, is_first_message=True)
            number_of_nodes = len(graph_map.sorted_vertices)
            for i, vertex in enumerate(graph_map.generator_build(), 1):
                if vertex._built:
                    continue
                log_dict = {
                    "log": f"Building Vertex {vertex}",
                    "progress": round(i / number_of_nodes, 2),
                }
                yield build_stream_string("data", log_dict)
                for edge in vertex.edges:
                    if edge.is_fulfilled:
                        continue
                    try:
                        await edge.fulfill()

                    except Exception as exc:
                        params = str(exc)
                        valid = False

                await vertex.build()
                params = vertex._built_object_repr()
                valid = True
                logger.debug(
                    f"Building Vertex {params[:50]}{'...' if len(params) > 50 else ''}"
                )
                response = {
                    "valid": valid,
                    "params": params,
                    "id": vertex.id,
                }

                yield build_stream_string("data", response)

            chat_manager.set_cache(flow_id, graph_map)
        except Exception as exc:
            logger.exception("Error while building the flow: %s", exc)
            yield build_stream_string("error", {"error": str(exc)})
        finally:
            yield build_stream_string("data", final_response)

    try:
        return StreamingResponse(event_stream(flow_id), media_type="text/event-stream")
    except Exception as exc:
        logger.error(exc)
        raise HTTPException(status_code=500, detail=str(exc))


def build_stream_string(str_type: str, data_dict: dict):
    json_string = json.dumps(data_dict)
    return f"{str_type}: {json_string}\n\n"
