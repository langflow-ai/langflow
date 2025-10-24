"""Factory for creating FlexStore service instances."""

from typing import TYPE_CHECKING, Optional

from langflow.services.factory import ServiceFactory
from typing_extensions import override

from .service import FlexStoreService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class FlexStoreServiceFactory(ServiceFactory):
    """Factory for creating FlexStore service instances."""

    name = "flexstore_service"

    def __init__(self) -> None:
        """Initialize the FlexStore service factory."""
        super().__init__(FlexStoreService)

    @override
    def create(self, settings_service=None) -> FlexStoreService:
        """Create a new FlexStore service instance.

        Args:
            settings_service: Optional settings service (not used currently)

        Returns:
            FlexStoreService: A configured FlexStore service instance
        """
        # Create service - it will initialize its own settings
        service = FlexStoreService()

        # Set service as ready
        service.set_ready()

        return service