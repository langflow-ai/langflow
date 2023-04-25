from fastapi import APIRouter, WebSocket

from langflow.api.chat_manager import ChatManager
from langflow.utils.logger import logger

router = APIRouter()
chat_manager = ChatManager()


@router.websocket("/chat/{client_id}")
async def websocket_endpoint(client_id: str, websocket: WebSocket):
    """Websocket endpoint for chat."""
    try:
        await chat_manager.handle_websocket(client_id, websocket)
    except Exception as e:
        # Log stack trace
        logger.exception(e)
        raise e
