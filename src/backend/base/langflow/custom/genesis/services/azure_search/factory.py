"""Factory for Azure AI Search service."""

from langflow.services.factory import ServiceFactory

from .service import AzureSearchService


class AzureSearchServiceFactory(ServiceFactory):
    """Factory for creating Azure AI Search service."""

    def __init__(self):
        super().__init__(AzureSearchService)

    def create(self) -> AzureSearchService:
        """Create Azure AI Search service instance."""
        return AzureSearchService()
