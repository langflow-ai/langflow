import pytest
from langflow.services.cache.service import RedisCache
from lfx.services.cache.utils import CACHE_MISS


class _FakeRedisClient:
    def __init__(self) -> None:
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, _expiration_time, value):
        self.values[key] = value
        return True

    async def delete(self, key):
        self.values.pop(key, None)
        return 1


class _UnpickleableValue:
    def __getstate__(self):
        raise TypeError


@pytest.mark.asyncio
async def test_redis_cache_skips_unpickleable_values_and_clears_stale_entry():
    cache = RedisCache.__new__(RedisCache)
    cache._client = _FakeRedisClient()
    cache.expiration_time = 3600

    cache_key = 123
    await cache.set(cache_key, {"previous": "value"})
    assert await cache.get(cache_key) == {"previous": "value"}

    await cache.set(cache_key, _UnpickleableValue())

    assert await cache.get(cache_key) is CACHE_MISS
