from fastapi import APIRouter, WebSocket
from uuid import uuid4

from langflow.api.chat_manager import ChatManager

router = APIRouter()
chat_manager = ChatManager()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(client_id: str, websocket: WebSocket):
    await chat_manager.handle_websocket(client_id, websocket)
