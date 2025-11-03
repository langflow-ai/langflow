"""Factory for creating background agent service."""

from langflow.services.background_agent.service import BackgroundAgentService
from langflow.services.factory import ServiceFactory


class BackgroundAgentServiceFactory(ServiceFactory):
    """Factory for creating background agent service."""

    def __init__(self):
        super().__init__(BackgroundAgentService)

    def create(self, settings_service):
        """Create a background agent service instance.

        Args:
            settings_service: Settings service instance

        Returns:
            BackgroundAgentService instance
        """
        return BackgroundAgentService(settings_service)
