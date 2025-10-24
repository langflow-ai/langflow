"""Factory for creating EncoderProService instances."""

from typing import override
from langflow.services.factory import ServiceFactory
from .service import EncoderProService


class EncoderProServiceFactory(ServiceFactory):
    """Factory for creating EncoderProService instances."""

    name = "encoder_pro_service"

    def __init__(self):
        """Initialize the EncoderProServiceFactory."""
        super().__init__(EncoderProService)

    @override
    def create(self) -> EncoderProService:
        """Create a new EncoderProService instance."""
        return EncoderProService()
