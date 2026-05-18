import pytest
from langflow.services.cache import service as cache_service


class FakeRedisClient:
    def __init__(self) -> None:
        self.setex_calls = []

    async def setex(self, *args):
        self.setex_calls.append(args)
        return True


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

    def raise_type_error(*_args, **_kwargs):
        msg = "cannot pickle 'ConsoleThreadLocals' object"
        raise TypeError(msg)

    async def record_warning(message):
        warnings.append(message)

    monkeypatch.setattr(cache_service.dill, "dumps", raise_type_error)
    monkeypatch.setattr(cache_service.logger, "awarning", record_warning)

    await cache.set("flow-cache-key", {"result": object()})

    assert client.setex_calls == []
    assert len(warnings) == 1
    assert "flow-cache-key" in warnings[0]
    assert "ConsoleThreadLocals" in warnings[0]


@pytest.mark.asyncio
async def test_redis_cache_set_stores_pickled_values():
    client = FakeRedisClient()
    cache = make_redis_cache(client)

    await cache.set("flow-cache-key", {"result": "ok"})

    assert len(client.setex_calls) == 1
    assert client.setex_calls[0][0] == "flow-cache-key"
    assert client.setex_calls[0][1] == 3600
    assert cache_service.dill.loads(client.setex_calls[0][2]) == {"result": "ok"}
