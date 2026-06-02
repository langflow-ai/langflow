from __future__ import annotations

import asyncio
from collections import defaultdict
from threading import RLock
from typing import Any

import pytest
from langflow.services.cache.base import AsyncBaseCacheService, CacheService
from langflow.services.cache.service import RedisCache, ThreadingInMemoryCache
from langflow.services.chat.service import ChatService, _cache_type_name, _is_pickle_error
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


class RejectingNonPickleAsyncCache(RecordingAsyncCache):
    async def upsert(self, key, value, lock=None):
        _ = key, value, lock
        msg = "cache backend rejected the value"
        raise TypeError(msg)


def make_chat_service(cache_service: AsyncBaseCacheService | CacheService) -> ChatService:
    service = ChatService.__new__(ChatService)
    service.async_cache_locks = defaultdict(asyncio.Lock)
    service._sync_cache_locks = defaultdict(RLock)
    service.cache_service = cache_service
    return service


@pytest.mark.asyncio
async def test_chat_service_stores_type_name_not_class_object() -> None:
    cache = RecordingAsyncCache()
    service = make_chat_service(cache)

    cached_value = object()

    assert await service.set_cache("flow-id", cached_value) is True

    assert cache.value is not None
    assert cache.value["type"] == _cache_type_name(cached_value)
    assert isinstance(cache.value["type"], str)


@pytest.mark.asyncio
async def test_chat_service_sync_cache_stores_type_name_not_class_object() -> None:
    cache = ThreadingInMemoryCache()
    service = make_chat_service(cache)
    cached_value = object()

    assert await service.set_cache("flow-id", cached_value) is True

    stored_value = cache.get("flow-id")
    assert stored_value["type"] == _cache_type_name(cached_value)
    assert isinstance(stored_value["type"], str)


@pytest.mark.asyncio
async def test_chat_service_skips_unpickleable_external_cache_write() -> None:
    service = make_chat_service(RejectingAsyncCache())

    assert await service.set_cache("flow-id", object()) is False


@pytest.mark.asyncio
async def test_chat_service_reraises_non_pickle_type_errors() -> None:
    service = make_chat_service(RejectingNonPickleAsyncCache())

    with pytest.raises(TypeError, match="cache backend rejected"):
        await service.set_cache("flow-id", object())


def test_is_pickle_error_detects_serialization_messages() -> None:
    assert _is_pickle_error(TypeError("cannot pickle SSLContext object")) is True
    assert _is_pickle_error(TypeError("value could not be pickled")) is True
    assert _is_pickle_error(TypeError("cache backend rejected the value")) is False


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
