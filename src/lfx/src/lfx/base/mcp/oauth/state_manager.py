"""OAuth state manager for MCP deployment-ready authentication.

This module provides a state manager that stores OAuth flow state using
the CacheService, enabling OAuth flows to work in multi-instance deployments.
"""

from __future__ import annotations

import asyncio
import inspect
import secrets
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlparse
from uuid import UUID, uuid4

from lfx.log.logger import logger

if TYPE_CHECKING:
    from langflow.services.cache.base import AsyncBaseCacheService, CacheService


def _get_server_key(server_url: str) -> str:
    """Generate a cache-safe key from a server URL.

    This is a local copy to avoid circular imports with provider.py.

    Args:
        server_url: The MCP server URL.

    Returns:
        A safe string key for cache storage.
    """
    parsed = urlparse(server_url)
    return f"{parsed.netloc}{parsed.path}".replace("/", "_").replace(":", "_")


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

    async def get_flow_by_id(self, flow_id: str) -> dict[str, Any] | None:
        """Get flow data directly by flow ID.

        Args:
            flow_id: The flow ID.

        Returns:
            The flow data dict if found, None otherwise.
        """
        return await self._cache_get(self._flow_key(flow_id))

    async def store_callback(self, state_param: str, code: str) -> bool:
        """Store OAuth callback code for retrieval by SDK's callback_handler.

        This is called by the /callback endpoint when the OAuth provider
        redirects back with the authorization code. The SDK's callback_handler
        (via get_callback) will retrieve this code to complete the token exchange.

        Args:
            state_param: The OAuth state parameter from the callback.
            code: The authorization code from the OAuth provider.

        Returns:
            True if callback was stored successfully, False if flow not found.
        """
        flow_data = await self.get_flow(state_param)
        if not flow_data:
            return False

        flow_id = flow_data["flow_id"]
        flow_data["callback_code"] = code
        flow_data["callback_received"] = True
        flow_data["callback_state"] = state_param
        await self._cache_set(self._flow_key(flow_id), flow_data)

        await logger.ainfo(f"Stored OAuth callback for flow {flow_id}")
        return True

    async def get_callback(self, flow_id: str, timeout: float = 300.0) -> tuple[str, str | None]:
        """Wait for and retrieve callback code (used by SDK's callback_handler).

        This method polls the cache waiting for the callback to be stored
        by the /callback endpoint. Once received, it returns the authorization
        code and state for the SDK to complete the token exchange.

        Args:
            flow_id: The flow ID to wait for callback on.
            timeout: Maximum time to wait for callback in seconds.

        Returns:
            A tuple of (authorization_code, state_param).

        Raises:
            TimeoutError: If callback is not received within timeout.
            ValueError: If flow not found or callback failed.
        """
        loop = asyncio.get_running_loop()
        start = loop.time()
        while loop.time() - start < timeout:
            flow_data = await self._cache_get(self._flow_key(flow_id))
            if not flow_data:
                msg = f"OAuth flow {flow_id} not found or expired"
                raise ValueError(msg)

            if flow_data.get("callback_received"):
                code = flow_data.get("callback_code")
                state = flow_data.get("callback_state")
                if code:
                    await logger.ainfo(f"Retrieved OAuth callback for flow {flow_id}")
                    return code, state
                msg = f"OAuth flow {flow_id} callback received but no code"
                raise ValueError(msg)

            if flow_data.get("status") == "error":
                error_msg = flow_data.get("error_message", "Unknown error")
                msg = f"OAuth flow {flow_id} failed: {error_msg}"
                raise ValueError(msg)

            await asyncio.sleep(0.5)

        msg = f"OAuth callback not received for flow {flow_id} within {timeout}s"
        raise TimeoutError(msg)

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
        server_key = _get_server_key(server_url)
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
            - status: "pending" | "awaiting_callback" | "complete" | "error" | "expired"
            - auth_url: Authorization URL if status is "awaiting_callback"
            - error_message: Error message if status is "error"
            - server_url: Server URL if status is "complete"
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

        status: Literal["pending", "awaiting_callback", "complete", "error", "expired"] = flow_data.get(
            "status", "pending"
        )
        result: dict[str, Any] = {"status": status}

        if status == "awaiting_callback":
            # Include the auth URL so frontend can open it
            result["auth_url"] = flow_data.get("auth_url")
        elif status == "error":
            result["error_message"] = flow_data.get("error_message")
        elif status == "complete":
            # Don't expose full tokens to frontend, just indicate success
            # The tokens are stored separately and used by the backend
            result["server_url"] = flow_data.get("server_url")

        return result

    async def update_flow(self, flow_id: str, updates: dict[str, Any]) -> bool:
        """Merge updates into existing flow data and persist.

        Args:
            flow_id: The flow ID to update.
            updates: Key/value pairs to merge into the flow data.

        Returns:
            True if the flow was found and updated, False if not found.
        """
        flow_data = await self._cache_get(self._flow_key(flow_id))
        if flow_data is None:
            return False
        flow_data.update(updates)
        await self._cache_set(self._flow_key(flow_id), flow_data)
        return True

    async def map_sdk_state(self, sdk_state: str, flow_id: str) -> None:
        """Store a mapping from the MCP SDK's OAuth state parameter to a flow ID.

        The SDK generates its own state parameter when building the authorization URL.
        This mapping allows the callback endpoint to find the correct flow when the
        OAuth provider redirects back with the SDK's state parameter.

        Args:
            sdk_state: The OAuth state parameter generated by the MCP SDK.
            flow_id: The internal flow ID to map to.
        """
        await self._cache_set(self._state_key(sdk_state), flow_id)

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

    def _is_async_cache(self) -> bool:
        """Return True if the cache's get method is a coroutine function."""
        return inspect.iscoroutinefunction(self._cache.get)

    async def _cache_get(self, key: str) -> Any:
        """Get value from cache, handling both sync and async caches."""
        from lfx.services.cache.utils import CACHE_MISS

        try:
            if self._is_async_cache():
                result = await self._cache.get(key)
            else:
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
            if self._is_async_cache():
                await self._cache.set(key, value)
            else:
                self._cache.set(key, value)
        except Exception as e:  # noqa: BLE001
            await logger.awarning(f"Cache set error for key {key}: {e}")

    async def _cache_delete(self, key: str) -> None:
        """Delete value from cache, handling both sync and async caches."""
        try:
            if self._is_async_cache():
                await self._cache.delete(key)
            else:
                self._cache.delete(key)
        except Exception as e:  # noqa: BLE001
            await logger.awarning(f"Cache delete error for key {key}: {e}")


