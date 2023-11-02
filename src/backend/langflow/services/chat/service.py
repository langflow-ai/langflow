from collections import defaultdict
import uuid
from fastapi import WebSocket, status
from starlette.websockets import WebSocketState
from langflow.api.v1.schemas import ChatMessage, ChatResponse, FileResponse
from langflow.interface.utils import pil_to_base64
from langflow.services.base import Service
from langflow.services.chat.cache import Subject
from langflow.services.chat.utils import process_graph
from loguru import logger

from .cache import cache_service
import asyncio
from typing import Any, Dict, List

from langflow.services import service_manager, ServiceType
import orjson


class ChatHistory(Subject):
    def __init__(self):
        super().__init__()
        self.history: Dict[str, List[ChatMessage]] = defaultdict(list)

    def add_message(self, client_id: str, message: ChatMessage):
        """Add a message to the chat history."""

        self.history[client_id].append(message)

        if not isinstance(message, FileResponse):
            self.notify()

    def get_history(self, client_id: str, filter_messages=True) -> List[ChatMessage]:
        """Get the chat history for a client."""
        if history := self.history.get(client_id, []):
            if filter_messages:
                return [msg for msg in history if msg.type not in ["start", "stream"]]
            return history
        else:
            return []

    def empty_history(self, client_id: str):
        """Empty the chat history for a client."""
        self.history[client_id] = []


