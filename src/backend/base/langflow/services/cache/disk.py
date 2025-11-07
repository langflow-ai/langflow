import asyncio
import pickle
import time
from typing import Generic

from diskcache import Cache
from lfx.log.logger import logger
from lfx.services.cache.utils import CACHE_MISS

from langflow.services.cache.base import AsyncBaseCacheService, AsyncLockType


class AsyncDiskCache(AsyncBaseCacheService, Generic[AsyncLockType]):
    def __init__(self, cache_dir, max_size=None, expiration_time=3600) -> None:
        self.cache = Cache(cache_dir)
        # Let's clear the cache for now to maintain a similar
        # behavior as the in-memory cache
        # Later we should implement endpoints for the frontend to grab
        # output logs from the cache
        if len(self.cache) > 0:
            self.cache.clear()
        self.lock = asyncio.Lock()
        self.max_size = max_size
        self.expiration_time = expiration_time

    async def get(self, key, lock: asyncio.Lock | None = None):
        if not lock:
            async with self.lock:
                return await asyncio.to_thread(self._get, key)
        else:
            return await asyncio.to_thread(self._get, key)

    def _get(self, key):
        item = self.cache.get(key, default=None)
        if item:
            if time.time() - item["time"] < self.expiration_time:
                self.cache.touch(key)  # Refresh the expiry time
                return pickle.loads(item["value"]) if isinstance(item["value"], bytes) else item["value"]
            logger.info(f"Cache item for key '{key}' has expired and will be deleted.")
            self.cache.delete(key)  # Log before deleting the expired item
        return CACHE_MISS

    async def set(self, key, value, lock: asyncio.Lock | None = None) -> None:
        if not lock:
            async with self.lock:
                await self._set(key, value)
        else:
            await self._set(key, value)

    async def _set(self, key, value) -> None:
        if self.max_size and len(self.cache) >= self.max_size:
            await asyncio.to_thread(self.cache.cull)
        item = {"value": pickle.dumps(value) if not isinstance(value, str | bytes) else value, "time": time.time()}
        await asyncio.to_thread(self.cache.set, key, item)

    async def delete(self, key, lock: asyncio.Lock | None = None) -> None:
        if not lock:
            async with self.lock:
                await self._delete(key)
        else:
            await self._delete(key)

    async def _delete(self, key) -> None:
        await asyncio.to_thread(self.cache.delete, key)

    async def clear(self, lock: asyncio.Lock | None = None) -> None:
        if not lock:
            async with self.lock:
                await self._clear()
        else:
            await self._clear()

    async def _clear(self) -> None:
        await asyncio.to_thread(self.cache.clear)

    async def upsert(self, key, value, lock: asyncio.Lock | None = None) -> None:
        if not lock:
            async with self.lock:
                await self._upsert(key, value)
        else:
            await self._upsert(key, value)

    async def _upsert(self, key, value) -> None:
        existing_value = await asyncio.to_thread(self._get, key)
        if existing_value is not CACHE_MISS and isinstance(existing_value, dict) and isinstance(value, dict):
            existing_value.update(value)
            value = existing_value
        await self.set(key, value)

    async def contains(self, key) -> bool:
        return await asyncio.to_thread(self.cache.__contains__, key)

    async def teardown(self) -> None:
        # Clean up the cache directory
        self.cache.clear(retry=True)
