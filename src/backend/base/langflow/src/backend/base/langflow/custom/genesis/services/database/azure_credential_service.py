"""Azure credential management service for database authentication."""

import time
from typing import Dict, Optional

from azure.core.exceptions import ClientAuthenticationError
from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from langflow.services.base import Service
from loguru import logger

from .settings import DatabaseSettings

# Constants
DEFAULT_TOKEN_REFRESH_BUFFER = 300  # 5 minutes buffer


class TokenCache:
    """Thread-safe token cache with expiration."""

    def __init__(self, refresh_buffer: int = DEFAULT_TOKEN_REFRESH_BUFFER):
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._refresh_buffer = refresh_buffer

    def is_valid(self) -> bool:
        """Check if cached token is still valid."""
        return self._token is not None and time.time() < (
            self._expires_at - self._refresh_buffer
        )

    def get_token(self) -> Optional[str]:
        """Get cached token if valid."""
        return self._token if self.is_valid() else None

    def set_token(self, token: str, expires_in: int) -> None:
        """Cache token with expiration time."""
        self._token = token
        self._expires_at = time.time() + expires_in
        logger.debug(f"Token cached, expires in {expires_in}s")

    def clear(self) -> None:
        """Clear cached token."""
        self._token = None
        self._expires_at = 0


class AzureCredentialService(Service):
    """Service for managing Azure credentials and tokens."""

    name = "azure_credential_service"

    def __init__(self, settings: Optional[DatabaseSettings] = None):
        super().__init__()
        self.settings = settings or DatabaseSettings()
        self._token_cache = TokenCache(self.settings.TOKEN_REFRESH_BUFFER)
        self._credential: Optional[DefaultAzureCredential] = None
        self._async_credential: Optional[AsyncDefaultAzureCredential] = None
        self._postgres_scope = "https://ossrdbms-aad.database.windows.net/.default"

    @property
    def credential(self) -> DefaultAzureCredential:
        """Get synchronous Azure credential."""
        if self._credential is None:
            credential_options = self._get_credential_options()
            self._credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True, **credential_options
            )
            logger.debug("Synchronous Azure credential initialized")
        return self._credential

    @property
    def async_credential(self) -> AsyncDefaultAzureCredential:
        """Get asynchronous Azure credential."""
        if self._async_credential is None:
            credential_options = self._get_credential_options()
            self._async_credential = AsyncDefaultAzureCredential(
                exclude_interactive_browser_credential=True, **credential_options
            )
            logger.debug("Asynchronous Azure credential initialized")
        return self._async_credential

    def _get_credential_options(self) -> Dict[str, str]:
        """Get credential options based on configuration."""
        options = {}
        if self.settings.AZURE_CLIENT_ID:
            options["managed_identity_client_id"] = self.settings.AZURE_CLIENT_ID
            logger.debug(
                f"Using user-assigned managed identity: {self.settings.AZURE_CLIENT_ID}"
            )
        else:
            logger.debug("Using system-assigned managed identity")
        return options

    def _handle_token_response(self, token_response) -> str:
        """Handle token response and caching logic."""
        expires_in = int(token_response.expires_on - time.time())
        self._token_cache.set_token(token_response.token, expires_in)
        logger.debug("Successfully obtained PostgreSQL access token")
        return token_response.token

    def _handle_authentication_error(
        self, error: Exception, is_async: bool = False
    ) -> None:
        """Handle authentication errors with proper logging and cache clearing."""
        async_suffix = " (async)" if is_async else ""

        if isinstance(error, ClientAuthenticationError):
            logger.error(f"Azure authentication failed{async_suffix}: {error}")
        else:
            logger.error(
                f"Unexpected error getting access token{async_suffix}: {error}"
            )

        self._token_cache.clear()

    def get_token_sync(self) -> str:
        """Get access token synchronously with caching."""
        # Check cache first
        cached_token = self._token_cache.get_token()
        if cached_token:
            logger.debug("Using cached PostgreSQL access token")
            return cached_token

        try:
            logger.debug("Requesting new PostgreSQL access token")
            token_response = self.credential.get_token(self._postgres_scope)
            return self._handle_token_response(token_response)

        except ClientAuthenticationError as e:
            self._handle_authentication_error(e)
            raise
        except Exception as e:
            self._handle_authentication_error(e)
            raise ClientAuthenticationError(f"Token acquisition failed: {e}")

    async def get_token_async(self) -> str:
        """Get access token asynchronously with caching."""
        # Check cache first
        cached_token = self._token_cache.get_token()
        if cached_token:
            logger.debug("Using cached PostgreSQL access token")
            return cached_token

        try:
            logger.debug("Requesting new PostgreSQL access token (async)")
            token_response = await self.async_credential.get_token(self._postgres_scope)
            return self._handle_token_response(token_response)

        except ClientAuthenticationError as e:
            self._handle_authentication_error(e, is_async=True)
            raise
        except Exception as e:
            self._handle_authentication_error(e, is_async=True)
            raise ClientAuthenticationError(f"Token acquisition failed: {e}")

    async def test_authentication(self) -> bool:
        """Test if Azure authentication is working."""
        try:
            await self.get_token_async()
            return True
        except Exception as e:
            logger.warning(f"Azure authentication test failed: {e}")
            return False

    def clear_cache(self) -> None:
        """Clear token cache."""
        self._token_cache.clear()
        logger.debug("Token cache cleared")

    async def cleanup(self) -> None:
        """Clean up resources."""
        self.clear_cache()
        if self._async_credential:
            await self._async_credential.close()
            self._async_credential = None
            logger.debug("Azure credential service cleaned up")
