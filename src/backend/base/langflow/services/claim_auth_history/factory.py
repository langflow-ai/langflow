"""Factory for creating ClaimAuthHistoryService instances."""

from typing import override
from langflow.services.factory import ServiceFactory
from .service import ClaimAuthHistoryService


class ClaimAuthHistoryServiceFactory(ServiceFactory):
    """Factory for creating ClaimAuthHistoryService instances."""

    name = "claim_auth_history_service"

    def __init__(self):
        """Initialize the ClaimAuthHistoryServiceFactory."""
        super().__init__(ClaimAuthHistoryService)

    @override
    def create(self, **kwargs):
        """Create a new ClaimAuthHistoryService instance."""
        return ClaimAuthHistoryService()