class ChatService(Service):
    name = "chat_service"

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_ids: Dict[str, str] = {}
        self.chat_history = ChatHistory()
        self.chat_cache = cache_service
        self.chat_cache.attach(self.update)
        self.cache_service = service_manager.get(ServiceType.CACHE_SERVICE)

    def on_chat_history_update(self):
        """Send the last chat message to the client."""
        client_id = self.chat_cache.current_client_id
        if client_id in self.active_connections:
            chat_response = self.chat_history.get_history(
                client_id, filter_messages=False
            )[-1]
            if chat_response.is_bot:
                # Process FileResponse
                if isinstance(chat_response, FileResponse):
                    # If data_type is pandas, convert to csv
                    if chat_response.data_type == "pandas":
                        chat_response.data = chat_response.data.to_csv()
                    elif chat_response.data_type == "image":
                        # Base64 encode the image
                        chat_response.data = pil_to_base64(chat_response.data)
                # get event loop
                loop = asyncio.get_event_loop()

                coroutine = self.send_json(client_id, chat_response)
                asyncio.run_coroutine_threadsafe(coroutine, loop)

    def update(self):
        if self.chat_cache.current_client_id in self.active_connections:
            self.last_cached_object_dict = self.chat_cache.get_last()
            # Add a new ChatResponse with the data
            chat_response = FileResponse(
                message=None,
                type="file",
                data=self.last_cached_object_dict["obj"],
                data_type=self.last_cached_object_dict["type"],
            )

            self.chat_history.add_message(
                self.chat_cache.current_client_id, chat_response
            )

    async def connect(self, client_id: str, websocket: WebSocket):
        self.active_connections[client_id] = websocket
        # This is to avoid having multiple clients with the same id
        #! Temporary solution
        self.connection_ids[client_id] = f"{client_id}-{uuid.uuid4()}"

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        self.connection_ids.pop(client_id, None)

    async def send_message(self, client_id: str, message: str):
        websocket = self.active_connections[client_id]
        await websocket.send_text(message)

    async def send_json(self, client_id: str, message: ChatMessage):
        websocket = self.active_connections[client_id]
        await websocket.send_json(message.dict())

    async def close_connection(self, client_id: str, code: int, reason: str):
        if websocket := self.active_connections[client_id]:
            try:
                await websocket.close(code=code, reason=reason)
                self.disconnect(client_id)
            except RuntimeError as exc:
                # This is to catch the following error:
                #  Unexpected ASGI message 'websocket.close', after sending 'websocket.close'
                if "after sending" in str(exc):
                    logger.error(f"Error closing connection: {exc}")

    async def process_message(
        self, client_id: str, payload: Dict, langchain_object: Any
    ):
        # Process the graph data and chat message
        chat_inputs = payload.pop("inputs", {})
        chatkey = payload.pop("chatKey", None)
        chat_inputs = ChatMessage(message=chat_inputs, chatKey=chatkey)
        self.chat_history.add_message(client_id, chat_inputs)

        # graph_data = payload
        start_resp = ChatResponse(message=None, type="start", intermediate_steps="")
        await self.send_json(client_id, start_resp)

        # is_first_message = len(self.chat_history.get_history(client_id=client_id)) <= 1
        # Generate result and thought
        try:
            logger.debug("Generating result and thought")

            result, intermediate_steps = await process_graph(
                langchain_object=langchain_object,
                chat_inputs=chat_inputs,
                client_id=client_id,
                session_id=self.connection_ids[client_id],
            )
            self.set_cache(client_id, langchain_object)
        except Exception as e:
            # Log stack trace
            logger.exception(e)
            self.chat_history.empty_history(client_id)
            raise e
        # Send a response back to the frontend, if needed
        intermediate_steps = intermediate_steps or ""
        history = self.chat_history.get_history(client_id, filter_messages=False)
        file_responses = []
        if history:
            # Iterate backwards through the history
            for msg in reversed(history):
                if isinstance(msg, FileResponse):
                    if msg.data_type == "image":
                        # Base64 encode the image
                        if isinstance(msg.data, str):
                            continue
                        msg.data = pil_to_base64(msg.data)
                    file_responses.append(msg)
                if msg.type == "start":
                    break

        response = ChatResponse(
            message=result,
            intermediate_steps=intermediate_steps.strip(),
            type="end",
            files=file_responses,
        )
        await self.send_json(client_id, response)
        self.chat_history.add_message(client_id, response)

    def set_cache(self, client_id: str, langchain_object: Any) -> bool:
        """
        Set the cache for a client.
        """
        # client_id is the flow id but that already exists in the cache
        # so we need to change it to something else

        result_dict = {
            "result": langchain_object,
            "type": type(langchain_object),
        }
        self.cache_service.upsert(client_id, result_dict)
        return client_id in self.cache_service

    async def handle_websocket(self, client_id: str, websocket: WebSocket):
        await self.connect(client_id, websocket)

        try:
            chat_history = self.chat_history.get_history(client_id)
            # iterate and make BaseModel into dict
            chat_history = [chat.dict() for chat in chat_history]
            await websocket.send_json(chat_history)

            while True:
                json_payload = await websocket.receive_json()
                if isinstance(json_payload, str):
                    payload = orjson.loads(json_payload)
                elif isinstance(json_payload, dict):
                    payload = json_payload
                if "clear_history" in payload and payload["clear_history"]:
                    self.chat_history.history[client_id] = []
                    continue

                with self.chat_cache.set_client_id(client_id):
                    if langchain_object := self.cache_service.get(client_id).get(
                        "result"
                    ):
                        await self.process_message(client_id, payload, langchain_object)

                    else:
                        raise RuntimeError(
                            f"Could not find a build result for client_id {client_id}"
                        )
        except Exception as exc:
            # Handle any exceptions that might occur
            logger.exception(f"Error handling websocket: {exc}")
            if websocket.client_state == WebSocketState.CONNECTED:
                await self.close_connection(
                    client_id=client_id,
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason=str(exc)[:120],
                )
            elif websocket.client_state == WebSocketState.DISCONNECTED:
                self.disconnect(client_id)

        finally:
            try:
                # first check if the connection is still open
                if websocket.client_state == WebSocketState.CONNECTED:
                    await self.close_connection(
                        client_id=client_id,
                        code=status.WS_1000_NORMAL_CLOSURE,
                        reason="Client disconnected",
                    )
            except Exception as exc:
                logger.error(f"Error closing connection: {exc}")
            self.disconnect(client_id)
