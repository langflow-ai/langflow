"""OAuth provider factory for MCP authentication.

This module provides a unified OAuth flow using the MCP SDK's OAuthClientProvider
for all environments (local and deployed). All OAuth flows go through backend
API endpoints for consistent behavior and automatic token refresh.
"""

from __future__ import annotations

import contextlib
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

import httpx

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from mcp.client.auth import OAuthClientProvider

    from lfx.base.mcp.oauth.storage import UserScopedTokenStorage


class OAuthRequiredError(Exception):
    """Raised when OAuth authentication is required.

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
        storage: UserScopedTokenStorage,
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

    def auth_flow(self, request: httpx.Request):
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

    async def async_auth_flow(self, request: httpx.Request):
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
            if response.status_code == HTTPStatus.UNAUTHORIZED and not self._tokens_cleared:
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
        with contextlib.suppress(Exception):
            error_body = response.text

        # Log the error
        await logger.awarning(
            f"Received 401 Unauthorized from server. "
            f"Clearing cached OAuth tokens to force re-authentication. "
            f"Response: {error_body[:200] if error_body else 'empty'}"
        )

        # Clear cached tokens
        await self._storage.clear()
        self._tokens_cleared = True


async def create_deployed_oauth_provider(
    server_url: str,
    user_id: str,
    redirect_uri: str,
    client_id: str | None = None,
    client_secret: str | None = None,
    scopes: list[str] | None = None,
    timeout: float = 300.0,
    flow_id: str | None = None,
) -> tuple[httpx.Auth, str, Callable[[], None]]:
    """Create OAuthClientProvider for deployed environments.

    This factory function sets up the MCP SDK's OAuthClientProvider configured
    for deployed environments where OAuth callbacks go through the backend API.

    The provider will:
    - Use UserScopedTokenStorage for per-user token persistence
    - Automatically refresh tokens when they expire
    - Raise OAuthFlowStarted when user interaction is needed
    - Wait for callback via the state manager

    Args:
        server_url: The MCP server URL to authenticate with.
        user_id: The ID of the user initiating the OAuth flow.
        redirect_uri: The OAuth callback URI (should point to /api/v1/mcp/oauth/callback).
        client_id: Pre-registered OAuth client ID (optional, uses dynamic registration if not provided).
        client_secret: Pre-registered OAuth client secret (optional).
        scopes: OAuth scopes to request (optional).
        timeout: OAuth flow timeout in seconds (default: 300).
        flow_id: Pre-created flow ID from state manager (optional).

    Returns:
        A tuple of (oauth_provider, flow_id, cleanup_function):
        - oauth_provider: The configured OAuthClientProvider (implements httpx.Auth)
        - flow_id: The flow ID for tracking the OAuth flow
        - cleanup_function: Call this to clean up resources when done (no-op for deployed mode)

    Raises:
        OAuthFlowStarted: When the user needs to authorize (contains auth URL and flow ID).

    Example:
        >>> try:
        ...     provider, flow_id, cleanup = await create_deployed_oauth_provider(
        ...         server_url="https://mcp.example.com",
        ...         user_id="user-123",
        ...         redirect_uri="https://app.example.com/api/v1/mcp/oauth/callback",
        ...     )
        ...     # Provider has valid tokens, use it
        ...     async with httpx.AsyncClient(auth=provider) as client:
        ...         response = await client.get(server_url)
        ... except OAuthFlowStarted as e:
        ...     # Return auth URL to frontend
        ...     return {"auth_url": e.authorization_url, "flow_id": e.flow_id}
    """
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata

    from lfx.base.mcp.oauth.state_manager import get_oauth_state_manager
    from lfx.base.mcp.oauth.storage import UserScopedTokenStorage

    state_manager = await get_oauth_state_manager()

    # Create flow for tracking if not provided
    if not flow_id:
        flow_config = {"client_id": client_id, "client_secret": client_secret}
        flow_id, _state_param = await state_manager.create_flow(user_id, server_url, flow_config)

    # User-scoped storage using the state manager's cache
    storage = UserScopedTokenStorage(user_id, server_url, state_manager)

    # Pre-register client if provided
    if client_id:
        token_endpoint_auth_method = "client_secret_post" if client_secret else "none"
        client_info = OAuthClientInformationFull(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=[redirect_uri],
            token_endpoint_auth_method=token_endpoint_auth_method,
        )
        await storage.set_client_info(client_info)

    # Capture flow_id in closure for redirect_handler
    captured_flow_id = flow_id

    # Redirect handler stores auth URL and waits for callback (doesn't raise)
    # This allows the SDK to complete the full OAuth flow including token exchange
    async def redirect_handler(url: str) -> None:
        # Extract the SDK's state parameter from the authorization URL
        # and store a mapping so the callback can find our flow
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        sdk_state = query_params.get("state", [None])[0]

        if sdk_state:
            # Store mapping from SDK's state -> our flow_id
            await state_manager._cache_set(  # noqa: SLF001
                state_manager._state_key(sdk_state),  # noqa: SLF001
                captured_flow_id,
            )
            await logger.ainfo(f"Stored SDK state mapping for flow {captured_flow_id}: {sdk_state[:20]}...")

        # Store the auth URL in the flow data so /status can return it
        flow_data = await state_manager.get_flow_by_id(captured_flow_id)
        if flow_data:
            flow_data["auth_url"] = url
            flow_data["status"] = "awaiting_callback"
            await state_manager._cache_set(  # noqa: SLF001
                state_manager._flow_key(captured_flow_id),  # noqa: SLF001
                flow_data,
            )
            await logger.ainfo(f"Stored auth URL for flow {captured_flow_id}, waiting for callback...")

        # Don't raise - let the SDK continue to call callback_handler
        # The callback_handler will wait for the callback to be received

    # Callback handler waits for callback via state manager
    async def callback_handler() -> tuple[str, str | None]:
        return await state_manager.get_callback(captured_flow_id, timeout)

    # Create client metadata for dynamic registration
    client_metadata = OAuthClientMetadata(
        client_name="langflow",
        redirect_uris=[redirect_uri],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",  # noqa: S106
        scope=" ".join(scopes) if scopes else None,
    )

    # Create the SDK provider
    provider = OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )

    # Wrap the provider to handle 401 errors
    wrapped_provider = OAuthAuthWrapper(provider, storage)

    # No-op cleanup for deployed mode (no local resources to clean up)
    def cleanup() -> None:
        pass

    return wrapped_provider, flow_id, cleanup
