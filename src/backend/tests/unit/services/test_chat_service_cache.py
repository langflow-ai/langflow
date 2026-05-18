from __future__ import annotations

import asyncio
from collections import defaultdict
from threading import RLock
from typing import Any

import pytest
from langflow.services.cache import service as cache_service_module
from langflow.services.cache.base import AsyncBaseCacheService
from langflow.services.cache.service import RedisCache
from langflow.services.chat.service import ChatService, _cache_type_name
from lfx.services.cache.utils import CACHE_MISS


class RecordingAsyncCache(AsyncBaseCacheService):
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


class RejectingAsyncCache(RecordingAsyncCache):
    async def upsert(self, key, value, lock=None):
        _ = key, value, lock
        raise TypeError("cannot pickle 'ConsoleThreadLocals' object")

    async def contains(self, key) -> bool:
        _ = key
        raise AssertionError("contains should not run after a rejected cache write")


class UnexpectedTypeErrorAsyncCache(RecordingAsyncCache):
    async def upsert(self, key, value, lock=None):
        _ = key, value, lock
        raise TypeError("missing required argument")


class UnpickleableValue:
    def __getstate__(self):
        raise TypeError("cannot pickle test value")


def make_chat_service(cache_service: AsyncBaseCacheService) -> ChatService:
    service = ChatService.__new__(ChatService)
    service.async_cache_locks = defaultdict(asyncio.Lock)
    service._sync_cache_locks = defaultdict(RLock)
    service.cache_service = cache_service
    return service


async def test_set_cache_stores_type_name_instead_of_class_object() -> None:
    cache = RecordingAsyncCache()
    service = make_chat_service(cache)
    value = object()

    assert await service.set_cache("flow-id", value) is True

    assert cache.values["flow-id"] == {"result": value, "type": _cache_type_name(value)}
    assert isinstance(cache.values["flow-id"]["type"], str)


async def test_set_cache_returns_false_for_unpickleable_cache_values() -> None:
    service = make_chat_service(RejectingAsyncCache())

    assert await service.set_cache("flow-id", object()) is False


async def test_set_cache_reraises_unrelated_type_errors() -> None:
    service = make_chat_service(UnexpectedTypeErrorAsyncCache())

    with pytest.raises(TypeError, match="missing required argument"):
        await service.set_cache("flow-id", object())


async def test_redis_cache_rejects_unpickleable_values_before_network_write() -> None:
    cache = RedisCache.__new__(RedisCache)
    cache.expiration_time = 60

    class FailingClient:
        async def setex(self, key, expiration_time, value):
            _ = key, expiration_time, value
            pytest.fail("Redis should not be called when serialization fails")

    cache._client = FailingClient()

    with pytest.raises(TypeError, match="RedisCache only accepts values that can be pickled"):
        await cache.set("flow-id", UnpickleableValue())


async def test_redis_cache_rejects_empty_serialization_result(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = RedisCache.__new__(RedisCache)
    cache.expiration_time = 60

    class FailingClient:
        async def setex(self, key, expiration_time, value):
            _ = key, expiration_time, value
            pytest.fail("Redis should not be called when serialization returns an empty value")

    cache._client = FailingClient()
    monkeypatch.setattr(cache_service_module.dill, "dumps", lambda value, recurse=True: b"")

    with pytest.raises(ValueError, match="RedisCache serialization returned empty result"):
        await cache.set("flow-id", object())
