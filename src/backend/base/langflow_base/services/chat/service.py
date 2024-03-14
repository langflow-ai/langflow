import asyncio
from collections import defaultdict
from typing import Any, Optional

import orjson
from fastapi import WebSocket, status
from loguru import logger
from starlette.websockets import WebSocketState

from langflow_base.api.v1.schemas import ChatMessage, ChatResponse, FileResponse
from langflow_base.interface.utils import pil_to_base64
from langflow_base.services import ServiceType, service_manager
from langflow_base.services.base import Service
from langflow_base.services.chat.cache import Subject
from langflow_base.services.chat.utils import process_graph

from .cache import cache_service


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
        self._cache_locks = defaultdict(asyncio.Lock)
        self.cache_service = get_cache_service()

    async def set_cache(self, flow_id: str, data: Any, lock: Optional[asyncio.Lock] = None) -> bool:
        """
        Set the cache for a client.
        """
        # client_id is the flow id but that already exists in the cache
        # so we need to change it to something else
        result_dict = {
            "result": data,
            "type": type(data),
        }
        await self.cache_service.upsert(flow_id, result_dict, lock=lock or self._cache_locks[flow_id])
        return flow_id in self.cache_service

    async def get_cache(self, flow_id: str, lock: Optional[asyncio.Lock] = None) -> Any:
        """
        Get the cache for a client.
        """
        return await self.cache_service.get(flow_id, lock=lock or self._cache_locks[flow_id])

    async def clear_cache(self, flow_id: str, lock: Optional[asyncio.Lock] = None):
        """
        Clear the cache for a client.
        """
        self.cache_service.delete(flow_id, lock=lock or self._cache_locks[flow_id])
