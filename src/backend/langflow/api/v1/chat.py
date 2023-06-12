import json
from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from fastapi.responses import StreamingResponse, JSONResponse

from langflow.chat.manager import ChatManager
from langflow.graph.graph.base import Graph
from langflow.utils.logger import logger

router = APIRouter()
chat_manager = ChatManager()
flow_data_store = {}


@router.websocket("/chat/{client_id}")
async def websocket_endpoint(client_id: str, websocket: WebSocket):
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
    except WebSocketDisconnect as exc:
        logger.error(exc)
        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE, reason=str(exc))


@router.post("/build/init")
async def init_build(graph_data: dict):
    """Initialize the build by storing graph data and returning a unique session ID."""

    flow_id = graph_data.get("id")

    flow_data_store[flow_id] = graph_data

    return JSONResponse(content={"flowId": flow_id})


@router.get("/build/stream/{flow_id}", response_class=StreamingResponse)
async def stream_build(flow_id: str):
    """Stream the build process based on stored flow data."""

    async def event_stream(flow_id):
        if flow_id not in flow_data_store:
            error_message = "Invalid session ID"
            yield f"data: {json.dumps({'error': error_message})}\n\n"
            return

        graph_data = flow_data_store[flow_id].get("data")

        if not graph_data:
            error_message = "No data provided"
            yield f"data: {json.dumps({'error': error_message})}\n\n"
            return

        try:
            logger.debug("Building langchain object")
            graph = Graph.from_payload(graph_data)
            for node_repr, node_id in graph.generator_build():
                logger.debug(
                    f"Building node {node_repr[:50]}{'...' if len(node_repr) > 50 else ''}"
                )
                response = json.dumps(
                    {
                        "valid": True,
                        "params": node_repr,
                        "id": node_id,
                    }
                )
                yield f"data: {response}\n\n"  # SSE format

            chat_manager.set_cache(flow_id, graph.build())
            final_response = json.dumps({"end_of_stream": True})
            yield f"data: {final_response}\n\n"  # SSE format

        except Exception as exc:
            logger.exception(exc)
            error_response = json.dumps({"valid": False, "params": str(exc)})
            yield f"data: {error_response}\n\n"  # SSE format

    return StreamingResponse(event_stream(flow_id), media_type="text/event-stream")
