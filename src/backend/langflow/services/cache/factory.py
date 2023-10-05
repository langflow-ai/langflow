from langflow.services.cache.manager import InMemoryCache, RedisCache, BaseCacheService
from langflow.services.factory import ServiceFactory
from langflow.utils.logger import logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.settings.manager import SettingsService


class CacheServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(BaseCacheService)

    def create(self, settings_service: "SettingsService"):
        # Here you would have logic to create and configure a CacheService
        # based on the settings_service

        if settings_service.settings.CACHE_TYPE == "redis":
            logger.debug("Creating Redis cache")
            redis_cache = RedisCache(
                host=settings_service.settings.REDIS_HOST,
                port=settings_service.settings.REDIS_PORT,
                db=settings_service.settings.REDIS_DB,
                expiration_time=settings_service.settings.REDIS_CACHE_EXPIRE,
            )
            if redis_cache.is_connected():
                logger.debug("Redis cache is connected")
                return redis_cache
            logger.warning(
                "Redis cache is not connected, falling back to in-memory cache"
            )
            return InMemoryCache()

        elif settings_service.settings.CACHE_TYPE == "memory":
            return InMemoryCache()
