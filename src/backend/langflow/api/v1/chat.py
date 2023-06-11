from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)

from langflow.chat.manager import ChatManager
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


@router.post("/build/{client_id}")
async def post_build(client_id: str, graph_data: dict):
    """Build langchain object from data_graph."""
    try:
        if chat_manager.build(client_id, graph_data.get("data")):
            return {"message": "Build successful"}
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
