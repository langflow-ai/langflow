from __future__ import annotations

import asyncio
from collections import defaultdict
from threading import RLock
from typing import Any

import pytest
from langflow.services.cache.base import AsyncBaseCacheService
from langflow.services.cache.service import RedisCache
from langflow.services.chat.service import ChatService, _cache_type_name
from rich.console import Console


class RecordingAsyncCache(AsyncBaseCacheService):
    def __init__(self) -> None:
        self.value: dict[str, Any] | None = None

    async def get(self, key, lock=None):
        _ = key, lock
        return self.value

    async def set(self, key, value, lock=None):
        _ = key, lock
        self.value = value

    async def upsert(self, key, value, lock=None):
        _ = key, lock
        self.value = value

    async def delete(self, key, lock=None):
        _ = key, lock
        self.value = None

    async def clear(self, lock=None):
        _ = lock
        self.value = None

    async def contains(self, key) -> bool:
        _ = key
        return self.value is not None


class RejectingAsyncCache(RecordingAsyncCache):
    async def upsert(self, key, value, lock=None):
        _ = key, value, lock
        msg = "pickled"
        raise TypeError(msg)


def make_chat_service(cache_service: AsyncBaseCacheService) -> ChatService:
    service = ChatService.__new__(ChatService)
    service.async_cache_locks = defaultdict(asyncio.Lock)
    service._sync_cache_locks = defaultdict(RLock)
    service.cache_service = cache_service
    return service


@pytest.mark.asyncio
async def test_chat_service_stores_type_name_not_class_object() -> None:
    cache = RecordingAsyncCache()
    service = make_chat_service(cache)

    assert await service.set_cache("flow-id", object()) is True

    assert cache.value is not None
    assert cache.value["type"] == _cache_type_name(object())
    assert isinstance(cache.value["type"], str)


@pytest.mark.asyncio
async def test_chat_service_skips_unpickleable_external_cache_write() -> None:
    service = make_chat_service(RejectingAsyncCache())

    assert await service.set_cache("flow-id", object()) is False


@pytest.mark.asyncio
async def test_redis_cache_reports_unpickleable_values_before_network_write() -> None:
    cache = RedisCache.__new__(RedisCache)
    cache.expiration_time = 60

    class FailingClient:
        async def setex(self, key, expiration_time, value):
            _ = key, expiration_time, value
            pytest.fail("Redis should not be called when serialization fails")

    cache._client = FailingClient()

    with pytest.raises(TypeError, match="RedisCache only accepts values that can be pickled"):
        await cache.set("console", Console())
