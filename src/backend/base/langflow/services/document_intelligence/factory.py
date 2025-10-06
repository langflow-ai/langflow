"""Factory for Document Intelligence Service."""

from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from typing_extensions import override

from .service import DocumentIntelligenceService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class DocumentIntelligenceServiceFactory(ServiceFactory):
    """Factory for creating Document Intelligence service instances."""

    name = "document_intelligence_service"

    def __init__(self) -> None:
        super().__init__(DocumentIntelligenceService)

    @override
    def create(self, settings_service: "SettingsService" = None) -> DocumentIntelligenceService:
        """Create a new Document Intelligence service instance."""
        # Create service - it will initialize its own settings
        service = DocumentIntelligenceService()

        # Try to set service as ready - will fail gracefully if Azure SDK not available
        try:
            service.set_ready()
        except ValueError as e:
            # Log warning but don't fail - service can still be created for fallback
            from loguru import logger
            logger.warning(f"Document Intelligence service not fully ready: {e}")

        return service