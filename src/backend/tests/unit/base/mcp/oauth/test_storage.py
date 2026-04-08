"""Unit tests for UserScopedTokenStorage.

Covers get_tokens, set_tokens, get_client_info, set_client_info, and clear.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from lfx.base.mcp.oauth.state_manager import OAuthStateManager
from lfx.base.mcp.oauth.storage import UserScopedTokenStorage


class _DictCache:
    """Minimal async in-memory cache used to back OAuthStateManager in tests."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> Any:
        return self._store.get(key)

    async def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture
def state_manager() -> OAuthStateManager:
    return OAuthStateManager(_DictCache())


@pytest.fixture
def storage(state_manager: OAuthStateManager) -> UserScopedTokenStorage:
    return UserScopedTokenStorage("user-1", "https://mcp.example.com", state_manager)


class TestGetAndSetTokens:
    async def test_get_tokens_empty(self, storage: UserScopedTokenStorage) -> None:
        """get_tokens returns None when no tokens have been stored."""
        result = await storage.get_tokens()
        assert result is None

    async def test_set_and_get_tokens(self, storage: UserScopedTokenStorage) -> None:
        """Tokens stored via set_tokens are retrievable as an OAuthToken object."""
        from mcp.shared.auth import OAuthToken

        token = OAuthToken(
            access_token="access-abc",  # noqa: S106
            token_type="Bearer",  # noqa: S106
        )
        await storage.set_tokens(token)

        retrieved = await storage.get_tokens()
        assert retrieved is not None
        assert retrieved.access_token == "access-abc"  # noqa: S105
        assert retrieved.token_type == "Bearer"  # noqa: S105

    async def test_tokens_are_user_and_server_scoped(self, state_manager: OAuthStateManager) -> None:
        """Tokens for one user+server do not leak to a different user+server combination."""
        from mcp.shared.auth import OAuthToken

        storage_a = UserScopedTokenStorage("user-1", "https://mcp.example.com", state_manager)
        storage_b = UserScopedTokenStorage("user-2", "https://mcp.example.com", state_manager)

        token = OAuthToken(access_token="tok-a", token_type="Bearer")  # noqa: S106
        await storage_a.set_tokens(token)

        assert await storage_b.get_tokens() is None

    async def test_tokens_are_server_scoped(self, state_manager: OAuthStateManager) -> None:
        """Tokens for the same user but different servers are stored independently."""
        from mcp.shared.auth import OAuthToken

        storage_a = UserScopedTokenStorage("user-1", "https://server-a.com", state_manager)
        storage_b = UserScopedTokenStorage("user-1", "https://server-b.com", state_manager)

        token = OAuthToken(access_token="tok-a", token_type="Bearer")  # noqa: S106
        await storage_a.set_tokens(token)

        assert await storage_b.get_tokens() is None


class TestClientInfo:
    async def test_get_client_info_empty(self, storage: UserScopedTokenStorage) -> None:
        """get_client_info returns None before any client info is stored."""
        result = await storage.get_client_info()
        assert result is None

    async def test_set_and_get_client_info(self, storage: UserScopedTokenStorage) -> None:
        """Client info stored via set_client_info is retrievable."""
        from mcp.shared.auth import OAuthClientInformationFull

        info = OAuthClientInformationFull(
            client_id="my-client-id",
            redirect_uris=["https://app.example.com/callback"],
        )
        await storage.set_client_info(info)

        retrieved = await storage.get_client_info()
        assert retrieved is not None
        assert retrieved.client_id == "my-client-id"


class TestClear:
    async def test_clear_removes_tokens(self, storage: UserScopedTokenStorage) -> None:
        """clear() deletes stored tokens so get_tokens returns None afterwards."""
        from mcp.shared.auth import OAuthToken

        await storage.set_tokens(OAuthToken(access_token="tok", token_type="Bearer"))  # noqa: S106
        await storage.clear()
        assert await storage.get_tokens() is None

    async def test_clear_resets_client_info(self, storage: UserScopedTokenStorage) -> None:
        """clear() sets the in-memory client_info back to None."""
        from mcp.shared.auth import OAuthClientInformationFull

        info = OAuthClientInformationFull(
            client_id="cid",
            redirect_uris=["https://app.example.com/callback"],
        )
        await storage.set_client_info(info)
        await storage.clear()
        assert await storage.get_client_info() is None

    async def test_clear_on_empty_storage_does_not_raise(self, storage: UserScopedTokenStorage) -> None:
        """clear() is safe to call even when no tokens have been stored."""
        await storage.clear()  # should not raise
