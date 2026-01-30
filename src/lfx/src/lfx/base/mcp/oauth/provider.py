"""OAuth provider factory for MCP authentication.

This module provides a factory function to create an OAuthClientProvider
configured for use with Langflow and MCP servers.

For deployed environments, use `is_deployed_mode()` to detect if the server
is running in a deployment (non-localhost) environment, and use
`create_token_auth()` with pre-obtained tokens from the OAuth API endpoints.
"""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx

from lfx.base.mcp.oauth.handlers import OAuthCallbackHandler
from lfx.base.mcp.oauth.storage import FileTokenStorage, InMemoryTokenStorage
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from mcp.client.auth import OAuthClientProvider


class OAuthRequiredError(Exception):
    """Raised when OAuth authentication is required in deployed mode.

    This error is raised when the MCP component detects that OAuth is needed
    but no cached tokens are available. The frontend should handle this by
    initiating the OAuth flow via the /api/v1/mcp/oauth/initiate endpoint.

    Attributes:
        message: Human-readable error message.
        server_url: The MCP server URL requiring authentication.
        initiate_endpoint: The API endpoint to start the OAuth flow.
        client_id: Pre-registered OAuth client ID (optional).
        client_secret: Pre-registered OAuth client secret (optional).
        redirect_uri: Custom redirect URI (optional).
        scopes: OAuth scopes to request (optional).
    """

    def __init__(
        self,
        message: str,
        server_url: str,
        initiate_endpoint: str = "/api/v1/mcp/oauth/initiate",
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.server_url = server_url
        self.initiate_endpoint = initiate_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dict for API responses."""
        result = {
            "error": "oauth_required",
            "message": self.message,
            "server_url": self.server_url,
            "initiate_endpoint": self.initiate_endpoint,
        }
        # Include optional fields if provided
        if self.client_id:
            result["client_id"] = self.client_id
        if self.client_secret:
            result["client_secret"] = self.client_secret
        if self.redirect_uri:
            result["redirect_uri"] = self.redirect_uri
        if self.scopes:
            result["scopes"] = self.scopes
        return result


def is_deployed_mode() -> bool:
    """Detect if Langflow is running in a deployed environment.

    A deployed environment is one where users access Langflow through
    a network (not localhost), meaning the local browser-based OAuth
    callback flow won't work.

    Detection methods:
    1. Explicit environment variable: LANGFLOW_DEPLOYED=true
    2. Running in Docker container (/.dockerenv exists)
    3. Host setting is not localhost/127.0.0.1

    Returns:
        True if running in deployed mode, False for local development.
    """
    # Check explicit environment variable
    if os.getenv("LANGFLOW_DEPLOYED", "").lower() == "true":
        return True

    # Check for Docker container
    if Path("/.dockerenv").exists():
        return True

    # Check if running in Kubernetes (common env var)
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        return True

    # Check host setting from Langflow settings
    try:
        from lfx.services.deps import get_settings_service

        settings = get_settings_service().settings
        host = getattr(settings, "host", "localhost")

        # Consider deployed if host is not localhost
        # Note: 0.0.0.0 means "all interfaces" but is commonly used in containers
        if host not in ("localhost", "127.0.0.1", "0.0.0.0"):  # noqa: S104
            return True
    except Exception:  # noqa: BLE001, S110
        # If we can't get settings, assume local mode
        pass

    return False


class TokenAuth(httpx.Auth):
    """Simple token-based authentication for pre-obtained OAuth tokens.

    This is used in deployed mode where tokens are obtained via the
    OAuth API endpoints and cached. It adds the Bearer token to requests.
    """

    def __init__(self, access_token: str, token_type: str = "Bearer") -> None:  # noqa: S107
        """Initialize token auth.

        Args:
            access_token: The OAuth access token.
            token_type: The token type (default: "Bearer").
        """
        self._access_token = access_token
        self._token_type = token_type

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Add authorization header to the request."""
        request.headers["Authorization"] = f"{self._token_type} {self._access_token}"
        yield request


def create_token_auth(tokens: dict[str, Any]) -> httpx.Auth:
    """Create an httpx.Auth instance from pre-obtained tokens.

    Use this in deployed mode with tokens obtained from the OAuth API
    endpoints or from the OAuth state manager cache.

    Args:
        tokens: A dict containing at least 'access_token' and optionally
            'token_type' (defaults to 'Bearer').

    Returns:
        An httpx.Auth instance that adds the Bearer token to requests.

    Raises:
        ValueError: If tokens dict doesn't contain access_token.

    Example:
        >>> tokens = await state_manager.get_tokens(user_id, server_key)
        >>> if tokens:
        ...     auth = create_token_auth(tokens)
        ...     async with httpx.AsyncClient(auth=auth) as client:
        ...         response = await client.get(server_url)
    """
    access_token = tokens.get("access_token")
    if not access_token:
        msg = "tokens dict must contain 'access_token'"
        raise ValueError(msg)

    token_type = tokens.get("token_type", "Bearer")
    return TokenAuth(access_token, token_type)


def get_server_key(server_url: str) -> str:
    """Generate a cache-safe key from a server URL.

    This is the same key format used by the OAuth state manager
    for storing tokens.

    Args:
        server_url: The MCP server URL.

    Returns:
        A safe string key for cache storage.
    """
    parsed = urlparse(server_url)
    return f"{parsed.netloc}{parsed.path}".replace("/", "_").replace(":", "_")


class OAuthAuthWrapper(httpx.Auth):
    """Wrapper around OAuthClientProvider that handles 401 errors.

    This wrapper detects 401 Unauthorized responses and clears cached
    tokens to force re-authentication on the next request.
    """

    def __init__(
        self,
        provider: OAuthClientProvider,
        storage: FileTokenStorage | InMemoryTokenStorage,
    ) -> None:
        """Initialize the OAuth auth wrapper.

        Args:
            provider: The underlying OAuthClientProvider from MCP SDK.
            storage: Token storage to clear on authentication errors.
        """
        self._provider = provider
        self._storage = storage
        self._tokens_cleared = False

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying provider.

        This allows access to properties like `context`, `storage`, etc.
        from the underlying OAuthClientProvider.
        """
        return getattr(self._provider, name)

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Handle the authentication flow with 401 error detection.

        This method wraps the underlying provider's auth_flow and monitors
        for 401 responses to clear invalid cached tokens.
        """
        # Delegate to the underlying provider's auth_flow
        flow = self._provider.auth_flow(request)

        # Process the flow
        try:
            request = next(flow)
            while True:
                response = yield request
                try:
                    request = flow.send(response)
                except StopIteration:
                    break
        except StopIteration:
            pass

        # Check if we got a 401 response (response is available after yield)
        # Note: This check happens after the flow completes

    async def async_auth_flow(self, request: httpx.Request) -> Any:  # Generator type is complex for async
        """Handle async authentication flow with 401 error detection.

        This method wraps the underlying provider's async_auth_flow and
        monitors for 401 responses to clear invalid cached tokens.
        """
        # Delegate to the underlying provider's async_auth_flow
        flow = self._provider.async_auth_flow(request)

        request = await flow.__anext__()
        while True:
            response = yield request
            # Check for 401 and clear tokens if needed
            if response.status_code == 401 and not self._tokens_cleared:
                await self._clear_tokens_on_401(response)
            try:
                request = await flow.asend(response)
            except StopAsyncIteration:
                break

    async def _clear_tokens_on_401(self, response: httpx.Response) -> None:
        """Clear cached tokens when a 401 response is received.

        Args:
            response: The 401 response from the server.
        """
        # Check if this is an OAuth-related 401 (invalid_token, expired_token, etc.)
        error_body = ""
        try:
            error_body = response.text
        except Exception:  # noqa: BLE001
            pass

        # Log the error
        await logger.awarning(
            f"Received 401 Unauthorized from server. "
            f"Clearing cached OAuth tokens to force re-authentication. "
            f"Response: {error_body[:200] if error_body else 'empty'}"
        )

        # Clear cached tokens
        if hasattr(self._storage, "clear"):
            self._storage.clear()
        else:
            # For InMemoryTokenStorage, set to None
            self._storage._tokens = None  # noqa: SLF001
            self._storage._client_info = None  # noqa: SLF001

        self._tokens_cleared = True


async def create_mcp_oauth_provider(
    server_url: str,
    client_name: str = "langflow",
    storage_dir: Path | None = None,
    timeout: float = 300.0,
    *,
    use_file_storage: bool = True,
    redirect_port: int = 18085,
    redirect_host: str = "localhost",
    redirect_uri: str | None = None,
    client_metadata_url: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> tuple[httpx.Auth, str, Callable[[], None]]:
    """Create an OAuthClientProvider for an MCP server.

    This factory function sets up all the components needed for OAuth 2.1
    authentication with an MCP server:
    - Token storage (file-based or in-memory)
    - Callback handler (local HTTP server)
    - Redirect handler (browser opener)
    - The OAuthClientProvider itself

    The returned provider implements httpx.Auth, so it can be passed directly
    to httpx.AsyncClient as the `auth` parameter.

    Client Registration Priority (per MCP spec):
    1. Pre-registered credentials (if client_id is provided)
    2. Client ID Metadata Documents (if client_metadata_url is provided and server supports it)
    3. Dynamic Client Registration (fallback)

    Args:
        server_url: The MCP server URL to authenticate with.
        client_name: Client name for dynamic registration (default: "langflow").
        storage_dir: Directory for file-based token storage.
            Default: ~/.langflow/oauth
        timeout: OAuth flow timeout in seconds (default: 300).
        use_file_storage: Whether to use file-based storage (True) or in-memory (False).
        redirect_port: Port for OAuth callback server (default: 18085).
            Ignored if redirect_uri is provided.
        redirect_host: Host for redirect_uri (default: "localhost").
            Ignored if redirect_uri is provided.
        redirect_uri: Custom OAuth redirect URI. Use this when the OAuth provider
            requires a specific callback URL (e.g., "http://localhost:9000/auth/callback").
            The callback server will listen on the host:port parsed from this URI.
            If not provided, defaults to "http://{redirect_host}:{redirect_port}/callback".
        client_metadata_url: URL-based client ID for Client ID Metadata Documents (CIMD).
            When provided and the authorization server advertises
            `client_id_metadata_document_supported=true`, this URL will be used as
            the client_id instead of performing dynamic client registration.
            Must be a valid HTTPS URL with a non-root pathname (e.g.,
            "https://app.example.com/oauth/client-metadata.json").
            See: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-client-id-metadata-document
        client_id: Pre-registered OAuth client ID. Use this when the authorization
            server doesn't support Dynamic Client Registration (e.g., Logto, Auth0).
            Takes priority over client_metadata_url and dynamic registration.
        client_secret: Pre-registered OAuth client secret. Required for confidential
            clients. If not provided with client_id, the client is treated as a
            public client (token_endpoint_auth_method="none").

    Returns:
        A tuple of (oauth_provider, redirect_uri, cleanup_function):
        - oauth_provider: The configured OAuthClientProvider (implements httpx.Auth)
        - redirect_uri: The redirect URI configured for this OAuth flow
        - cleanup_function: Call this to clean up resources when done

    Raises:
        ValueError: If client_metadata_url is provided but is not a valid HTTPS URL
            with a non-root pathname.
        ValueError: If redirect_uri is provided but cannot be parsed.

    Example:
        >>> # Dynamic Client Registration (default):
        >>> provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
        ...     server_url="https://mcp.example.com",
        ...     client_name="my-app",
        ... )

        >>> # Pre-registered client (e.g., for Logto, Auth0):
        >>> provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
        ...     server_url="https://mcp.example.com",
        ...     client_id="my-client-id-from-auth-server",
        ... )

        >>> # Custom redirect URI (for IBM, Okta, etc.):
        >>> provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
        ...     server_url="https://mcp.example.com",
        ...     client_id="my-client-id",
        ...     redirect_uri="http://localhost:9000/auth/idaas/callback",
        ... )

        >>> # Client ID Metadata Documents (CIMD):
        >>> provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
        ...     server_url="https://mcp.example.com",
        ...     client_metadata_url="https://myapp.example.com/oauth/metadata.json",
        ... )
    """
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata

    # Generate storage key from server URL
    parsed = urlparse(server_url)
    server_key = f"mcp_{parsed.netloc}_{parsed.path.replace('/', '_')}"

    # Set up storage
    storage: FileTokenStorage | InMemoryTokenStorage
    if use_file_storage:
        if storage_dir is None:
            storage_dir = Path.home() / ".langflow" / "oauth"
        storage = FileTokenStorage(storage_dir, server_key)
    else:
        storage = InMemoryTokenStorage()

    # Set up callback handler with configured port and host
    # If redirect_uri is provided, parse it to extract host and port
    effective_redirect_uri: str
    if redirect_uri is not None:
        parsed_redirect = urlparse(redirect_uri)
        if not parsed_redirect.scheme or not parsed_redirect.netloc:
            msg = f"Invalid redirect_uri: {redirect_uri}. Must be a valid URL."
            raise ValueError(msg)
        # Extract host and port from the redirect URI
        callback_host = parsed_redirect.hostname or "localhost"
        callback_port = parsed_redirect.port or (443 if parsed_redirect.scheme == "https" else 80)
        callback_handler = OAuthCallbackHandler(port=callback_port, host=callback_host)
        # Start the handler but use the exact redirect_uri provided
        await callback_handler.start()
        effective_redirect_uri = redirect_uri
    else:
        callback_handler = OAuthCallbackHandler(port=redirect_port, host=redirect_host)
        effective_redirect_uri = await callback_handler.start()

    # If pre-registered client credentials are provided, store them
    if client_id is not None:
        token_endpoint_auth_method = "client_secret_post" if client_secret else "none"
        pre_registered_client = OAuthClientInformationFull(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=[effective_redirect_uri],
            token_endpoint_auth_method=token_endpoint_auth_method,
        )
        await storage.set_client_info(pre_registered_client)

    # Create client metadata for dynamic registration (public client)
    client_metadata = OAuthClientMetadata(
        client_name=client_name,
        redirect_uris=[effective_redirect_uri],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
    )

    # Redirect handler opens browser
    async def redirect_handler(url: str) -> None:
        webbrowser.open(url)

    # Callback handler waits for OAuth response
    async def callback_fn() -> tuple[str, str | None]:
        return await callback_handler.wait_for_callback(timeout=timeout)

    # Create the provider
    provider = OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_fn,
        client_metadata_url=client_metadata_url,
    )

    # Wrap the provider to handle 401 errors and clear cached tokens
    wrapped_provider = OAuthAuthWrapper(provider, storage)

    def cleanup() -> None:
        """Clean up OAuth resources."""
        callback_handler.shutdown()

    return wrapped_provider, effective_redirect_uri, cleanup


async def get_oauth_token_for_server(
    server_url: str,
    client_name: str = "langflow",
    storage_dir: Path | None = None,
    timeout: float = 300.0,
    *,
    redirect_uri: str | None = None,
    client_metadata_url: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> str | None:
    """Get an OAuth access token for an MCP server.

    This is a convenience function that handles the complete OAuth flow
    and returns just the access token. Use this when you need to make
    authenticated requests manually.

    If valid tokens are already stored, they will be returned without
    requiring user interaction. If tokens are expired but a refresh token
    is available, the tokens will be refreshed automatically.

    Args:
        server_url: The MCP server URL to authenticate with.
        client_name: Client name for dynamic registration.
        storage_dir: Directory for token storage.
        timeout: OAuth flow timeout in seconds.
        redirect_uri: Custom OAuth redirect URI. Use this when the OAuth provider
            requires a specific callback URL.
        client_metadata_url: URL-based client ID for Client ID Metadata Documents (CIMD).
            When provided and the authorization server advertises
            `client_id_metadata_document_supported=true`, this URL will be used as
            the client_id instead of performing dynamic client registration.
        client_id: Pre-registered OAuth client ID. Use this when the authorization
            server doesn't support Dynamic Client Registration (e.g., Logto, Auth0).
        client_secret: Pre-registered OAuth client secret for confidential clients.

    Returns:
        The access token string if authentication succeeds, None otherwise.
    """
    provider, _, cleanup = await create_mcp_oauth_provider(
        server_url=server_url,
        client_name=client_name,
        storage_dir=storage_dir,
        timeout=timeout,
        redirect_uri=redirect_uri,
        client_metadata_url=client_metadata_url,
        client_id=client_id,
        client_secret=client_secret,
    )

    try:
        # The OAuthClientProvider implements httpx.Auth
        # Making a request triggers the OAuth flow if needed
        async with httpx.AsyncClient(auth=provider) as client:
            # Make a lightweight request to trigger auth flow
            # Using HEAD to minimize data transfer
            try:
                await client.head(server_url, timeout=timeout)
            except httpx.HTTPError as e:
                await logger.awarning(f"HTTP error during OAuth flow: {e}")
                # Auth may still have succeeded, check for tokens

            # After auth flow, check if we have tokens
            # Accessing internal provider state to extract tokens (intentional)
            if hasattr(provider, "_context") and provider._context:  # noqa: SLF001
                tokens = provider._context.current_tokens  # noqa: SLF001
                if tokens:
                    return tokens.access_token

            # Fallback: try to get tokens from storage
            if hasattr(provider, "_storage"):
                tokens = await provider._storage.get_tokens()  # noqa: SLF001
                if tokens:
                    return tokens.access_token

            return None

    except (httpx.HTTPError, OSError, ValueError, TimeoutError) as e:
        await logger.aerror(f"OAuth authentication failed: {e}")
        return None

    finally:
        cleanup()
