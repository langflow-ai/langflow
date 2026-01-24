"""OAuth provider factory for MCP authentication.

This module provides a factory function to create an OAuthClientProvider
configured for use with Langflow and MCP servers.
"""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from lfx.base.mcp.oauth.handlers import OAuthCallbackHandler
from lfx.base.mcp.oauth.storage import FileTokenStorage, InMemoryTokenStorage

if TYPE_CHECKING:
    from collections.abc import Callable

    from mcp.client.auth import OAuthClientProvider


async def create_mcp_oauth_provider(
    server_url: str,
    client_name: str = "langflow",
    storage_dir: Path | None = None,
    timeout: float = 300.0,
    *,
    use_file_storage: bool = True,
    redirect_port: int = 18085,
    redirect_host: str = "localhost",
    client_metadata_url: str | None = None,
) -> tuple[OAuthClientProvider, str, Callable[[], None]]:
    """Create an OAuthClientProvider for an MCP server.

    This factory function sets up all the components needed for OAuth 2.1
    authentication with an MCP server:
    - Token storage (file-based or in-memory)
    - Callback handler (local HTTP server)
    - Redirect handler (browser opener)
    - The OAuthClientProvider itself

    The returned provider implements httpx.Auth, so it can be passed directly
    to httpx.AsyncClient as the `auth` parameter.

    Args:
        server_url: The MCP server URL to authenticate with.
        client_name: Client name for dynamic registration (default: "langflow").
        storage_dir: Directory for file-based token storage.
            Default: ~/.langflow/oauth
        timeout: OAuth flow timeout in seconds (default: 300).
        use_file_storage: Whether to use file-based storage (True) or in-memory (False).
        redirect_port: Port for OAuth callback server (default: 18085).
        redirect_host: Host for redirect_uri (default: "localhost").
        client_metadata_url: URL-based client ID for Client ID Metadata Documents (CIMD).
            When provided and the authorization server advertises
            `client_id_metadata_document_supported=true`, this URL will be used as
            the client_id instead of performing dynamic client registration.
            Must be a valid HTTPS URL with a non-root pathname (e.g.,
            "https://app.example.com/oauth/client-metadata.json").
            See: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-client-id-metadata-document

    Returns:
        A tuple of (oauth_provider, redirect_uri, cleanup_function):
        - oauth_provider: The configured OAuthClientProvider (implements httpx.Auth)
        - redirect_uri: The redirect URI configured for this OAuth flow
        - cleanup_function: Call this to clean up resources when done

    Raises:
        ValueError: If client_metadata_url is provided but is not a valid HTTPS URL
            with a non-root pathname.

    Example:
        >>> provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
        ...     server_url="https://mcp.example.com",
        ...     client_name="my-app",
        ... )
        >>> try:
        ...     async with httpx.AsyncClient(auth=provider) as client:
        ...         response = await client.get(server_url)
        ... finally:
        ...     cleanup()

        # Using Client ID Metadata Documents (CIMD):
        >>> provider, redirect_uri, cleanup = await create_mcp_oauth_provider(
        ...     server_url="https://mcp.example.com",
        ...     client_metadata_url="https://myapp.example.com/oauth/metadata.json",
        ... )
    """
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata

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
    callback_handler = OAuthCallbackHandler(port=redirect_port, host=redirect_host)
    redirect_uri = await callback_handler.start()

    # Create client metadata for dynamic registration
    # Using "none" auth method for public clients (no client secret)
    public_client_auth_method = "none"
    client_metadata = OAuthClientMetadata(
        client_name=client_name,
        redirect_uris=[redirect_uri],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method=public_client_auth_method,
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

    def cleanup() -> None:
        """Clean up OAuth resources."""
        callback_handler.shutdown()

    return provider, redirect_uri, cleanup


async def get_oauth_token_for_server(
    server_url: str,
    client_name: str = "langflow",
    storage_dir: Path | None = None,
    timeout: float = 300.0,
    *,
    client_metadata_url: str | None = None,
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
        client_metadata_url: URL-based client ID for Client ID Metadata Documents (CIMD).
            When provided and the authorization server advertises
            `client_id_metadata_document_supported=true`, this URL will be used as
            the client_id instead of performing dynamic client registration.

    Returns:
        The access token string if authentication succeeds, None otherwise.
    """
    import httpx

    from lfx.log.logger import logger

    provider, _, cleanup = await create_mcp_oauth_provider(
        server_url=server_url,
        client_name=client_name,
        storage_dir=storage_dir,
        timeout=timeout,
        client_metadata_url=client_metadata_url,
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