# Global instance, lazily initialized
_state_manager: OAuthStateManager | None = None
_state_manager_lock: asyncio.Lock | None = None


def _get_state_manager_lock() -> asyncio.Lock:
    """Return (or lazily create) the module-level initialisation lock."""
    global _state_manager_lock  # noqa: PLW0603
    if _state_manager_lock is None:
        _state_manager_lock = asyncio.Lock()
    return _state_manager_lock


async def get_oauth_state_manager() -> OAuthStateManager:
    """Get or create the global OAuth state manager instance.

    Uses a double-checked locking pattern so that concurrent coroutines
    never create more than one OAuthStateManager.

    Returns:
        The OAuth state manager singleton.
    """
    global _state_manager  # noqa: PLW0603

    if _state_manager is not None:
        return _state_manager

    async with _get_state_manager_lock():
        if _state_manager is not None:
            return _state_manager

        from langflow.services.deps import get_cache_service

        cache_service = get_cache_service()
        _state_manager = OAuthStateManager(cache_service)

        # Log warning if using in-memory cache (won't work across instances)
        cache_type = type(cache_service).__name__
        if "Redis" not in cache_type:
            await logger.ainfo(
                f"Using {cache_type} for OAuth state. For multi-instance deployments, configure Redis for shared state."
            )

    return _state_manager
