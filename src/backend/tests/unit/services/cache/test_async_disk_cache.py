"""Tests for langflow.services.cache.disk.AsyncDiskCache."""

import asyncio
import time

import pytest

from langflow.services.cache.disk import AsyncDiskCache

pytestmark = pytest.mark.asyncio


@pytest.fixture
def cache(tmp_path):
    """Create a fresh AsyncDiskCache for each test."""
    c = AsyncDiskCache(str(tmp_path / "cache"), max_size=10, expiration_time=3600)
    return c


@pytest.fixture
def short_expiry_cache(tmp_path):
    """Cache with very short expiration for testing expiry."""
    return AsyncDiskCache(str(tmp_path / "cache_exp"), max_size=10, expiration_time=0.1)


class TestAsyncDiskCacheSetGet:
    async def test_set_and_get_string(self, cache):
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    async def test_set_and_get_dict(self, cache):
        data = {"name": "test", "count": 42}
        await cache.set("key1", data)
        result = await cache.get("key1")
        assert result == data

    async def test_set_and_get_list(self, cache):
        data = [1, 2, 3, "four"]
        await cache.set("key1", data)
        result = await cache.get("key1")
        assert result == data

    async def test_set_and_get_int(self, cache):
        await cache.set("key1", 42)
        result = await cache.get("key1")
        assert result == 42

    async def test_get_missing_key(self, cache):
        from lfx.services.cache.utils import CACHE_MISS

        result = await cache.get("nonexistent")
        assert result is CACHE_MISS


class TestAsyncDiskCacheDelete:
    async def test_delete_existing(self, cache):
        from lfx.services.cache.utils import CACHE_MISS

        await cache.set("key1", "value1")
        await cache.delete("key1")
        result = await cache.get("key1")
        assert result is CACHE_MISS

    async def test_delete_nonexistent(self, cache):
        # Should not raise
        await cache.delete("nonexistent")


class TestAsyncDiskCacheClear:
    async def test_clear(self, cache):
        from lfx.services.cache.utils import CACHE_MISS

        await cache.set("k1", "v1")
        await cache.set("k2", "v2")
        await cache.clear()
        assert await cache.get("k1") is CACHE_MISS
        assert await cache.get("k2") is CACHE_MISS


class TestAsyncDiskCacheUpsert:
    # Note: We pass an explicit lock to avoid a deadlock in AsyncDiskCache._upsert
    # which calls self.set() without passing the lock, causing it to re-acquire self.lock.

    async def test_upsert_new_key(self, cache):
        lock = asyncio.Lock()
        await cache.upsert("key1", "value1", lock=lock)
        result = await cache.get("key1")
        assert result == "value1"

    async def test_upsert_merge_dicts(self, cache):
        lock = asyncio.Lock()
        await cache.set("key1", {"a": 1, "b": 2})
        await cache.upsert("key1", {"b": 3, "c": 4}, lock=lock)
        result = await cache.get("key1")
        assert result == {"a": 1, "b": 3, "c": 4}

    async def test_upsert_replace_non_dict(self, cache):
        lock = asyncio.Lock()
        await cache.set("key1", "old_value")
        await cache.upsert("key1", "new_value", lock=lock)
        result = await cache.get("key1")
        assert result == "new_value"


class TestAsyncDiskCacheContains:
    async def test_contains_existing(self, cache):
        await cache.set("key1", "v")
        assert await cache.contains("key1") is True

    async def test_contains_missing(self, cache):
        assert await cache.contains("nonexistent") is False


class TestAsyncDiskCacheExpiration:
    async def test_expired_item_returns_cache_miss(self, short_expiry_cache):
        from lfx.services.cache.utils import CACHE_MISS

        await short_expiry_cache.set("key1", "value1")
        await asyncio.sleep(0.2)  # Wait for expiration
        result = await short_expiry_cache.get("key1")
        assert result is CACHE_MISS


class TestAsyncDiskCacheTeardown:
    async def test_teardown(self, cache):
        await cache.set("key1", "value1")
        await cache.teardown()
        # After teardown, cache should be cleared
        assert len(cache.cache) == 0


class TestAsyncDiskCacheLocking:
    async def test_get_with_external_lock(self, cache):
        lock = asyncio.Lock()
        await cache.set("key1", "value1")
        async with lock:
            result = await cache.get("key1", lock=lock)
            assert result == "value1"

    async def test_set_with_external_lock(self, cache):
        lock = asyncio.Lock()
        async with lock:
            await cache.set("key1", "value1", lock=lock)
        result = await cache.get("key1")
        assert result == "value1"
