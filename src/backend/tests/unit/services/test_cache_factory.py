from types import SimpleNamespace

from langflow.services.cache.factory import CacheServiceFactory
from langflow.services.cache.service import AsyncInMemoryCache


def test_disk_cache_type_falls_back_to_async_in_memory_cache():
    settings_service = SimpleNamespace(
        settings=SimpleNamespace(
            cache_type="disk",
            cache_expire=123,
        )
    )

    cache = CacheServiceFactory().create(settings_service)

    assert isinstance(cache, AsyncInMemoryCache)
    assert cache.expiration_time == 123
