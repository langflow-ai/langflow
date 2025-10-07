from langflow.services.factory import ServiceFactory
from langflow.services.flow_cache.service import FlowCacheService


class FlowCacheServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(FlowCacheService)
        self._flow_cache_service_instance: FlowCacheService | None = None

    def create(self):
        # Cache the FlowCacheService instance to avoid repeated instantiation
        if self._flow_cache_service_instance is None:
            self._flow_cache_service_instance = FlowCacheService()
        return self._flow_cache_service_instance
