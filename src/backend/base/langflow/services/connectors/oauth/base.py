from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class OAuthTokens(BaseModel):
    """OAuth token response."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"  # noqa: S105
    expires_in: int | None = None
    expires_at: datetime | None = None
    scope: str | None = None


class BaseOAuthHandler(ABC):
    """Abstract base class for OAuth handlers."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """Initialize OAuth handler.

        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Redirect URI for OAuth callback
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    @abstractmethod
    def get_authorization_url(self, state: str, scopes: list[str], **kwargs) -> str:
        """Generate OAuth authorization URL.

        Args:
            state: CSRF protection token
            scopes: OAuth scopes to request
            **kwargs: Provider-specific parameters

        Returns:
            Authorization URL
        """

    @abstractmethod
    async def exchange_code_for_tokens(self, code: str, **kwargs) -> OAuthTokens:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback
            **kwargs: Provider-specific parameters

        Returns:
            OAuth tokens
        """

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str, **kwargs) -> OAuthTokens:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Current refresh token
            **kwargs: Provider-specific parameters

        Returns:
            New OAuth tokens
        """

    @abstractmethod
    async def revoke_tokens(self, token: str, token_type: str = "access_token", **kwargs) -> bool:  # noqa: S107
        """Revoke OAuth tokens.

        Args:
            token: Token to revoke
            token_type: Type of token (access_token or refresh_token)
            **kwargs: Provider-specific parameters

        Returns:
            True if revoked successfully
        """

    def generate_state_token(self) -> str:
        """Generate secure state token for CSRF protection.

        Returns:
            Random state token
        """
        import secrets

        return secrets.token_urlsafe(32)
