"""Factory for creating KnowledgeHub service instances."""

from typing import TYPE_CHECKING, Optional

from langflow.services.factory import ServiceFactory
from typing_extensions import override

from .service import KnowledgeService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class KnowledgeServiceFactory(ServiceFactory):
    """Factory for creating KnowledgeHub service instances."""

    name = "knowledge_service"

    def __init__(self) -> None:
        """Initialize the Knowledge service factory."""
        super().__init__(KnowledgeService)

    @override
    def create(self, settings_service=None) -> KnowledgeService:
        """Create a new KnowledgeHub service instance.

        Args:
            settings_service: Optional settings service (not used currently)

        Returns:
            KnowledgeService: A configured Knowledge service instance
        """
        # Create service - it will initialize its own settings
        service = KnowledgeService()

        # Set service as ready
        service.set_ready()

        return service