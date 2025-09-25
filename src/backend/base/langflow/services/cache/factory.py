from __future__ import annotations

from typing import TYPE_CHECKING

# Try to import logger, fallback to standard logging if lfx not available
try:
    from lfx.log.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from typing_extensions import override

from langflow.services.cache.disk import AsyncDiskCache
from langflow.services.cache.service import AsyncInMemoryCache, CacheService, RedisCache, ThreadingInMemoryCache
from langflow.services.cache.utils import setup_rich_pickle_support, validate_rich_pickle_support
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class CacheServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(CacheService)
        # Setup Rich pickle support when factory is initialized
        self._rich_pickle_enabled = setup_rich_pickle_support()
        if self._rich_pickle_enabled:
            logger.debug("Rich pickle support enabled for cache serialization")
            # Optionally validate the support
            if validate_rich_pickle_support():
                logger.debug("Rich pickle support validation successful")
            else:
                logger.warning("Rich pickle support validation failed")
        else:
            logger.info("Rich pickle support could not be enabled")

    @override
    def create(self, settings_service: SettingsService):
        # Here you would have logic to create and configure a CacheService
        # based on the settings_service

        # Debug: Log the cache type being used
        cache_type = settings_service.settings.cache_type
        logger.info(f"Cache factory creating cache with type: {cache_type}")

        if settings_service.settings.cache_type == "redis":
            logger.debug("Creating Redis cache")
            cache = RedisCache(
                host=settings_service.settings.redis_host,
                port=settings_service.settings.redis_port,
                db=settings_service.settings.redis_db,
                url=settings_service.settings.redis_url,
                expiration_time=settings_service.settings.redis_cache_expire,
            )

            # Log Rich pickle status for Redis caches
            if self._rich_pickle_enabled:
                logger.info("Redis cache created with Rich object serialization support")
            else:
                logger.warning(
                    "Redis cache created without Rich object serialization - may cause issues with console objects"
                )

            return cache

        if settings_service.settings.cache_type == "memory":
            return ThreadingInMemoryCache(expiration_time=settings_service.settings.cache_expire)
        if settings_service.settings.cache_type == "async":
            return AsyncInMemoryCache(expiration_time=settings_service.settings.cache_expire)
        if settings_service.settings.cache_type == "disk":
            return AsyncDiskCache(
                cache_dir=settings_service.settings.config_dir,
                expiration_time=settings_service.settings.cache_expire,
            )
        return None
