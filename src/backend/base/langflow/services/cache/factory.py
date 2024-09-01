from typing import TYPE_CHECKING

from langflow.services.cache.disk import AsyncDiskCache
from langflow.services.cache.service import AsyncInMemoryCache, CacheService, RedisCache, ThreadingInMemoryCache
from langflow.services.factory import ServiceFactory
from langflow.logging.logger import logger

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class CacheServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(CacheService)

    def create(self, settings_service: "SettingsService"):
        # Here you would have logic to create and configure a CacheService
        # based on the settings_service

        if settings_service.settings.cache_type == "redis":
            logger.debug("Creating Redis cache")
            redis_cache: RedisCache = RedisCache(
                host=settings_service.settings.redis_host,
                port=settings_service.settings.redis_port,
                db=settings_service.settings.redis_db,
                url=settings_service.settings.redis_url,
                expiration_time=settings_service.settings.redis_cache_expire,
            )
            if redis_cache.is_connected():
                logger.debug("Redis cache is connected")
                return redis_cache
            else:
                # do not attempt to fallback to another cache type
                raise ConnectionError("Failed to connect to Redis cache")

        elif settings_service.settings.cache_type == "memory":
            return ThreadingInMemoryCache(expiration_time=settings_service.settings.cache_expire)
        elif settings_service.settings.cache_type == "async":
            return AsyncInMemoryCache(expiration_time=settings_service.settings.cache_expire)
        elif settings_service.settings.cache_type == "disk":
            return AsyncDiskCache(
                cache_dir=settings_service.settings.config_dir,
                expiration_time=settings_service.settings.cache_expire,
            )
