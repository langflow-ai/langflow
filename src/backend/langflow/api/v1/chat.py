import json
from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from fastapi.responses import StreamingResponse

from langflow.chat.manager import ChatManager
from langflow.graph.graph.base import Graph
from langflow.utils.logger import logger

router = APIRouter()
chat_manager = ChatManager()


@router.websocket("/chat/{client_id}")
async def websocket_endpoint(client_id: str, websocket: WebSocket):
    """Websocket endpoint for chat."""
    try:
        await chat_manager.handle_websocket(client_id, websocket)
    except WebSocketException as exc:
        logger.error(exc)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(exc))
    except WebSocketDisconnect as exc:
        logger.error(exc)
        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE, reason=str(exc))


@router.post("/build/{client_id}", response_class=StreamingResponse)
async def stream_build(client_id: str, graph_data: dict):
    """Build langchain object from data_graph."""

    async def event_stream(graph_data):
        try:
            graph_data = graph_data.get("data")
            if not graph_data:
                raise HTTPException(status_code=400, detail="No data provided")

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

            chat_manager.set_cache(client_id, graph.build())

        except Exception as exc:
            logger.exception(exc)
            error_response = json.dumps(
                {"valid": False, "params": str(exc), "id": node_id}
            )
            yield f"data: {error_response}\n\n"  # SSE format

    return StreamingResponse(event_stream(graph_data), media_type="text/event-stream")
