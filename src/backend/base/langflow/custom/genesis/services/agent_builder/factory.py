"""Factory for Agent Builder service."""

from langflow.services.factory import ServiceFactory

from .service import AgentBuilderService


class AgentBuilderServiceFactory(ServiceFactory):
    """Factory for creating Agent Builder service."""

    def __init__(self):
        super().__init__(AgentBuilderService)

    def create(self) -> AgentBuilderService:
        """Create Agent Builder service instance."""
        return AgentBuilderService()
