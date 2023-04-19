from fastapi import APIRouter, WebSocket
from uuid import uuid4

from langflow.api.chat_manager import ChatManager

router = APIRouter()
chat_manager = ChatManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = str(uuid4())
    await chat_manager.handle_websocket(client_id, websocket)
