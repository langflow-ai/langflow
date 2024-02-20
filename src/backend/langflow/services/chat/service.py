from typing import Any, Dict

from fastapi import WebSocket
from langflow.services.base import Service
from langflow.services.deps import get_cache_service

from .cache import cache_service


class ChatService(Service):
    name = "chat_service"

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_ids: Dict[str, str] = {}
        self.chat_cache = cache_service
        self.chat_cache.attach(self.update)
        self.cache_service = get_cache_service()

    def set_cache(self, client_id: str, data: Any) -> bool:
        """
        Set the cache for a client.
        """
        # client_id is the flow id but that already exists in the cache
        # so we need to change it to something else

        result_dict = {
            "result": data,
            "type": type(data),
        }
        self.cache_service.upsert(client_id, result_dict)
        return client_id in self.cache_service

    def get_cache(self, client_id: str) -> Any:
        """
        Get the cache for a client.
        """
        return self.cache_service.get(client_id)

    def clear_cache(self, client_id: str):
        """
        Clear the cache for a client.
        """
        self.cache_service.delete(client_id)
