"""Token storage implementation for MCP OAuth 2.1.

This module provides a TokenStorage implementation that satisfies the MCP SDK's
TokenStorage Protocol (mcp.client.auth.TokenStorage).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

    from lfx.base.mcp.oauth.state_manager import OAuthStateManager


class UserScopedTokenStorage:
    """User-scoped token storage using OAuthStateManager for deployed environments.

    This storage implementation uses the OAuthStateManager's cache-based storage
    to persist tokens per user and per server, enabling OAuth flows to work
    in multi-instance deployed environments with shared cache (e.g., Redis).

    This is the recommended storage for deployed environments as it:
    - Supports multi-instance deployments via shared cache
    - Provides per-user token isolation
    - Integrates with the OAuth API flow
    """

    def __init__(self, user_id: str, server_url: str, state_manager: OAuthStateManager) -> None:
        """Initialize user-scoped token storage.

        Args:
            user_id: The ID of the user whose tokens are being managed.
            server_url: The MCP server URL (used to generate storage key).
            state_manager: The OAuthStateManager instance for cache access.
        """
        from lfx.base.mcp.oauth.provider import get_server_key

        self._user_id = user_id
        self._server_key = get_server_key(server_url)
        self._state_manager = state_manager
        self._client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        """Retrieve stored OAuth tokens from the cache.

        Returns:
            The stored OAuthToken if available, None otherwise.
        """
        from mcp.shared.auth import OAuthToken

        tokens_dict = await self._state_manager.get_tokens(self._user_id, self._server_key)
        if tokens_dict:
            return OAuthToken.model_validate(tokens_dict)
        return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store OAuth tokens in the cache.

        Args:
            tokens: The OAuthToken to store.
        """
        await self._state_manager.store_tokens(self._user_id, self._server_key, tokens.model_dump())

    def _client_info_key(self) -> str:
        """Cache key for persisting client registration information."""
        return f"client_info:{self._user_id}:{self._server_key}"

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Retrieve stored client information.

        Checks the in-memory cache first; falls back to the shared cache so
        dynamically-registered client credentials survive across new
        UserScopedTokenStorage instances (e.g. after server restart).

        Returns:
            The stored OAuthClientInformationFull if available, None otherwise.
        """
        if self._client_info is not None:
            return self._client_info

        from mcp.shared.auth import OAuthClientInformationFull

        data = await self._state_manager.get_tokens(self._user_id, self._client_info_key())
        if data:
            self._client_info = OAuthClientInformationFull.model_validate(data)
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client information from dynamic registration.

        Persists to the shared cache so the registration survives new
        UserScopedTokenStorage instances created for subsequent requests.

        Args:
            client_info: The OAuthClientInformationFull to store.
        """
        self._client_info = client_info
        await self._state_manager.store_tokens(
            self._user_id, self._client_info_key(), client_info.model_dump()
        )

    async def clear(self) -> None:
        """Remove all stored tokens and client info for this user and server.

        This is useful when the user wants to re-authenticate or when
        stored credentials are no longer valid.
        """
        await self._state_manager.delete_tokens(self._user_id, self._server_key)
        await self._state_manager.delete_tokens(self._user_id, self._client_info_key())
        self._client_info = None
