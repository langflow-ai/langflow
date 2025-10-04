"""Factory for creating AI Gateway service instances."""

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.factory import ServiceFactory

from .service import AIGatewayService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class AIGatewayServiceFactory(ServiceFactory):
    """Factory for creating AI Gateway service instances."""

    name = "ai_gateway_service"

    def __init__(self) -> None:
        super().__init__(AIGatewayService)

    @override
    def create(self, settings_service: "SettingsService" = None) -> AIGatewayService:
        """Create a new AI Gateway service instance."""
        return AIGatewayService()
