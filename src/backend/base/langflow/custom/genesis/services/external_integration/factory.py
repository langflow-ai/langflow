"""Factory for External Integration Service."""

import os
from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory

from .service import ExternalIntegrationService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class ExternalIntegrationServiceFactory(ServiceFactory):
    """Factory for creating ExternalIntegrationService instances."""

    def __init__(self):
        super().__init__(ExternalIntegrationService)

    def create(
        self, settings_service: "SettingsService" = None
    ) -> ExternalIntegrationService:
        """Create service instance from settings or environment variables."""
        # If settings service is available, use it; otherwise use environment variables
        if settings_service and hasattr(settings_service, "settings"):
            genesis_api_url = getattr(
                settings_service.settings,
                "genesis_service_auth_url",
                "http://localhost:8000",
            )
            notification_api_url = getattr(
                settings_service.settings,
                "notification_api_url",
                "http://localhost:8001",
            )
            activity_log_url = getattr(
                settings_service.settings, "activity_log_url", "http://localhost:8002"
            )
            api_key = getattr(
                settings_service.settings, "external_integration_api_key", ""
            )
            client_id = getattr(
                settings_service.settings, "client_id", "genesis_studio_backend"
            )
        else:
            # Fall back to environment variables or defaults
            genesis_api_url = os.getenv(
                "GENESIS_SERVICE_AUTH_URL", "http://localhost:8000"
            )
            notification_api_url = os.getenv(
                "NOTIFICATION_API_URL", "http://localhost:8001"
            )
            activity_log_url = os.getenv("ACTIVITY_LOG_URL", "http://localhost:8002")
            api_key = os.getenv("EXTERNAL_INTEGRATION_API_KEY", "")
            client_id = os.getenv("GENESIS_CLIENT_ID", "genesis_studio_backend")

        service = ExternalIntegrationService(
            genesis_api_url=genesis_api_url,
            notification_api_url=notification_api_url,
            activity_log_url=activity_log_url,
            api_key=api_key,
            client_id=client_id,
        )
        return service
