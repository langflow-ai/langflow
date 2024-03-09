import asyncio
from collections import defaultdict
from typing import Any

from langflow.services.base import Service
from langflow.services.deps import get_cache_service


class ChatService(Service):
    name = "chat_service"

    def __init__(self):
        self._cache_locks = defaultdict(asyncio.Lock)
        self.cache_service = get_cache_service()

    async def set_cache(self, flow_id: str, data: Any) -> bool:
        """
        Set the cache for a client.
        """
        # client_id is the flow id but that already exists in the cache
        # so we need to change it to something else
        async with self._cache_locks[flow_id]:
            result_dict = {
                "result": data,
                "type": type(data),
            }
            await self.cache_service.upsert(
                flow_id, result_dict, lock=self._cache_locks[flow_id]
            )
        return flow_id in self.cache_service

    async def get_cache(self, client_id: str) -> Any:
        """
        Get the cache for a client.
        """
        return await self.cache_service.get(client_id)

    async def clear_cache(self, client_id: str):
        """
        Clear the cache for a client.
        """
        self.cache_service.delete(client_id)
