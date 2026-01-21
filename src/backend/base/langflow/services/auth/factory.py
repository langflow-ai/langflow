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
    from langflow.services.auth.base import AuthServiceBase
    from langflow.services.settings.service import SettingsService


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

    def __init__(self):
        # Import here to avoid circular dependencies
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
                sso_config = sso_service._load_from_file(auth_settings.SSO_CONFIG_FILE)
                if sso_config and sso_config.provider == AuthProvider.OIDC and sso_config.oidc:
                    from langflow.services.auth.oidc_service import OIDCAuthService
                    logger.info(f"Initializing OIDC authentication with {sso_config.oidc.provider_name}")
                    return OIDCAuthService(settings_service, sso_config.oidc)
            except Exception as e:
                logger.error(f"Failed to load SSO config from file: {e}")
        
        # Fallback to JWT auth
        logger.warning("SSO enabled but no valid configuration found, using JWT authentication")
        return AuthService(settings_service)
    
    @staticmethod
    def create_auth_service_from_provider(
        settings_service: SettingsService,
        provider: AuthProvider,
        config: dict | None = None,
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
        elif provider == AuthProvider.OIDC:
            # Will be implemented in Phase 2
            raise NotImplementedError("OIDC authentication not yet implemented")
        elif provider == AuthProvider.SAML:
            # Will be implemented in Phase 7
            raise NotImplementedError("SAML authentication not yet implemented")
        elif provider == AuthProvider.LDAP:
            # Will be implemented in Phase 8
            raise NotImplementedError("LDAP authentication not yet implemented")
        else:
            # Fallback to JWT
            return AuthService(settings_service)
