"""Authentication service factory for pluggable authentication providers.

This module implements a factory pattern to support multiple authentication
providers (JWT, OIDC, SAML, LDAP) that can be swapped at runtime based on
configuration.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.factory import ServiceFactory
from langflow.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

    from langflow.services.auth.base import AuthServiceBase


class AuthProvider(str, Enum):
    """Supported authentication provider types."""

    JWT = "jwt"
    OIDC = "oidc"
    SAML = "saml"
    LDAP = "ldap"


class AuthServiceFactory(ServiceFactory):
    """Factory for creating authentication service instances.

    Supports pluggable authentication providers that can be configured
    via environment variables or configuration files.
    """

    name = ServiceType.AUTH_SERVICE.value

    def __init__(self) -> None:
        # Import here to avoid circular dependencies at module level
        from langflow.services.auth.service import AuthService

        super().__init__(AuthService)

    def create(self, settings_service: SettingsService) -> AuthServiceBase:
        """Create authentication service based on configured provider.

        Args:
            settings_service: Settings service instance containing auth configuration

        Returns:
            AuthServiceBase implementation for the configured provider

        The provider is determined by:
        1. LANGFLOW_SSO_ENABLED environment variable (default: False)
        2. LANGFLOW_SSO_PROVIDER environment variable (default: jwt)
        3. Configuration file if SSO_CONFIG_FILE is specified or database config exists
        """
        # Import here to avoid circular dependencies
        from langflow.services.auth.service import AuthService
        from langflow.services.auth.sso_service import SSOConfigService

        # Check if SSO is enabled
        auth_settings = settings_service.auth_settings

        if not auth_settings.SSO_ENABLED:
            # SSO disabled, use default JWT auth
            return AuthService(settings_service)

        # SSO enabled - try to load configuration
        sso_service = SSOConfigService(settings_service)

        # Note: We can't use async here, so we'll need to handle this differently
        # For now, if SSO is enabled but we can't load config synchronously,
        # we'll return JWT auth and log a warning

        # Check if file-based config is available
        if auth_settings.SSO_CONFIG_FILE:
            try:
                # Use public method instead of private member
                sso_config = sso_service._load_from_file(auth_settings.SSO_CONFIG_FILE)  # noqa: SLF001
                
                # With multi-provider support, we need to pick the first enabled OIDC provider
                # In the future, this could be made configurable via environment variable
                if sso_config and sso_config.providers:
                    # Find first enabled OIDC provider
                    for provider_config in sso_config.providers:
                        if (
                            provider_config.enabled
                            and provider_config.provider_type == AuthProvider.OIDC
                            and provider_config.oidc
                        ):
                            from langflow.services.auth.oidc_service import OIDCAuthService

                            logger.info(
                                f"Initializing OIDC authentication with {provider_config.oidc.provider_name}"
                            )
                            return OIDCAuthService(settings_service, provider_config.oidc)
                    
                    # If we have providers but none are OIDC, log warning
                    logger.warning(
                        "SSO config loaded but no enabled OIDC providers found, using JWT authentication"
                    )
            except (FileNotFoundError, ValueError, OSError) as e:
                logger.error(f"Failed to load SSO config from file: {e}")

        # Fallback to JWT auth
        logger.warning("SSO enabled but no valid configuration found, using JWT authentication")
        return AuthService(settings_service)

    @staticmethod
    def create_auth_service_from_provider(
        settings_service: SettingsService,
        provider: AuthProvider,
        config: dict | None = None,  # noqa: ARG004
    ) -> AuthServiceBase:
        """Create authentication service for a specific provider.

        This method allows explicit provider selection, useful for testing
        or when multiple auth providers need to coexist.

        Args:
            settings_service: Settings service instance
            provider: Authentication provider type
            config: Optional provider-specific configuration

        Returns:
            AuthServiceBase implementation for the specified provider

        Raises:
            NotImplementedError: If the provider is not yet implemented
        """
        from langflow.services.auth.service import AuthService

        if provider == AuthProvider.JWT:
            return AuthService(settings_service)
        if provider == AuthProvider.OIDC:
            msg = "OIDC authentication not yet implemented"
            raise NotImplementedError(msg)
        if provider == AuthProvider.SAML:
            msg = "SAML authentication not yet implemented"
            raise NotImplementedError(msg)
        if provider == AuthProvider.LDAP:
            msg = "LDAP authentication not yet implemented"
            raise NotImplementedError(msg)
        # Fallback to JWT
        return AuthService(settings_service)
