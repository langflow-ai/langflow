"""Factory for creating prompt services."""

from typing import Optional

from langflow.services.base import Service
from langflow.services.factory import ServiceFactory
from loguru import logger

from .service import PromptService


class PromptServiceFactory(ServiceFactory):
    """Factory for creating prompt services."""

    def __init__(self):
        """Initialize the factory."""
        super().__init__(PromptService)

    def create(self) -> Optional[Service]:
        """Create a new prompt service."""
        try:
            service = PromptService()
            service.set_ready()
            return service
        except Exception as e:
            logger.error(f"Error creating prompt service: {e!s}")
            return None
