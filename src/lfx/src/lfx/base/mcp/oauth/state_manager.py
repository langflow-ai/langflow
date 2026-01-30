"""OAuth state manager for MCP deployment-ready authentication.

This module provides a state manager that stores OAuth flow state using
the CacheService, enabling OAuth flows to work in multi-instance deployments.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID, uuid4

from lfx.base.mcp.oauth.provider import get_server_key
from lfx.log.logger import logger

if TYPE_CHECKING:
    from langflow.services.cache.base import AsyncBaseCacheService, CacheService


class OAuthStateManager:
    """Manages OAuth flow state using CacheService.

    This enables OAuth flows to work across multiple server instances by storing
    state in a shared cache (Redis in production, in-memory for single instances).

    The flow works as follows:
    1. create_flow() - Frontend initiates OAuth, returns flow_id + auth_url
    2. get_flow() - Callback endpoint looks up flow by state parameter
    3. complete_flow() - Exchange code for tokens, store result
    4. get_flow_status() - Frontend polls for completion

    Cache key structure:
    - mcp_oauth:flow:{flow_id} - Flow metadata (user_id, server_url, state, config)
    - mcp_oauth:state:{state} - Maps state param to flow_id (for callback lookup)
    - mcp_oauth:tokens:{user_id}:{server_key} - Stored tokens for reuse
    """

    PREFIX = "mcp_oauth:"

    def __init__(self, cache_service: CacheService | AsyncBaseCacheService) -> None:
        """Initialize the OAuth state manager.

        Args:
            cache_service: The cache service to use for state storage.
                Supports both sync and async cache services.
        """
        self._cache = cache_service

    def _flow_key(self, flow_id: str) -> str:
        """Get cache key for flow data."""
        return f"{self.PREFIX}flow:{flow_id}"

    def _state_key(self, state: str) -> str:
        """Get cache key for state-to-flow mapping."""
        return f"{self.PREFIX}state:{state}"

    def _tokens_key(self, user_id: str | UUID, server_key: str) -> str:
        """Get cache key for stored tokens."""
        return f"{self.PREFIX}tokens:{user_id}:{server_key}"

    async def create_flow(
        self,
        user_id: str | UUID,
        server_url: str,
        config: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """Create a new OAuth flow.

        Args:
            user_id: The ID of the user initiating the OAuth flow.
            server_url: The MCP server URL requiring authentication.
            config: Optional OAuth configuration (client_id, client_secret, scopes).

        Returns:
            A tuple of (flow_id, state_param) where:
            - flow_id: Unique ID for the frontend to poll status
            - state_param: OAuth state parameter to include in auth URL
        """
        flow_id = str(uuid4())
        state_param = f"{flow_id}:{secrets.token_urlsafe(32)}"

        flow_data = {
            "flow_id": flow_id,
            "user_id": str(user_id),
            "server_url": server_url,
            "config": config or {},
            "status": "pending",
            "error_message": None,
            "tokens": None,
        }

        # Store flow data
        await self._cache_set(self._flow_key(flow_id), flow_data)
        # Store state-to-flow mapping for callback lookup
        await self._cache_set(self._state_key(state_param), flow_id)

        await logger.ainfo(f"Created OAuth flow {flow_id} for user {user_id}")
        return flow_id, state_param

    async def get_flow(self, state_param: str) -> dict[str, Any] | None:
        """Get flow data by OAuth state parameter.

        This is used by the callback endpoint to look up the flow when
        the OAuth provider redirects back with the state parameter.

        Args:
            state_param: The OAuth state parameter from the callback.

        Returns:
            The flow data dict if found and valid, None otherwise.
        """
        # Look up flow_id from state
        flow_id = await self._cache_get(self._state_key(state_param))
        if not flow_id:
            await logger.awarning(f"OAuth flow not found for state: {state_param[:20]}...")
            return None

        # Get flow data
        flow_data = await self._cache_get(self._flow_key(flow_id))
        if not flow_data:
            await logger.awarning(f"OAuth flow data not found for flow_id: {flow_id}")
            return None

        return flow_data

    async def complete_flow(
        self,
        state_param: str,
        tokens: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Mark a flow as complete with tokens.

        Called by the callback endpoint after successfully exchanging
        the authorization code for tokens.

        Args:
            state_param: The OAuth state parameter from the callback.
            tokens: The tokens obtained from the token exchange.

        Returns:
            The updated flow data, or None if flow not found.
        """
        flow_data = await self.get_flow(state_param)
        if not flow_data:
            return None

        flow_id = flow_data["flow_id"]
        user_id = flow_data["user_id"]
        server_url = flow_data["server_url"]

        # Update flow status
        flow_data["status"] = "complete"
        flow_data["tokens"] = tokens
        await self._cache_set(self._flow_key(flow_id), flow_data)

        # Also store tokens for future use
        server_key = get_server_key(server_url)
        await self.store_tokens(user_id, server_key, tokens)

        # Clean up state mapping (one-time use)
        await self._cache_delete(self._state_key(state_param))

        await logger.ainfo(f"Completed OAuth flow {flow_id} for user {user_id}")
        return flow_data

    async def fail_flow(
        self,
        state_param: str,
        error_message: str,
    ) -> dict[str, Any] | None:
        """Mark a flow as failed with an error message.

        Args:
            state_param: The OAuth state parameter from the callback.
            error_message: The error message to store.

        Returns:
            The updated flow data, or None if flow not found.
        """
        flow_data = await self.get_flow(state_param)
        if not flow_data:
            return None

        flow_id = flow_data["flow_id"]

        # Update flow status
        flow_data["status"] = "error"
        flow_data["error_message"] = error_message
        await self._cache_set(self._flow_key(flow_id), flow_data)

        # Clean up state mapping
        await self._cache_delete(self._state_key(state_param))

        await logger.awarning(f"OAuth flow {flow_id} failed: {error_message}")
        return flow_data

    async def get_flow_status(
        self,
        flow_id: str,
        user_id: str | UUID,
    ) -> dict[str, Any]:
        """Get the status of an OAuth flow.

        Used by the frontend to poll for completion.

        Args:
            flow_id: The flow ID returned from create_flow.
            user_id: The user ID (for validation).

        Returns:
            A dict with status information:
            - status: "pending" | "complete" | "error" | "expired"
            - error_message: Error message if status is "error"
            - tokens: Tokens if status is "complete" (only access_token exposed)
        """
        flow_data = await self._cache_get(self._flow_key(flow_id))

        if not flow_data:
            return {"status": "expired", "error_message": "OAuth flow expired or not found"}

        # Validate user ownership
        if str(flow_data.get("user_id")) != str(user_id):
            await logger.awarning(
                f"User {user_id} tried to access OAuth flow {flow_id} owned by {flow_data.get('user_id')}"
            )
            return {"status": "expired", "error_message": "OAuth flow not found"}

        status: Literal["pending", "complete", "error", "expired"] = flow_data.get("status", "pending")
        result: dict[str, Any] = {"status": status}

        if status == "error":
            result["error_message"] = flow_data.get("error_message")
        elif status == "complete":
            # Don't expose full tokens to frontend, just indicate success
            # The tokens are stored separately and used by the backend
            result["server_url"] = flow_data.get("server_url")

        return result

    async def store_tokens(
        self,
        user_id: str | UUID,
        server_key: str,
        tokens: dict[str, Any],
    ) -> None:
        """Store OAuth tokens for future use.

        Args:
            user_id: The user ID.
            server_key: A key identifying the MCP server.
            tokens: The tokens to store.
        """
        cache_key = self._tokens_key(user_id, server_key)
        await self._cache_set(cache_key, tokens)
        await logger.ainfo(f"Stored OAuth tokens for user {user_id}, server {server_key}")

    async def get_tokens(
        self,
        user_id: str | UUID,
        server_key: str,
    ) -> dict[str, Any] | None:
        """Get cached OAuth tokens.

        Args:
            user_id: The user ID.
            server_key: A key identifying the MCP server.

        Returns:
            The stored tokens if found and valid, None otherwise.
        """
        cache_key = self._tokens_key(user_id, server_key)
        return await self._cache_get(cache_key)

    async def delete_tokens(
        self,
        user_id: str | UUID,
        server_key: str,
    ) -> bool:
        """Delete stored OAuth tokens.

        Args:
            user_id: The user ID.
            server_key: A key identifying the MCP server.

        Returns:
            True if tokens were deleted, False if not found.
        """
        cache_key = self._tokens_key(user_id, server_key)
        existing = await self._cache_get(cache_key)
        if existing:
            await self._cache_delete(cache_key)
            await logger.ainfo(f"Deleted OAuth tokens for user {user_id}, server {server_key}")
            return True
        return False

    async def _cache_get(self, key: str) -> Any:
        """Get value from cache, handling both sync and async caches."""
        from lfx.services.cache.utils import CACHE_MISS

        try:
            if hasattr(self._cache, "lock"):
                # Async cache (AsyncInMemoryCache, RedisCache)
                result = await self._cache.get(key)
            else:
                # Sync cache (ThreadingInMemoryCache)
                result = self._cache.get(key)

            # Handle CACHE_MISS sentinel
            if result is CACHE_MISS or result is None:
                return None
        except Exception as e:  # noqa: BLE001
            await logger.awarning(f"Cache get error for key {key}: {e}")
            return None
        else:
            return result

    async def _cache_set(self, key: str, value: Any) -> None:
        """Set value in cache, handling both sync and async caches."""
        try:
            if hasattr(self._cache, "lock"):
                # Async cache
                await self._cache.set(key, value)
            else:
                # Sync cache
                self._cache.set(key, value)
        except Exception as e:  # noqa: BLE001
            await logger.awarning(f"Cache set error for key {key}: {e}")

    async def _cache_delete(self, key: str) -> None:
        """Delete value from cache, handling both sync and async caches."""
        try:
            if hasattr(self._cache, "lock"):
                # Async cache
                await self._cache.delete(key)
            else:
                # Sync cache
                self._cache.delete(key)
        except Exception as e:  # noqa: BLE001
            await logger.awarning(f"Cache delete error for key {key}: {e}")


# Global instance, lazily initialized
_state_manager: OAuthStateManager | None = None


async def get_oauth_state_manager() -> OAuthStateManager:
    """Get or create the global OAuth state manager instance.

    Returns:
        The OAuth state manager singleton.
    """
    global _state_manager  # noqa: PLW0603

    if _state_manager is None:
        from langflow.services.deps import get_cache_service

        cache_service = get_cache_service()
        _state_manager = OAuthStateManager(cache_service)

        # Log warning if using in-memory cache in deployed mode
        from lfx.base.mcp.oauth.provider import is_deployed_mode

        if is_deployed_mode():
            # Check if we're using Redis
            cache_type = type(cache_service).__name__
            if "Redis" not in cache_type:
                await logger.awarning(
                    f"Using {cache_type} for OAuth state in deployed mode. "
                    "OAuth flows will not work across multiple server instances. "
                    "Consider configuring Redis for production deployments."
                )

    return _state_manager
