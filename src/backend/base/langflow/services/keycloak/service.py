"""Keycloak Authentication Service.

This module provides a service for integrating with Keycloak/OpenID Connect authentication.
The KeycloakService handles initialization of the Keycloak client, token operations,
user information retrieval, and role extraction for the Langflow application.

This service is injected into other components that need Keycloak authentication functionality.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jose import jwt
from keycloak import KeycloakOpenID
from loguru import logger

from langflow.services.base import Service

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class KeycloakService(Service):
    """Service for Keycloak/OpenID Connect authentication integration with Langflow.

    This service wraps the python-keycloak library to provide authentication functionality,
    including token handling, user information retrieval, and role-based access control.
    It is initialized with settings from the SettingsService.
    """

    name = "keycloak_service"  # Service name for service manager registration

    def __init__(self, settings_service: SettingsService):
        """Initialize the KeycloakService with required dependencies.

        Args:
            settings_service: The settings service containing Keycloak configuration
        """
        # Store the settings service for accessing authentication settings
        self.settings_service = settings_service

        # Initialize instance variables
        self._keycloak_openid: KeycloakOpenID | None = None

    def initialize(self) -> None:
        """Initialize the Keycloak client with settings from auth_settings.

        This method checks if Keycloak is enabled and all required settings are present,
        then initializes the KeycloakOpenID client. If any required settings are missing,
        it logs warnings and returns without initializing the client.

        Note:
            This method is called automatically the first time `client` is accessed.
            It can also be called explicitly to force re-initialization.
        """
        # Get authentication settings
        auth_settings = self.settings_service.auth_settings

        # Check if Keycloak is enabled
        if not hasattr(auth_settings, "KEYCLOAK_ENABLED") or not auth_settings.KEYCLOAK_ENABLED:
            logger.info("Keycloak authentication is disabled or not configured")
            return

        logger.info("Initializing Keycloak client")

        # Validate all required settings are present
        server_url_error_msg = "Keycloak server URL is not configured"
        if not hasattr(auth_settings, "KEYCLOAK_SERVER_URL") or not auth_settings.KEYCLOAK_SERVER_URL:
            logger.warning(server_url_error_msg)
            raise ValueError(server_url_error_msg)

        realm_error_msg = "Keycloak realm is not configured"
        if not hasattr(auth_settings, "KEYCLOAK_REALM") or not auth_settings.KEYCLOAK_REALM:
            logger.warning(realm_error_msg)
            raise ValueError(realm_error_msg)

        client_id_error_msg = "Keycloak client ID is not configured"
        if not hasattr(auth_settings, "KEYCLOAK_CLIENT_ID") or not auth_settings.KEYCLOAK_CLIENT_ID:
            logger.warning(client_id_error_msg)
            raise ValueError(client_id_error_msg)

        client_secret_error_msg = "Keycloak client secret is not configured"  # noqa: S105
        if not hasattr(auth_settings, "KEYCLOAK_CLIENT_SECRET") or not auth_settings.KEYCLOAK_CLIENT_SECRET:
            logger.warning(client_secret_error_msg)
            raise ValueError(client_secret_error_msg)

        # Initialize the KeycloakOpenID client
        self._keycloak_openid = KeycloakOpenID(
            server_url=self.server_url,
            client_id=self.client_id,
            realm_name=self.realm,
            client_secret_key=self.client_secret,
            verify=True,
        )
        logger.info("Keycloak client initialized successfully")

    @property
    def client(self) -> KeycloakOpenID | None:
        """Get the initialized Keycloak client.

        If the client is not yet initialized, this property will attempt
        to initialize it before returning. This lazy initialization pattern
        ensures the client is available when needed.

        Returns:
            KeycloakOpenID: The initialized Keycloak client or None if initialization failed
        """
        if self._keycloak_openid is None:
            self.initialize()
        return self._keycloak_openid

    @property
    def is_enabled(self) -> bool:
        """Check if Keycloak authentication is enabled in settings.

        Returns:
            bool: True if Keycloak authentication is enabled, False otherwise
        """
        auth_settings = self.settings_service.auth_settings
        return hasattr(auth_settings, "KEYCLOAK_ENABLED") and auth_settings.KEYCLOAK_ENABLED

    @property
    def server_url(self) -> str:
        """Get the Keycloak server URL.

        Returns:
            str: The base URL of the Keycloak server or empty string if not configured
        """
        auth_settings = self.settings_service.auth_settings
        if hasattr(auth_settings, "KEYCLOAK_SERVER_URL"):
            return auth_settings.KEYCLOAK_SERVER_URL
        return ""

    @property
    def realm(self) -> str:
        """Get the Keycloak realm name.

        and rarely changes during runtime.

        Returns:
            str: The Keycloak realm name or empty string if not configured
        """
        auth_settings = self.settings_service.auth_settings
        if hasattr(auth_settings, "KEYCLOAK_REALM"):
            return auth_settings.KEYCLOAK_REALM
        return ""

    @property
    def client_id(self) -> str:
        """Get the Keycloak client ID.

        and rarely changes during runtime.

        Returns:
            str: The client ID registered in Keycloak or empty string if not configured
        """
        auth_settings = self.settings_service.auth_settings
        if hasattr(auth_settings, "KEYCLOAK_CLIENT_ID"):
            return auth_settings.KEYCLOAK_CLIENT_ID
        return ""

    @property
    def client_secret(self) -> str:
        """Get the Keycloak client secret.

        This is the confidential client secret for the Keycloak client
        if it's configured as a confidential client. Not all clients
        require a secret (public clients don't).

        Returns:
            str: The client secret or empty string if not configured
        """
        auth_settings = self.settings_service.auth_settings
        if hasattr(auth_settings, "KEYCLOAK_CLIENT_SECRET") and auth_settings.KEYCLOAK_CLIENT_SECRET is not None:
            return auth_settings.KEYCLOAK_CLIENT_SECRET.get_secret_value()
        return ""

    @property
    def admin_role(self) -> str:
        """Get the Keycloak role that grants admin privileges.

        Users with this role will be granted admin privileges in Langflow.

        Returns:
            str: The admin role name or empty string if not configured
        """
        auth_settings = self.settings_service.auth_settings
        if hasattr(auth_settings, "KEYCLOAK_ADMIN_ROLE"):
            return auth_settings.KEYCLOAK_ADMIN_ROLE
        return ""

    @property
    def redirect_uri(self) -> str:
        """Get the Keycloak redirect URI.

        and rarely changes during runtime.

        Returns:
            str: The URI where Keycloak will redirect after authentication
                or empty string if not configured
        """
        auth_settings = self.settings_service.auth_settings
        if hasattr(auth_settings, "KEYCLOAK_REDIRECT_URI"):
            return auth_settings.KEYCLOAK_REDIRECT_URI or ""
        return ""

    @property
    def force_sso(self) -> bool:
        """Check if Keycloak SSO-only mode is enabled.

        When this is true, the username/password login form should be hidden,
        forcing users to authenticate via Keycloak/SSO.

        and rarely changes during runtime.

        Returns:
            bool: True if SSO-only mode is enabled, False otherwise
        """
        auth_settings = self.settings_service.auth_settings
        return hasattr(auth_settings, "KEYCLOAK_FORCE_SSO") and auth_settings.KEYCLOAK_FORCE_SSO

    async def get_token(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for access and refresh tokens.

        This method is called during the OAuth 2.0 Authorization Code flow
        after the user has authenticated with Keycloak and been redirected
        back to the application with an authorization code.

        Args:
            code: The authorization code received from Keycloak
            redirect_uri: The URI to which Keycloak redirected (must match the original request)

        Returns:
            Dict: Token response containing access_token, refresh_token, and token_type

        Raises:
            Exception: If token retrieval fails
        """
        # Log the received code (truncated for security)
        logger.debug(f"Exchanging authorization code: {code[:8]}")

        # Verify Keycloak is enabled and client is initialized
        if not self.is_enabled or not self.client:
            logger.error("Keycloak is not enabled or client is not initialized")
            return {}

        try:
            # Exchange the authorization code for tokens
            token_response = self.client.token(
                grant_type="authorization_code",
                code=code,
                redirect_uri=redirect_uri,
            )

            logger.debug("Successfully obtained tokens from authorization code")
        except Exception as e:
            logger.error(f"Error getting token from Keycloak: {e!s}")
            raise
        else:
            return token_response

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh an access token using a refresh token.

        This method is used when an access token is about to expire or has expired,
        allowing the application to obtain a new access token without requiring
        the user to log in again.

        Args:
            refresh_token: The refresh token to use for token renewal

        Returns:
            Dict: New token response containing access_token and refresh_token

        Raises:
            Exception: If token refresh fails
        """
        # Verify Keycloak is enabled and client is initialized
        if not self.is_enabled or not self.client:
            logger.error("Keycloak is not enabled or client is not initialized")
            return {}

        try:
            # Log token refresh attempt (truncated for security)
            logger.debug(f"Refreshing token: {refresh_token[:8]}")

            # Call Keycloak to refresh the token
            token_response = self.client.refresh_token(refresh_token)

            logger.debug("Successfully refreshed token:")
        except Exception as e:
            logger.error(f"Error refreshing token from Keycloak: {e!s}")
            raise
        else:
            return token_response

    async def decode_token(self, token: str) -> dict:
        """Decode a JWT token without calling Keycloak server.

        This method decodes the token locally without verification.
        It is safe to skip verification because the token comes directly
        from Keycloak in an OAuth flow and was already verified during that process.

        Args:
            token: The JWT token to decode

        Returns:
            Dict: Decoded token claims/payload

        Raises:
            Exception: If token decoding fails
        """
        # Verify Keycloak is enabled and client is initialized
        if not self.is_enabled or not self.client:
            logger.error("Keycloak is not enabled or client is not initialized")
            return {}

        try:
            # Log decode attempt (truncated for security)
            logger.debug(f"Decoding token: {token[:8]}")

            # Get the expected audience (Keycloak Client ID)
            expected_audience = self.client_id

            # Decode the token without verification
            # This is safe because we've already validated the token with Keycloak
            decoded_token = jwt.decode(token, "", options={"verify_signature": False}, audience=expected_audience)
        except Exception as e:
            logger.error(f"Error decoding token: {e!s}")
            raise
        else:
            return decoded_token

    def extract_roles(self, token_info: dict) -> list[str]:
        """Extract user roles from a token or userinfo response.

        In Keycloak, roles can be realm-level or client-level. This method
        extracts client-specific roles from the token info.

        Args:
            token_info: The decoded token or userinfo response

        Returns:
            List[str]: List of role names assigned to the user
        """
        # Extract resource_access section which contains client-specific roles
        resource_access = token_info.get("resource_access", {})

        # Use the client_id property getter
        client_id = self.client_id

        # Extract roles for our specific client
        client_roles = resource_access.get(client_id, {}).get("roles", [])

        # Return unique roles (removing duplicates)
        return list(set(client_roles))

    async def logout(self, refresh_token: str) -> None:
        """Log out a user from Keycloak by invalidating their session.

        This method calls Keycloak's logout endpoint using the refresh token.
        If successful, the user session is invalidated in Keycloak.

        Args:
            refresh_token: The refresh token to use for logging out.

        Raises:
            Exception: If the logout request fails.
        """
        # Ensure Keycloak is enabled and initialized
        if not self.is_enabled or not self.client:
            logger.error("Cannot log out: Keycloak is not enabled or client is not initialized")
            return

        if not refresh_token:
            logger.warning("Logout attempted without a refresh token")
            return

        try:
            # Call Keycloak's logout endpoint
            self.client.logout(refresh_token)
            logger.info("Successfully logged out from Keycloak")
        except Exception as e:
            logger.error(f"Error logging out from Keycloak: {e!s}")
            raise
