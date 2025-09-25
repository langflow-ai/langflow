"""Factory for creating RAG service instances."""

from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from typing_extensions import override

from .service import RAGService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class RAGServiceFactory(ServiceFactory):
    """Factory for creating RAG QnA service instances."""

    name = "rag_service"

    def __init__(self) -> None:
        super().__init__(RAGService)

    @override
    def create(self) -> RAGService:
        """Create a new RAG QnA service instance."""
        return RAGService()
