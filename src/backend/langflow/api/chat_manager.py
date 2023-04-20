from typing import Dict, List
from collections import defaultdict
from fastapi import WebSocket
import json
from langflow.api.schemas import ChatMessage, ChatResponse

from langflow.interface.run import (
    async_get_result_and_steps,
    load_or_build_langchain_object,
)
from langflow.utils.logger import logger


class ChatHistory:
    def __init__(self):
        self.history: Dict[str, List[ChatMessage]] = defaultdict(list)

    def add_message(self, client_id: str, message: ChatMessage):
        self.history[client_id].append(message)

    def get_history(self, client_id: str) -> List[ChatMessage]:
        return self.history[client_id]


class ChatManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.chat_history = ChatHistory()

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        del self.active_connections[client_id]

    async def send_message(self, client_id: str, message: str):
        websocket = self.active_connections[client_id]
        await websocket.send_text(message)

    async def send_json(self, client_id: str, message: ChatMessage):
        websocket = self.active_connections[client_id]
        self.chat_history.add_message(client_id, message)
        await websocket.send_json(message.dict())

    async def process_message(self, client_id: str, payload: Dict):
        # Process the graph data and chat message

        chat_message = payload.pop("message", "")
        chat_message = ChatMessage(sender="user", message=chat_message)
        self.chat_history.add_message(client_id, chat_message)

        graph_data = payload
        start_resp = ChatResponse(
            sender="bot", message=None, type="start", intermediate_steps=""
        )
        await self.send_json(client_id, start_resp)

        is_first_message = len(self.chat_history.get_history(client_id=client_id)) == 0
        langchain_object = load_or_build_langchain_object(graph_data, is_first_message)
        logger.debug("Loaded langchain object")

        if langchain_object is None:
            # Raise user facing error
            raise ValueError(
                "There was an error loading the langchain_object. Please, check all the nodes and try again."
            )

        # Generate result and thought
        try:
            logger.debug("Generating result and thought")
            result, intermediate_steps = await async_get_result_and_steps(
                langchain_object, chat_message.message or ""
            )
            logger.debug("Generated result and intermediate_steps")
        except Exception as e:
            # Log stack trace
            logger.exception(e)
            error_resp = ChatResponse(
                sender="bot", message=str(e), type="error", intermediate_steps=""
            )
            await self.send_json(client_id, error_resp)
            return
        # Send a response back to the frontend, if needed
        response = ChatResponse(
            sender="bot",
            message=result or "",
            intermediate_steps=intermediate_steps or "",
            type="end",
        )
        await self.send_json(client_id, response)

    async def handle_websocket(self, client_id: str, websocket: WebSocket):
        await self.connect(client_id, websocket)
        try:
            chat_history = self.chat_history.get_history(client_id)
            await websocket.send_json(json.dumps(chat_history))

            while True:
                json_payload = await websocket.receive_json()
                payload = json.loads(json_payload)
                await self.process_message(client_id, payload)
        except Exception as e:
            # Handle any exceptions that might occur
            print(f"Error: {e}")
        finally:
            self.disconnect(client_id)
