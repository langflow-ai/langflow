"""Unit tests for OAuth provider utilities.

Covers OAuthAuthWrapper (401 token-clearing behaviour) and
OAuthRequiredError (serialisation helper).
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

import httpx
import pytest
from lfx.base.mcp.oauth.provider import OAuthAuthWrapper, OAuthRequiredError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeStorage:
    """In-memory token storage stub used by OAuthAuthWrapper tests."""

    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


def _make_provider() -> MagicMock:
    """Return a minimal mock OAuthClientProvider."""
    provider = MagicMock()
    provider.async_auth_flow = MagicMock()
    return provider


# ---------------------------------------------------------------------------
# OAuthAuthWrapper
# ---------------------------------------------------------------------------


class TestOAuthAuthWrapper:
    @pytest.fixture
    def storage(self) -> _FakeStorage:
        return _FakeStorage()

    @pytest.fixture
    def provider(self) -> MagicMock:
        return _make_provider()

    @pytest.fixture
    def wrapper(self, provider: MagicMock, storage: _FakeStorage) -> OAuthAuthWrapper:
        return OAuthAuthWrapper(provider, storage)

    def test_getattr_delegates_to_provider(self, wrapper: OAuthAuthWrapper, provider: MagicMock) -> None:
        """Attribute access on the wrapper falls through to the underlying provider."""
        provider.some_attr = "hello"
        assert wrapper.some_attr == "hello"

    async def test_async_auth_flow_clears_tokens_on_401(
        self, wrapper: OAuthAuthWrapper, provider: MagicMock, storage: _FakeStorage
    ) -> None:
        """async_auth_flow clears tokens only after the SDK finishes its own retry logic.

        Token clearing is deferred until after the SDK's auth flow generator is
        exhausted, so tokens are only wiped when the final response is still 401.
        """
        request = httpx.Request("GET", "https://mcp.example.com/")

        async def _fake_flow(req: httpx.Request):
            # Single yield: once 401 is received the SDK gives up immediately.
            yield req

        provider.async_auth_flow.return_value = _fake_flow(request)

        gen = wrapper.async_auth_flow(request)
        sent_request = await gen.__anext__()
        assert sent_request == request

        # Sending 401 exhausts the inner flow → StopAsyncIteration breaks the
        # while loop → post-loop check fires → tokens are cleared.
        with contextlib.suppress(StopAsyncIteration):
            await gen.asend(httpx.Response(401))

        assert storage.cleared is True
        assert wrapper._tokens_cleared is True

    async def test_async_auth_flow_does_not_clear_on_200(
        self, wrapper: OAuthAuthWrapper, provider: MagicMock, storage: _FakeStorage
    ) -> None:
        """async_auth_flow does NOT clear tokens when the final response is 200."""
        request = httpx.Request("GET", "https://mcp.example.com/")

        async def _fake_flow(req: httpx.Request):
            yield req

        provider.async_auth_flow.return_value = _fake_flow(request)

        gen = wrapper.async_auth_flow(request)
        await gen.__anext__()
        with contextlib.suppress(StopAsyncIteration):
            await gen.asend(httpx.Response(200))

        assert storage.cleared is False

    async def test_async_auth_flow_clears_tokens_only_once(
        self, wrapper: OAuthAuthWrapper, provider: MagicMock, storage: _FakeStorage
    ) -> None:
        """Tokens are cleared at most once even if async_auth_flow is called twice.

        The _tokens_cleared flag prevents a second invocation from clearing again,
        which guards against double-clearing when the wrapper is reused across retries.
        """
        request = httpx.Request("GET", "https://mcp.example.com/")

        async def _single_yield(req: httpx.Request):
            yield req

        # First invocation ends with 401 → tokens cleared, flag set.
        provider.async_auth_flow.return_value = _single_yield(request)
        gen = wrapper.async_auth_flow(request)
        await gen.__anext__()
        with contextlib.suppress(StopAsyncIteration):
            await gen.asend(httpx.Response(401))
        assert storage.cleared is True

        # Reset to check the second invocation does NOT clear again.
        storage.cleared = False

        # Second invocation also ends with 401, but _tokens_cleared is already True.
        provider.async_auth_flow.return_value = _single_yield(request)
        gen2 = wrapper.async_auth_flow(request)
        await gen2.__anext__()
        with contextlib.suppress(StopAsyncIteration):
            await gen2.asend(httpx.Response(401))

        assert storage.cleared is False


# ---------------------------------------------------------------------------
# OAuthRequiredError
# ---------------------------------------------------------------------------


class TestOAuthRequiredError:
    def test_to_dict_required_fields(self) -> None:
        """to_dict always includes error, message, server_url, and initiate_endpoint."""
        err = OAuthRequiredError(
            message="Please authenticate",
            server_url="https://mcp.example.com",
        )
        data = err.to_dict()
        assert data["error"] == "oauth_required"
        assert data["message"] == "Please authenticate"
        assert data["server_url"] == "https://mcp.example.com"
        assert data["initiate_endpoint"] == "/api/v1/mcp/oauth/initiate"

    def test_to_dict_optional_fields_omitted_when_none(self) -> None:
        """Optional fields (client_id, scopes, etc.) are absent from to_dict when not provided."""
        err = OAuthRequiredError(message="auth needed", server_url="https://mcp.example.com")
        data = err.to_dict()
        assert "client_id" not in data
        assert "client_secret" not in data
        assert "redirect_uri" not in data
        assert "scopes" not in data

    def test_to_dict_optional_fields_present_when_provided(self) -> None:
        """Optional fields appear in to_dict when explicitly set."""
        err = OAuthRequiredError(
            message="auth needed",
            server_url="https://mcp.example.com",
            client_id="my-client",
            client_secret="s3cr3t",  # noqa: S106
            redirect_uri="https://app.example.com/callback",
            scopes=["read", "write"],
        )
        data = err.to_dict()
        assert data["client_id"] == "my-client"
        assert data["client_secret"] == "s3cr3t"  # noqa: S105
        assert data["redirect_uri"] == "https://app.example.com/callback"
        assert data["scopes"] == ["read", "write"]

    def test_custom_initiate_endpoint(self) -> None:
        """A custom initiate_endpoint is reflected in to_dict."""
        err = OAuthRequiredError(
            message="auth",
            server_url="https://mcp.example.com",
            initiate_endpoint="/custom/oauth/start",
        )
        assert err.to_dict()["initiate_endpoint"] == "/custom/oauth/start"

    def test_is_exception(self) -> None:
        """OAuthRequiredError can be raised and caught as a standard exception."""
        with pytest.raises(OAuthRequiredError, match="needs auth"):
            raise OAuthRequiredError(message="needs auth", server_url="https://mcp.example.com")
