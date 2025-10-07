"""Factory for creating and managing FlowCacheService instances."""

from langflow.services.factory import ServiceFactory
from langflow.services.flow_cache.service import FlowCacheService


class FlowCacheServiceFactory(ServiceFactory):
    """Factory for creating FlowCacheService instances with singleton pattern."""

    def __init__(self) -> None:
        """Initialize the FlowCacheServiceFactory."""
        super().__init__(FlowCacheService)
        self._flow_cache_service_instance: FlowCacheService | None = None

    def create(self):
        """Create or return the cached FlowCacheService instance.

        Returns:
            FlowCacheService: The singleton FlowCacheService instance
        """
        # Cache the FlowCacheService instance to avoid repeated instantiation
        if self._flow_cache_service_instance is None:
            self._flow_cache_service_instance = FlowCacheService()
        return self._flow_cache_service_instance
