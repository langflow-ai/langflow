"""Authentication service factory.

Builds the Langflow auth implementation (JWT, DB users, etc.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.auth.base import BaseAuthService  # noqa: TC002
from lfx.services.settings.service import SettingsService  # noqa: TC002

from langflow.services.factory import ServiceFactory
from langflow.services.schema import ServiceType

if TYPE_CHECKING:
    from langflow.services.auth.service import AuthService


class AuthServiceFactory(ServiceFactory):
    """Factory that creates the Langflow auth service (implements LFX BaseAuthService)."""

    name = ServiceType.AUTH_SERVICE.value

    # Narrow type from parent's type[Service] so create() can call with settings_service
    service_class: type[AuthService]

    def __init__(self) -> None:
        # Import here to avoid circular dependencies; stored on instance by parent
        from langflow.services.auth.service import AuthService

        super().__init__(AuthService)

    def create(self, settings_service: SettingsService) -> BaseAuthService:
        """Create JWT authentication service.

        Args:
            settings_service: Settings service instance containing auth configuration

        Returns:
            AuthService instance (JWT-based authentication)
        """
        return self.service_class(settings_service)
