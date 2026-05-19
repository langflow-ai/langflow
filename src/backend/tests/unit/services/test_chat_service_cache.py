from __future__ import annotations

import asyncio
from collections import defaultdict
from threading import RLock
from typing import Any

from langflow.services.cache.base import AsyncBaseCacheService, CacheService
from langflow.services.chat.service import ChatService
from lfx.services.cache.utils import CACHE_MISS

PICKLE_ERROR_MESSAGE = "cannot pickle 'ConsoleThreadLocals' object"
CONTAINS_AFTER_FAILURE_MESSAGE = "contains should not be called after a rejected cache write"


class RejectingAsyncCache(AsyncBaseCacheService):
    """Async cache double that rejects writes like Redis can when dill fails."""

    async def get(self, _key, lock=None):
        _ = lock
        return CACHE_MISS

    async def set(self, _key, _value, lock=None):
        _ = lock
        raise TypeError(PICKLE_ERROR_MESSAGE)

    async def upsert(self, _key, _value, lock=None):
        _ = lock
        raise TypeError(PICKLE_ERROR_MESSAGE)

    async def delete(self, _key, lock=None):
        _ = lock

    async def clear(self, lock=None):
        _ = lock

    async def contains(self, _key) -> bool:
        raise AssertionError(CONTAINS_AFTER_FAILURE_MESSAGE)


class RecordingAsyncCache(AsyncBaseCacheService):
    """Async cache double that stores successful writes in memory."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    async def get(self, key, lock=None):
        _ = lock
        return self.values.get(key, CACHE_MISS)

    async def set(self, key, value, lock=None):
        _ = lock
        self.values[key] = value

    async def upsert(self, key, value, lock=None):
        _ = lock
        self.values[key] = value

    async def delete(self, key, lock=None):
        _ = lock
        self.values.pop(key, None)

    async def clear(self, lock=None):
        _ = lock
        self.values.clear()

    async def contains(self, key) -> bool:
        return key in self.values


class RejectingSyncCache(CacheService):
    """Sync cache double that rejects writes like Redis can when dill fails."""

    def get(self, _key, lock=None):
        _ = lock
        return CACHE_MISS

    def set(self, _key, _value, lock=None):
        _ = lock
        raise TypeError(PICKLE_ERROR_MESSAGE)

    def upsert(self, _key, _value, lock=None):
        _ = lock
        raise TypeError(PICKLE_ERROR_MESSAGE)

    def delete(self, _key, lock=None):
        _ = lock

    def clear(self, lock=None):
        _ = lock

    def contains(self, _key) -> bool:
        raise AssertionError(CONTAINS_AFTER_FAILURE_MESSAGE)

    def __contains__(self, _key) -> bool:
        raise AssertionError(CONTAINS_AFTER_FAILURE_MESSAGE)

    def __getitem__(self, _key):
        return CACHE_MISS

    def __setitem__(self, _key, _value) -> None:
        raise TypeError(PICKLE_ERROR_MESSAGE)

    def __delitem__(self, _key) -> None:
        return None


class RecordingSyncCache(CacheService):
    """Sync cache double that stores successful writes in memory."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def get(self, key, lock=None):
        _ = lock
        return self.values.get(key, CACHE_MISS)

    def set(self, key, value, lock=None):
        _ = lock
        self.values[key] = value

    def upsert(self, key, value, lock=None):
        _ = lock
        self.values[key] = value

    def delete(self, key, lock=None):
        _ = lock
        self.values.pop(key, None)

    def clear(self, lock=None):
        _ = lock
        self.values.clear()

    def contains(self, key) -> bool:
        return key in self.values

    def __contains__(self, key) -> bool:
        return key in self.values

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value) -> None:
        self.values[key] = value

    def __delitem__(self, key) -> None:
        del self.values[key]


def _chat_service_with_cache(cache: AsyncBaseCacheService | CacheService) -> ChatService:
    service = ChatService.__new__(ChatService)
    service.async_cache_locks = defaultdict(asyncio.Lock)
    service._sync_cache_locks = defaultdict(RLock)
    service.cache_service = cache
    return service


def test_set_cache_returns_false_when_async_cache_rejects_unpickleable_value():
    async def run_test() -> None:
        service = _chat_service_with_cache(RejectingAsyncCache())

        cached = await service.set_cache("flow-id", object())

        assert cached is False

    asyncio.run(run_test())


def test_set_cache_preserves_successful_async_cache_writes():
    async def run_test() -> None:
        cache = RecordingAsyncCache()
        service = _chat_service_with_cache(cache)

        cached = await service.set_cache("flow-id", "graph")

        assert cached is True
        assert cache.values["flow-id"] == {"result": "graph", "type": str}

    asyncio.run(run_test())


def test_set_cache_returns_false_when_sync_cache_rejects_unpickleable_value():
    async def run_test() -> None:
        service = _chat_service_with_cache(RejectingSyncCache())

        cached = await service.set_cache("flow-id", object())

        assert cached is False

    asyncio.run(run_test())


def test_set_cache_preserves_successful_sync_cache_writes():
    async def run_test() -> None:
        cache = RecordingSyncCache()
        service = _chat_service_with_cache(cache)

        cached = await service.set_cache("flow-id", "graph")

        assert cached is True
        assert cache.values["flow-id"] == {"result": "graph", "type": str}

    asyncio.run(run_test())
