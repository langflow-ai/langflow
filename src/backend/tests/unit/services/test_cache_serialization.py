from __future__ import annotations

import asyncio
from collections import defaultdict
from threading import RLock
from typing import Any

import pytest
from langflow.services.cache.base import AsyncBaseCacheService, CacheService
from langflow.services.cache.service import RedisCache
from langflow.services.chat.service import ChatService, _cache_type_name
from langflow.services.session.service import SessionService
from lfx.services.cache.utils import CACHE_MISS

PICKLE_ERROR = "cannot pickle ConsoleThreadLocals object"
UNRELATED_TYPE_ERROR = "missing required argument"
CONTAINS_AFTER_REJECTED = "contains should not run after a rejected cache write"
SYNC_CONTAINS_AFTER_REJECTED = "__contains__ should not run after a rejected cache write"


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
    async def set(self, key, value, lock=None):
        _ = key, value, lock
        raise TypeError(PICKLE_ERROR)

    async def upsert(self, key, value, lock=None):
        _ = key, value, lock
        raise TypeError(PICKLE_ERROR)

    async def contains(self, key) -> bool:
        _ = key
        raise AssertionError(CONTAINS_AFTER_REJECTED)


class UnexpectedTypeErrorAsyncCache(RecordingAsyncCache):
    async def set(self, key, value, lock=None):
        _ = key, value, lock
        raise TypeError(UNRELATED_TYPE_ERROR)

    async def upsert(self, key, value, lock=None):
        _ = key, value, lock
        raise TypeError(UNRELATED_TYPE_ERROR)


class RecordingSyncCache(CacheService):
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


class RejectingSyncCache(RecordingSyncCache):
    def upsert(self, key, value, lock=None):
        _ = key, value, lock
        raise TypeError(PICKLE_ERROR)

    def __contains__(self, key) -> bool:
        _ = key
        raise AssertionError(SYNC_CONTAINS_AFTER_REJECTED)


class UnpickleableValue:
    def __getstate__(self):
        message = "cannot pickle test value"
        raise TypeError(message)


def make_chat_service(cache_service: CacheService | AsyncBaseCacheService) -> ChatService:
    service = ChatService.__new__(ChatService)
    service.async_cache_locks = defaultdict(asyncio.Lock)
    service._sync_cache_locks = defaultdict(RLock)
    service.cache_service = cache_service
    return service


async def test_chat_cache_stores_type_name_instead_of_class_object() -> None:
    cache = RecordingAsyncCache()
    service = make_chat_service(cache)
    value = object()

    assert await service.set_cache("flow-id", value) is True

    assert cache.values["flow-id"] == {"result": value, "type": _cache_type_name(value)}
    assert isinstance(cache.values["flow-id"]["type"], str)


async def test_chat_cache_returns_false_for_async_pickle_failures() -> None:
    service = make_chat_service(RejectingAsyncCache())

    assert await service.set_cache("flow-id", object()) is False


async def test_chat_cache_returns_false_for_sync_pickle_failures() -> None:
    service = make_chat_service(RejectingSyncCache())

    assert await service.set_cache("flow-id", object()) is False


async def test_chat_cache_reraises_unrelated_type_errors() -> None:
    service = make_chat_service(UnexpectedTypeErrorAsyncCache())

    with pytest.raises(TypeError, match="missing required argument"):
        await service.set_cache("flow-id", object())


async def test_session_cache_skips_pickle_failures() -> None:
    service = SessionService(RejectingAsyncCache())

    await service.update_session("session-id", object())


async def test_load_session_returns_graph_when_cache_write_fails(monkeypatch) -> None:
    from lfx.graph.graph.base import Graph

    service = SessionService(RejectingAsyncCache())
    expected_graph = object()

    def from_payload(payload, flow_id=None, flow_name=None, user_id=None, context=None):
        _ = flow_name, user_id, context
        assert payload == {"nodes": [], "edges": []}
        assert flow_id == "flow-id"
        return expected_graph

    monkeypatch.setattr(Graph, "from_payload", staticmethod(from_payload))

    graph, artifacts = await service.load_session("session-id", "flow-id", {"nodes": [], "edges": []})

    assert graph is expected_graph
    assert artifacts == {}


async def test_session_cache_reraises_unrelated_type_errors() -> None:
    service = SessionService(UnexpectedTypeErrorAsyncCache())

    with pytest.raises(TypeError, match="missing required argument"):
        await service.update_session("session-id", object())


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
