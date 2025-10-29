from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory

from .service import ConnectorService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class ConnectorServiceFactory(ServiceFactory):
    """Factory for creating ConnectorService instances."""

    def __init__(self):
        super().__init__(ConnectorService)

    def create(self, settings_service: "SettingsService") -> ConnectorService:
        """Create a ConnectorService instance.

        Args:
            settings_service: Settings service for configuration

        Returns:
            Configured ConnectorService
        """
        return ConnectorService(settings_service=settings_service)
