import pickle

import pytest
from langflow.services.cache.service import RedisCache
from lfx.services.cache.utils import CACHE_MISS


class _FakeRedisClient:
    """Minimal Redis client double that records cache mutations."""

    def __init__(self) -> None:
        self.values = {}
        self.deleted_keys = []

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, _expiration_time, value):
        self.values[key] = value
        return True

    async def delete(self, key):
        self.deleted_keys.append(key)
        self.values.pop(key, None)
        return 1


class _UnpickleableValue:
    """Value that raises a configured exception during pickling."""

    def __init__(self, exception_type: type[Exception]) -> None:
        self.exception_type = exception_type

    def __getstate__(self):
        raise self.exception_type


@pytest.mark.parametrize("exception_type", [pickle.PicklingError, TypeError, AttributeError])
@pytest.mark.asyncio
async def test_redis_cache_skips_unpickleable_values_and_clears_stale_entry(exception_type):
    """Unpickleable values should not leave stale Redis entries behind."""
    cache = RedisCache.__new__(RedisCache)
    cache._client = _FakeRedisClient()
    cache.expiration_time = 3600

    cache_key = 123
    await cache.set(cache_key, {"previous": "value"})
    assert await cache.get(cache_key) == {"previous": "value"}
    assert "123" in cache._client.values
    assert 123 not in cache._client.values

    await cache.set(cache_key, _UnpickleableValue(exception_type))

    assert await cache.get(cache_key) is CACHE_MISS
    assert cache._client.deleted_keys == ["123"]


@pytest.mark.asyncio
async def test_redis_cache_delete_normalizes_keys():
    """Direct Redis cache deletes should normalize keys like get and set."""
    cache = RedisCache.__new__(RedisCache)
    cache._client = _FakeRedisClient()
    cache.expiration_time = 3600

    await cache.set(123, {"value": "cached"})
    await cache.delete(123)

    assert await cache.get(123) is CACHE_MISS
    assert cache._client.deleted_keys == ["123"]
