from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.logging.logger import logger
from langflow.services.cache.disk import AsyncDiskCache
from langflow.services.cache.service import AsyncInMemoryCache, CacheService, RedisCache, ThreadingInMemoryCache
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class CacheServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(CacheService)

    @override
    def create(self, settings_service: SettingsService):
        # Here you would have logic to create and configure a CacheService
        # based on the settings_service

        if settings_service.server.cache_type == "redis":
            logger.debug("Creating Redis cache")
            return RedisCache(
                host=settings_service.redis.redis_host,
                port=settings_service.redis.redis_port,
                db=settings_service.redis.redis_db,
                url=settings_service.redis.redis_url,
                expiration_time=settings_service.redis.redis_cache_expire,
            )

        if settings_service.server.cache_type == "memory":
            return ThreadingInMemoryCache(expiration_time=settings_service.server.cache_expire)
        if settings_service.server.cache_type == "async":
            return AsyncInMemoryCache(expiration_time=settings_service.server.cache_expire)
        if settings_service.server.cache_type == "disk":
            return AsyncDiskCache(
                cache_dir=settings_service.database.config_dir,
                expiration_time=settings_service.server.cache_expire,
            )
        return None
