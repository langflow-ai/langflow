# services/ocr/factory.py
from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from typing_extensions import override

from .service import OCRService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class OCRServiceFactory(ServiceFactory):
    """Factory for creating OCR service instances."""

    name = "ocr_service"

    def __init__(self) -> None:
        super().__init__(OCRService)

    @override
    def create(self, settings_service: "SettingsService" = None) -> OCRService:
        """Create a new OCR service instance."""
        # Create service - it will initialize its own settings
        service = OCRService()

        # Set service as ready
        service.set_ready()

        return service
