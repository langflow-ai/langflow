import threading

import pytest
from langflow.services.cache import service as cache_service


class FakeRedisClient:
    def __init__(self, *, setex_result=True) -> None:
        self.setex_result = setex_result
        self.setex_calls = []

    async def setex(self, *args):
        self.setex_calls.append(args)
        return self.setex_result


def make_redis_cache(client: FakeRedisClient):
    cache = cache_service.RedisCache.__new__(cache_service.RedisCache)
    cache._client = client
    cache.expiration_time = 3600
    return cache


@pytest.mark.asyncio
async def test_redis_cache_set_skips_values_that_dill_cannot_pickle(monkeypatch):
    client = FakeRedisClient()
    cache = make_redis_cache(client)
    warnings = []

    async def record_warning(message):
        warnings.append(message)

    monkeypatch.setattr(cache_service.logger, "awarning", record_warning)

    await cache.set("flow-cache-key", {"result": threading.local()})

    assert client.setex_calls == []
    assert len(warnings) == 1
    assert "flow-cache-key" in warnings[0]
    assert "_thread._local" in warnings[0]


@pytest.mark.asyncio
async def test_redis_cache_set_stores_pickled_values():
    client = FakeRedisClient()
    cache = make_redis_cache(client)

    await cache.set("flow-cache-key", {"result": "ok"})

    assert len(client.setex_calls) == 1
    assert client.setex_calls[0][0] == "flow-cache-key"
    assert client.setex_calls[0][1] == 3600
    assert cache_service.dill.loads(client.setex_calls[0][2]) == {"result": "ok"}


@pytest.mark.asyncio
async def test_redis_cache_set_raises_when_redis_setex_fails():
    client = FakeRedisClient(setex_result=False)
    cache = make_redis_cache(client)

    with pytest.raises(ValueError, match=r"RedisCache could not set the value\."):
        await cache.set("flow-cache-key", {"result": "ok"})
