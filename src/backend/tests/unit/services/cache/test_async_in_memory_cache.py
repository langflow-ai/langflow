"""Tests for AsyncInMemoryCache."""

import asyncio

import pytest
from langflow.services.cache.service import AsyncInMemoryCache
from lfx.services.cache.utils import CACHE_MISS

pytestmark = pytest.mark.asyncio


class TestAsyncInMemoryCacheBasic:
    """Basic async get/set/delete/clear operations."""

    async def test_set_and_get(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    async def test_get_missing_key_returns_cache_miss(self):
        cache = AsyncInMemoryCache()
        result = await cache.get("nonexistent")
        assert result is CACHE_MISS

    async def test_set_overwrites_existing(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", "value1")
        await cache.set("key1", "value2")
        result = await cache.get("key1")
        assert result == "value2"

    async def test_delete(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", "value1")
        await cache.delete("key1")
        result = await cache.get("key1")
        assert result is CACHE_MISS

    async def test_delete_nonexistent_key(self):
        cache = AsyncInMemoryCache()
        await cache.delete("nonexistent")  # Should not raise

    async def test_clear(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()
        assert await cache.get("key1") is CACHE_MISS
        assert await cache.get("key2") is CACHE_MISS

    async def test_contains(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", "value1")
        assert await cache.contains("key1") is True
        assert await cache.contains("nonexistent") is False


class TestAsyncInMemoryCacheLRU:
    """Tests for LRU eviction in async cache."""

    async def test_max_size_eviction(self):
        cache = AsyncInMemoryCache(max_size=3)
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")
        # key1 should be evicted (least recently used)
        assert await cache.get("key1") is CACHE_MISS
        assert await cache.get("key4") == "value4"

    async def test_access_refreshes_order(self):
        cache = AsyncInMemoryCache(max_size=3)
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        # Access key1 to make it recently used
        await cache.get("key1")
        # Add key4 should evict key2
        await cache.set("key4", "value4")
        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") is CACHE_MISS


class TestAsyncInMemoryCacheExpiration:
    """Tests for expiration in async cache."""

    async def test_expired_item_returns_cache_miss(self):
        cache = AsyncInMemoryCache(expiration_time=0.1)
        await cache.set("key1", "value1")
        await asyncio.sleep(0.5)
        result = await cache.get("key1")
        assert result is CACHE_MISS


class TestAsyncInMemoryCacheUpsert:
    """Tests for upsert in async cache."""

    async def test_upsert_new_key(self):
        cache = AsyncInMemoryCache()
        await cache.upsert("key1", {"a": 1})
        result = await cache.get("key1")
        assert result == {"a": 1}

    async def test_upsert_merges_dicts(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", {"a": 1, "b": 2})
        await cache.upsert("key1", {"b": 3, "c": 4})
        result = await cache.get("key1")
        assert result == {"a": 1, "b": 3, "c": 4}

    async def test_upsert_non_dict_replaces(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", "old")
        await cache.upsert("key1", "new")
        result = await cache.get("key1")
        assert result == "new"


class TestAsyncInMemoryCacheDataTypes:
    """Tests for various data types in async cache."""

    async def test_store_dict(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", {"nested": {"data": True}})
        result = await cache.get("key1")
        assert result == {"nested": {"data": True}}

    async def test_store_list(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", [1, 2, 3])
        result = await cache.get("key1")
        assert result == [1, 2, 3]

    async def test_store_numeric(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", 42)
        result = await cache.get("key1")
        assert result == 42

    async def test_store_string(self):
        cache = AsyncInMemoryCache()
        await cache.set("key1", "hello world")
        result = await cache.get("key1")
        assert result == "hello world"
