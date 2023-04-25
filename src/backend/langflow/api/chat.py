from fastapi import APIRouter, WebSocket

from langflow.api.chat_manager import ChatManager

router = APIRouter()
chat_manager = ChatManager()


@router.websocket("/chat/{client_id}")
async def websocket_endpoint(client_id: str, websocket: WebSocket):
    """Websocket endpoint for chat."""
    await chat_manager.handle_websocket(client_id, websocket)
