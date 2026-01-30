"""Authentication service factory.

This module implements a factory pattern for creating authentication service instances.
Currently supports JWT-based authentication. Future authentication providers (OIDC, SAML, LDAP)
can be added via plugins/extensions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.schema import ServiceType

if TYPE_CHECKING:
    from langflow.services.auth.base import AuthServiceBase
    from langflow.services.settings.service import SettingsService


class AuthServiceFactory(ServiceFactory):
    """Factory for creating authentication service instances.

    Currently returns JWT-based authentication service.
    Future authentication providers can be added via plugins/extensions.
    """

    name = ServiceType.AUTH_SERVICE.value

    def __init__(self):
        # Import here to avoid circular dependencies
        from langflow.services.auth.service import AuthService

        super().__init__(AuthService)

    def create(self, settings_service: SettingsService) -> AuthServiceBase:
        """Create JWT authentication service.

        Args:
            settings_service: Settings service instance containing auth configuration

        Returns:
            AuthService instance (JWT-based authentication)
        """
        # Import here to avoid circular dependencies
        from langflow.services.auth.service import AuthService

        return AuthService(settings_service)
