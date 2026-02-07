import asyncio
import logging
from collections import defaultdict
from threading import RLock
from typing import Any

from langflow.services.base import Service
from langflow.services.cache.base import AsyncBaseCacheService, CacheService
from langflow.services.deps import get_cache_service

logger = logging.getLogger(__name__)


class ChatService(Service):
    """Service class for managing chat-related operations."""

    name = "chat_service"

    def __init__(self) -> None:
        self.async_cache_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._sync_cache_locks: dict[str, RLock] = defaultdict(RLock)
        self.cache_service: CacheService | AsyncBaseCacheService = get_cache_service()

    async def set_cache(self, key: str, data: Any, lock: asyncio.Lock | None = None) -> bool:
        """Set the cache for a client.

        Cache failures (e.g. serialization errors with Redis) are logged and
        swallowed so they never interrupt flow execution.

        Args:
            key (str): The cache key.
            data (Any): The data to be cached.
            lock (Optional[asyncio.Lock], optional): The lock to use for the cache operation. Defaults to None.

        Returns:
            bool: True if the cache was set successfully, False otherwise.
        """
        result_dict = {
            "result": data,
            "type": type(data),
        }
        try:
            if isinstance(self.cache_service, AsyncBaseCacheService):
                await self.cache_service.upsert(str(key), result_dict, lock=lock or self.async_cache_locks[key])
                return await self.cache_service.contains(key)
            await asyncio.to_thread(
                self.cache_service.upsert, str(key), result_dict, lock=lock or self._sync_cache_locks[key]
            )
            return key in self.cache_service
        except Exception:  # noqa: BLE001
            logger.warning("Failed to set cache for key '%s' — flow execution will continue without caching.", key)
            return False

    async def get_cache(self, key: str, lock: asyncio.Lock | None = None) -> Any:
        """Get the cache for a client.

        Args:
            key (str): The cache key.
            lock (Optional[asyncio.Lock], optional): The lock to use for the cache operation. Defaults to None.

        Returns:
            Any: The cached data.
        """
        if isinstance(self.cache_service, AsyncBaseCacheService):
            return await self.cache_service.get(key, lock=lock or self.async_cache_locks[key])
        return await asyncio.to_thread(self.cache_service.get, key, lock=lock or self._sync_cache_locks[key])

    async def clear_cache(self, key: str, lock: asyncio.Lock | None = None) -> None:
        """Clear the cache for a client.

        Args:
            key (str): The cache key.
            lock (Optional[asyncio.Lock], optional): The lock to use for the cache operation. Defaults to None.
        """
        if isinstance(self.cache_service, AsyncBaseCacheService):
            return await self.cache_service.delete(key, lock=lock or self.async_cache_locks[key])
        return await asyncio.to_thread(self.cache_service.delete, key, lock=lock or self._sync_cache_locks[key])
