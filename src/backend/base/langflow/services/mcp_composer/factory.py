"""Factory for creating MCP Composer service instances."""

from langflow.services.factory import ServiceFactory
from langflow.services.mcp_composer.service import MCPComposerService


class MCPComposerServiceFactory(ServiceFactory):
    """Factory for creating MCP Composer service instances."""

    def __init__(self):
        super().__init__(MCPComposerService)

    def create(self):
        """Create a new MCP Composer service instance."""
        return MCPComposerService()
