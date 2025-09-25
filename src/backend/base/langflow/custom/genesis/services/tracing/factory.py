"""
Factory for creating tracing services for Genesis Studio Backend.
"""

from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService

from .service import TracingService


class TracingServiceFactory(ServiceFactory):
    """Factory for creating TracingService instances."""

    def __init__(self):
        super().__init__(TracingService)

    def create(self, settings_service: "SettingsService"):
        """Create a TracingService instance."""
        return TracingService(settings_service)


def register_tracing_service() -> bool:
    """Register the custom tracing service with Langflow.

    Returns:
        bool: True if registration was successful, False otherwise.
    """
    try:
        from langflow.services.manager import ServiceManager

        # Get the service manager and register our custom tracing service factory
        service_manager = ServiceManager()
        service_manager.register_factory(TracingServiceFactory())

        print("✅ Genesis TracingService registered successfully")
        return True
    except Exception as e:
        print(f"⚠️  Failed to register tracing service: {e}")
        return False
