"""Factory for creating shared component cache service."""

from typing import TYPE_CHECKING

from lfx.services.factory import ServiceFactory
from lfx.services.shared_component_cache.service import SharedComponentCacheService

if TYPE_CHECKING:
    from lfx.services.base import Service


class SharedComponentCacheServiceFactory(ServiceFactory):
    """Factory for creating SharedComponentCacheService instances."""

    def __init__(self) -> None:
        """Initialize the factory."""
        super().__init__()
        self.service_class = SharedComponentCacheService

    def create(self, **kwargs) -> "Service":
        """Create a SharedComponentCacheService instance.

        Args:
            **kwargs: Keyword arguments including expiration_time

        Returns:
            SharedComponentCacheService instance
        """
        expiration_time = kwargs.get("expiration_time", 60 * 60)  # Default 1 hour
        return SharedComponentCacheService(expiration_time=expiration_time)
