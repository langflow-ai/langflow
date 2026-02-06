"""Abstract base class for authentication services.

Defines the interface that all auth implementations must follow in the
pluggable services architecture. LFX provides a minimal no-op implementation;
full-featured implementations (JWT, OIDC, SAML) live in Langflow or plugins.

"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

from lfx.services.base import Service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from datetime import timedelta
    from uuid import UUID


class BaseAuthService(Service, abc.ABC):
    """Abstract base class for authentication services."""

    name = ServiceType.AUTH_SERVICE.value

    @abc.abstractmethod
    async def authenticate_with_credentials(
        self,
        token: str | None,
        api_key: str | None,
        db: Any,
    ) -> Any:
        """Authenticate user with provided credentials.

        Args:
            token: Access token (JWT, OIDC, etc.)
            api_key: API key
            db: Database session for user lookup/creation

        Returns:
            User or user-read object (id, username, is_active, is_superuser)

        Raises:
            MissingCredentialsError: No credentials provided
            InvalidCredentialsError: Invalid credentials
            InvalidTokenError: Invalid token
            TokenExpiredError: Token expired
            InactiveUserError: User inactive
        """

    @abc.abstractmethod
    async def get_current_user(
        self,
        token: str | Coroutine[Any, Any, str] | None,
        query_param: str | None,
        header_param: str | None,
        db: Any,
    ) -> Any:
        """Get the current authenticated user from token or API key.

        Args:
            token: JWT/OAuth token (may be a coroutine)
            query_param: API key from query
            header_param: API key from header
            db: Database session

        Returns:
            User or user-read object
        """

    @abc.abstractmethod
    async def get_current_user_for_websocket(
        self,
        token: str | None,
        api_key: str | None,
        db: Any,
    ) -> Any:
        """Get current user for WebSocket connections."""

    @abc.abstractmethod
    async def get_current_user_for_sse(
        self,
        token: str | None,
        api_key: str | None,
        db: Any,
    ) -> Any:
        """Get current user for SSE connections."""

    @abc.abstractmethod
    async def authenticate_user(
        self,
        username: str,
        password: str,
        db: Any,
    ) -> Any | None:
        """Authenticate with username and password. Returns user or None."""

    # -------------------------------------------------------------------------
    # User validation
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def get_current_active_user(self, current_user: Any) -> Any | None:
        """Return user if active, None otherwise."""

    @abc.abstractmethod
    async def get_current_active_superuser(self, current_user: Any) -> Any | None:
        """Return user if active superuser, None otherwise."""

    # -------------------------------------------------------------------------
    # Token/session management
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def create_user_tokens(
        self,
        user_id: UUID,
        db: Any,
        *,
        update_last_login: bool = False,
    ) -> dict[str, Any]:
        """Create auth tokens for a user. Returns dict with at least access_token, token_type."""

    @abc.abstractmethod
    async def create_refresh_token(self, refresh_token: str, db: Any) -> dict[str, Any]:
        """Create new tokens from a refresh token."""

    # -------------------------------------------------------------------------
    # API key security
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def api_key_security(
        self,
        query_param: str | None,
        header_param: str | None,
        db: Any | None = None,
    ) -> Any | None:
        """Validate API key from query or header. Returns user-read or None."""

    @abc.abstractmethod
    async def ws_api_key_security(self, api_key: str | None) -> Any:
        """Validate API key for WebSocket. Returns user-read or raises."""

    # -------------------------------------------------------------------------
    # Webhook / user management (required by API)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def get_webhook_user(self, flow_id: str, request: Any) -> Any:
        """Get user for webhook execution."""

    @abc.abstractmethod
    async def create_super_user(self, username: str, password: str, db: Any) -> Any:
        """Create superuser."""

    @abc.abstractmethod
    async def create_user_longterm_token(self, db: Any) -> tuple[UUID, dict[str, Any]]:
        """Create long-term token for auto-login. Returns (user_id, token_dict)."""

    @abc.abstractmethod
    def create_user_api_key(self, user_id: UUID) -> dict[str, Any]:
        """Create an API key for a user."""

    # -------------------------------------------------------------------------
    # API key encryption (required)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt an API key for storage."""

    @abc.abstractmethod
    def decrypt_api_key(self, encrypted_api_key: str) -> str:
        """Decrypt a stored API key."""

    # -------------------------------------------------------------------------
    # MCP auth
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def get_current_user_mcp(
        self,
        token: str | Coroutine[Any, Any, str] | None,
        query_param: str | None,
        header_param: str | None,
        db: Any,
    ) -> Any:
        """Get current user for MCP endpoints."""

    @abc.abstractmethod
    async def get_current_active_user_mcp(self, current_user: Any) -> Any:
        """Validate that the MCP user is active."""

    # -------------------------------------------------------------------------
    # Token helpers (used by utils/API)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def get_current_user_from_access_token(self, token: str | Coroutine[Any, Any, str] | None, db: Any) -> Any:
        """Get user from access token only."""

    @abc.abstractmethod
    def create_token(self, data: dict[str, Any], expires_delta: timedelta) -> str:
        """Create an access token."""

    @abc.abstractmethod
    def get_user_id_from_token(self, token: str) -> UUID:
        """Extract user ID from a token."""

    # -------------------------------------------------------------------------
    # JIT user provisioning (optional; default: NotImplementedError)
    # -------------------------------------------------------------------------

    async def get_or_create_user_from_claims(self, claims: dict, db: Any) -> Any:
        """Get or create user from identity provider claims. Override for OIDC/SAML."""
        msg = f"{self.__class__.__name__} does not support JIT provisioning."
        raise NotImplementedError(msg)

    def extract_user_info_from_claims(self, claims: dict) -> dict:
        """Extract user info from provider claims. Override for OIDC/SAML."""
        msg = f"{self.__class__.__name__} does not extract user info from claims."
        raise NotImplementedError(msg)

    # -------------------------------------------------------------------------
    # Optional: password helpers (no-op for OIDC/minimal)
    # -------------------------------------------------------------------------

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password. Minimal/OIDC implementations raise NotImplementedError."""
        msg = f"{self.__class__.__name__} does not manage passwords locally."
        raise NotImplementedError(msg)

    def get_password_hash(self, password: str) -> str:
        """Hash password. Minimal/OIDC implementations raise NotImplementedError."""
        msg = f"{self.__class__.__name__} does not manage passwords locally."
        raise NotImplementedError(msg)
