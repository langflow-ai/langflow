"""Factory for creating ModelHub services."""

from typing import Optional

from langflow.services.base import Service
from langflow.services.factory import ServiceFactory
from loguru import logger

from .service import ModelHubService


class ModelHubServiceFactory(ServiceFactory):
    """Factory for creating ModelHub services."""

    def __init__(self):
        """Initialize the factory."""
        super().__init__(ModelHubService)

    def create(self) -> Optional[Service]:
        """Create a new ModelHub service."""
        try:
            service = ModelHubService()
            service.set_ready()
            return service
        except Exception as e:
            logger.error(f"Error creating ModelHub service: {e!s}")
            return None