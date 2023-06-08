from fastapi import (
    APIRouter,
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
