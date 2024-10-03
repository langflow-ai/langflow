from langflow.services.cache import CacheService


class SharedComponentCacheService(CacheService):
    """
    A caching service shared across components.
    """
    name = "shared_component_cache_service"

