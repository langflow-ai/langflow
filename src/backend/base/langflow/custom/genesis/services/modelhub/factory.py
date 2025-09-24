"""Factory for creating ModelHub service instances."""

from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from typing_extensions import override
from .service import ModelHubService


if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class ModelHubServiceFactory(ServiceFactory):
    """Factory for creating ModelHub service instances."""

    name = "modelhub_service"

    def __init__(self) -> None:
        super().__init__(ModelHubService)

    @override
    def create(self, settings_service: "SettingsService" = None) -> ModelHubService:
        """Create a new ModelHub service instance."""
        # Create service - it will initialize its own settings
        service = ModelHubService()

        # Ensure the service is marked as ready after successful creation
        try:
            service.set_ready()
        except Exception as e:
            from loguru import logger
            logger.warning(f"ModelHub service could not be set as ready: {e}")

        return service
