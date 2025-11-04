# ruff: noqa: S105, S106, S107, ARG002, DTZ001
from datetime import datetime

import pytest
from langflow.services.connectors.oauth.base import BaseOAuthHandler, OAuthTokens


def test_base_oauth_handler_is_abstract():
    """Test that BaseOAuthHandler is abstract."""
    with pytest.raises(TypeError):
        BaseOAuthHandler("client_id", "client_secret", "redirect_uri")


def test_base_oauth_handler_has_required_methods():
    """Test required methods exist."""
    assert hasattr(BaseOAuthHandler, "get_authorization_url")
    assert hasattr(BaseOAuthHandler, "exchange_code_for_tokens")
    assert hasattr(BaseOAuthHandler, "refresh_access_token")
    assert hasattr(BaseOAuthHandler, "revoke_tokens")


def test_oauth_tokens_model():
    """Test OAuthTokens Pydantic model."""
    tokens = OAuthTokens(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_type="Bearer",
        expires_in=3600,
        scope="https://www.googleapis.com/auth/drive.readonly",
    )

    assert tokens.access_token == "test_access_token"
    assert tokens.refresh_token == "test_refresh_token"
    assert tokens.token_type == "Bearer"
    assert tokens.expires_in == 3600
    assert tokens.scope == "https://www.googleapis.com/auth/drive.readonly"


def test_oauth_tokens_model_optional_fields():
    """Test OAuthTokens with only required fields."""
    tokens = OAuthTokens(access_token="test_access_token")

    assert tokens.access_token == "test_access_token"
    assert tokens.refresh_token is None
    assert tokens.token_type == "Bearer"
    assert tokens.expires_in is None
    assert tokens.expires_at is None
    assert tokens.scope is None


def test_oauth_tokens_with_expires_at():
    """Test OAuthTokens with expires_at datetime."""
    expires_at = datetime(2025, 12, 31, 23, 59, 59)
    tokens = OAuthTokens(access_token="test_access_token", expires_at=expires_at)

    assert tokens.expires_at == expires_at


class ConcreteOAuthHandler(BaseOAuthHandler):
    """Concrete implementation for testing."""

    def get_authorization_url(self, state: str, scopes: list[str], **kwargs) -> str:
        return f"https://oauth.example.com/authorize?state={state}&scopes={','.join(scopes)}"

    async def exchange_code_for_tokens(self, code: str, **kwargs) -> OAuthTokens:
        return OAuthTokens(access_token=f"token_for_{code}")

    async def refresh_access_token(self, refresh_token: str, **kwargs) -> OAuthTokens:
        return OAuthTokens(access_token=f"refreshed_{refresh_token}")

    async def revoke_tokens(self, token: str, token_type: str = "access_token", **kwargs) -> bool:
        return True


def test_concrete_oauth_handler_instantiation():
    """Test that concrete implementation can be instantiated."""
    handler = ConcreteOAuthHandler(
        client_id="test_client_id", client_secret="test_client_secret", redirect_uri="https://example.com/callback"
    )

    assert handler.client_id == "test_client_id"
    assert handler.client_secret == "test_client_secret"  # pragma: allowlist secret
    assert handler.redirect_uri == "https://example.com/callback"


def test_concrete_oauth_handler_get_authorization_url():
    """Test get_authorization_url implementation."""
    handler = ConcreteOAuthHandler(
        client_id="test_client_id", client_secret="test_client_secret", redirect_uri="https://example.com/callback"
    )

    url = handler.get_authorization_url(state="test_state", scopes=["scope1", "scope2"])

    assert "test_state" in url
    assert "scope1" in url
    assert "scope2" in url


@pytest.mark.asyncio
async def test_concrete_oauth_handler_exchange_code():
    """Test exchange_code_for_tokens implementation."""
    handler = ConcreteOAuthHandler(
        client_id="test_client_id", client_secret="test_client_secret", redirect_uri="https://example.com/callback"
    )

    tokens = await handler.exchange_code_for_tokens(code="auth_code_123")

    assert tokens.access_token == "token_for_auth_code_123"


@pytest.mark.asyncio
async def test_concrete_oauth_handler_refresh_token():
    """Test refresh_access_token implementation."""
    handler = ConcreteOAuthHandler(
        client_id="test_client_id", client_secret="test_client_secret", redirect_uri="https://example.com/callback"
    )

    tokens = await handler.refresh_access_token(refresh_token="old_refresh_token")

    assert tokens.access_token == "refreshed_old_refresh_token"


@pytest.mark.asyncio
async def test_concrete_oauth_handler_revoke_tokens():
    """Test revoke_tokens implementation."""
    handler = ConcreteOAuthHandler(
        client_id="test_client_id", client_secret="test_client_secret", redirect_uri="https://example.com/callback"
    )

    result = await handler.revoke_tokens(token="token_to_revoke")

    assert result is True


def test_generate_state_token():
    """Test generate_state_token helper method."""
    handler = ConcreteOAuthHandler(
        client_id="test_client_id", client_secret="test_client_secret", redirect_uri="https://example.com/callback"
    )

    state1 = handler.generate_state_token()
    state2 = handler.generate_state_token()

    # Should generate different tokens
    assert state1 != state2
    # Should be non-empty strings
    assert isinstance(state1, str)
    assert len(state1) > 0
    assert isinstance(state2, str)
    assert len(state2) > 0
