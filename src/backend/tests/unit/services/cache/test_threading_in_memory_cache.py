"""Tests for ThreadingInMemoryCache."""

import time

from langflow.services.cache.service import ThreadingInMemoryCache
from lfx.services.cache.utils import CACHE_MISS


class TestThreadingInMemoryCacheBasic:
    """Basic get/set/delete/clear operations."""

    def test_set_and_get(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key_returns_cache_miss(self):
        cache = ThreadingInMemoryCache()
        result = cache.get("nonexistent")
        assert result is CACHE_MISS

    def test_set_overwrites_existing(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_delete(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is CACHE_MISS

    def test_delete_nonexistent_key(self):
        cache = ThreadingInMemoryCache()
        cache.delete("nonexistent")  # Should not raise

    def test_clear(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is CACHE_MISS
        assert cache.get("key2") is CACHE_MISS
        assert len(cache) == 0

    def test_contains(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", "value1")
        assert cache.contains("key1") is True
        assert cache.contains("nonexistent") is False

    def test_dunder_contains(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", "value1")
        assert "key1" in cache
        assert "nonexistent" not in cache

    def test_len(self):
        cache = ThreadingInMemoryCache()
        assert len(cache) == 0
        cache.set("key1", "value1")
        assert len(cache) == 1
        cache.set("key2", "value2")
        assert len(cache) == 2

    def test_repr(self):
        cache = ThreadingInMemoryCache(max_size=10, expiration_time=300)
        assert "max_size=10" in repr(cache)
        assert "expiration_time=300" in repr(cache)


class TestThreadingInMemoryCacheBracketNotation:
    """Tests for bracket notation access."""

    def test_getitem(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", "value1")
        assert cache["key1"] == "value1"

    def test_setitem(self):
        cache = ThreadingInMemoryCache()
        cache["key1"] = "value1"
        assert cache.get("key1") == "value1"

    def test_delitem(self):
        cache = ThreadingInMemoryCache()
        cache["key1"] = "value1"
        del cache["key1"]
        assert cache.get("key1") is CACHE_MISS


class TestThreadingInMemoryCacheLRU:
    """Tests for LRU eviction behavior."""

    def test_max_size_eviction(self):
        cache = ThreadingInMemoryCache(max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        # Adding a 4th should evict the least recently used (key1)
        cache.set("key4", "value4")
        assert cache.get("key1") is CACHE_MISS
        assert cache.get("key4") == "value4"
        assert len(cache) == 3

    def test_access_refreshes_lru_order(self):
        cache = ThreadingInMemoryCache(max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        # Access key1 to make it recently used
        cache.get("key1")
        # Adding key4 should now evict key2 (least recently used)
        cache.set("key4", "value4")
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is CACHE_MISS


class TestThreadingInMemoryCacheExpiration:
    """Tests for expiration behavior."""

    def test_expired_item_returns_cache_miss(self):
        cache = ThreadingInMemoryCache(expiration_time=0.1)
        cache.set("key1", "value1")
        time.sleep(0.5)
        result = cache.get("key1")
        assert result is CACHE_MISS

    def test_non_expired_item_returns_value(self):
        cache = ThreadingInMemoryCache(expiration_time=3600)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_no_expiration(self):
        cache = ThreadingInMemoryCache(expiration_time=None)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"


class TestThreadingInMemoryCacheUpsert:
    """Tests for upsert behavior."""

    def test_upsert_new_key(self):
        cache = ThreadingInMemoryCache()
        cache.upsert("key1", {"a": 1})
        assert cache.get("key1") == {"a": 1}

    def test_upsert_merges_dicts(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", {"a": 1, "b": 2})
        cache.upsert("key1", {"b": 3, "c": 4})
        result = cache.get("key1")
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_upsert_non_dict_replaces(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", "old_value")
        cache.upsert("key1", "new_value")
        assert cache.get("key1") == "new_value"


class TestThreadingInMemoryCacheGetOrSet:
    """Tests for get_or_set behavior."""

    def test_get_or_set_returns_existing(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", "existing")
        result = cache.get_or_set("key1", "new_value")
        assert result == "existing"

    def test_get_or_set_sets_and_returns_new(self):
        cache = ThreadingInMemoryCache()
        result = cache.get_or_set("key1", "new_value")
        assert result == "new_value"
        assert cache.get("key1") == "new_value"


class TestThreadingInMemoryCacheDataTypes:
    """Tests for various data types."""

    def test_store_dict(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", {"nested": {"data": True}})
        assert cache.get("key1") == {"nested": {"data": True}}

    def test_store_list(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", [1, 2, 3])
        assert cache.get("key1") == [1, 2, 3]

    def test_store_none(self):
        cache = ThreadingInMemoryCache()
        cache.set("key1", None)
        # None is stored, but the cache retrieval checks if item is truthy
        # so None value in cache may behave differently
        result = cache.get("key1")
        # The cache stores {"value": None, "time": ...} which is truthy
        assert result is None

    def test_store_numeric(self):
        cache = ThreadingInMemoryCache()
        cache.set("int_key", 42)
        cache.set("float_key", 3.14)
        assert cache.get("int_key") == 42
        assert cache.get("float_key") == 3.14

    def test_store_boolean(self):
        cache = ThreadingInMemoryCache()
        true_val = True
        false_val = False
        cache.set("true_key", true_val)
        cache.set("false_key", false_val)
        assert cache.get("true_key") is True
        # False is falsy, so cache item check might fail
        # But the item dict itself is truthy
        assert cache.get("false_key") is False
