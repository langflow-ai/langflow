"""Factory for creating MCP Composer service instances."""

from lfx.services.factory import ServiceFactory
from lfx.services.mcp_composer.service import MCPComposerService


class MCPComposerServiceFactory(ServiceFactory):
    """Factory for creating MCP Composer service instances."""

    def __init__(self):
        super().__init__(MCPComposerService)

    def create(self):
        """Create a new MCP Composer service instance."""
        return MCPComposerService()
