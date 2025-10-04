from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from typing_extensions import override

from .service import FlexStoreService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class FlexStoreServiceFactory(ServiceFactory):
    """Factory for creating FlexStore service instances."""

    name = "flexstore_service"

    def __init__(self) -> None:
        super().__init__(FlexStoreService)

    @override
    def create(self, settings_service: "SettingsService" = None) -> FlexStoreService:
        """Create a new FlexStore service instance."""
        # Create service - it will initialize its own settings
        service = FlexStoreService()

        # Set service as ready
        service.set_ready()

        return service
