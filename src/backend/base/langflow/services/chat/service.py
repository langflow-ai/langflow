import asyncio
from collections import defaultdict
from threading import RLock
from typing import Any, Optional

from langflow.services.base import Service
from langflow.services.cache.base import AsyncBaseCacheService
from langflow.services.deps import get_cache_service


class ChatService(Service):
    """
    Service class for managing chat-related operations.
    """

    name = "chat_service"

    def __init__(self):
        self._async_cache_locks = defaultdict(asyncio.Lock)
        self._sync_cache_locks = defaultdict(RLock)
        self.cache_service = get_cache_service()

    def _get_lock(self, key: str):
        """
        Retrieves the lock associated with the given key.

        Args:
            key (str): The key to retrieve the lock for.

        Returns:
            threading.Lock or asyncio.Lock: The lock associated with the given key.
        """
        if isinstance(self.cache_service, AsyncBaseCacheService):
            return self._async_cache_locks[key]
        else:
            return self._sync_cache_locks[key]

    async def _perform_cache_operation(
        self, operation: str, key: str, data: Any = None, lock: Optional[asyncio.Lock] = None
    ):
        """
        Perform a cache operation based on the given operation type.

        Args:
            operation (str): The type of cache operation to perform. Possible values are "upsert", "get", or "delete".
            key (str): The key associated with the cache operation.
            data (Any, optional): The data to be stored in the cache. Only applicable for "upsert" operation. Defaults to None.
            lock (Optional[asyncio.Lock], optional): The lock to be used for the cache operation. Defaults to None.

        Returns:
            Any: The result of the cache operation. Only applicable for "get" operation.

        Raises:
            None

        """
        lock = lock or self._get_lock(key)
        if isinstance(self.cache_service, AsyncBaseCacheService):
            if operation == "upsert":
                await self.cache_service.upsert(str(key), data, lock=lock)
            elif operation == "get":
                return await self.cache_service.get(key, lock=lock)
            elif operation == "delete":
                await self.cache_service.delete(key, lock=lock)
        else:
            if operation == "upsert":
                self.cache_service.upsert(str(key), data, lock=lock)
            elif operation == "get":
                return self.cache_service.get(key, lock=lock)
            elif operation == "delete":
                self.cache_service.delete(key, lock=lock)

    async def set_cache(self, key: str, data: Any, lock: Optional[asyncio.Lock] = None) -> bool:
        """
        Set the cache for a client.

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
        await self._perform_cache_operation("upsert", key, result_dict, lock)
        return key in self.cache_service

    async def get_cache(self, key: str, lock: Optional[asyncio.Lock] = None) -> Any:
        """
        Get the cache for a client.

        Args:
            key (str): The cache key.
            lock (Optional[asyncio.Lock], optional): The lock to use for the cache operation. Defaults to None.

        Returns:
            Any: The cached data.
        """
        return await self._perform_cache_operation("get", key, lock=lock or self._get_lock(key))

    async def clear_cache(self, key: str, lock: Optional[asyncio.Lock] = None):
        """
        Clear the cache for a client.

        Args:
            key (str): The cache key.
            lock (Optional[asyncio.Lock], optional): The lock to use for the cache operation. Defaults to None.
        """
        await self._perform_cache_operation("delete", key, lock=lock or self._get_lock(key))
