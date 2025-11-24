"""Abstract base class for authentication services.

This module defines the interface that all authentication implementations must follow.
Both the default JWT-based authentication and future OIDC implementations should
extend this base class.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from langflow.services.base import Service
from langflow.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from uuid import UUID

    from fastapi import Request
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User, UserRead


class AuthServiceBase(Service, abc.ABC):
    """Abstract base class for authentication services.

    This defines the contract that any authentication implementation must fulfill.
    Implementations include:
    - Default JWT-based authentication (AuthService)
    - Future OIDC authentication (OIDCAuthService)
    """

    name = ServiceType.AUTH_SERVICE.value

    # -------------------------------------------------------------------------
    # Core Authentication Methods (REQUIRED for all implementations)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def get_current_user(
        self,
        token: str | Coroutine | None,
        query_param: str | None,
        header_param: str | None,
        db: AsyncSession,
    ) -> User:
        """Get the current authenticated user from token or API key.

        Args:
            token: JWT/OAuth token (may be a coroutine that resolves to token)
            query_param: API key from query parameter
            header_param: API key from header
            db: Database session

        Returns:
            The authenticated User object

        Raises:
            HTTPException: If authentication fails
        """

    @abc.abstractmethod
    async def get_current_user_for_websocket(
        self,
        token: str | None,
        api_key: str | None,
        db: AsyncSession,
    ) -> User | UserRead:
        """Get the current user for WebSocket connections.

        Args:
            token: Access token from cookie or query param
            api_key: API key from query param or header
            db: Database session

        Returns:
            User or UserRead object

        Raises:
            WebSocketException: If authentication fails
        """

    @abc.abstractmethod
    async def authenticate_user(
        self,
        username: str,
        password: str,
        db: AsyncSession,
    ) -> User | None:
        """Authenticate a user with username and password.

        Args:
            username: The username
            password: The plain text password
            db: Database session

        Returns:
            User if authentication succeeds, None otherwise

        Raises:
            HTTPException: For specific auth failures (inactive user, etc.)
        """

    # -------------------------------------------------------------------------
    # User Validation Methods (REQUIRED for all implementations)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def get_current_active_user(self, current_user: User) -> User:
        """Validate that the current user is active.

        Args:
            current_user: The authenticated user

        Returns:
            The user if active

        Raises:
            HTTPException: If user is inactive
        """

    @abc.abstractmethod
    async def get_current_active_superuser(self, current_user: User) -> User:
        """Validate that the current user is an active superuser.

        Args:
            current_user: The authenticated user

        Returns:
            The user if active and superuser

        Raises:
            HTTPException: If user is inactive or not superuser
        """

    # -------------------------------------------------------------------------
    # Token/Session Management (REQUIRED - but implementation varies)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def create_user_tokens(
        self,
        user_id: UUID,
        db: AsyncSession,
        *,
        update_last_login: bool = False,
    ) -> dict:
        """Create authentication tokens for a user.

        The exact token format depends on the implementation:
        - JWT auth: Returns access_token and refresh_token
        - OIDC: May return tokens from the identity provider

        Args:
            user_id: The user's ID
            db: Database session
            update_last_login: Whether to update last login timestamp

        Returns:
            Dict containing token information (at minimum: access_token, token_type)
        """

    @abc.abstractmethod
    async def create_refresh_token(
        self,
        refresh_token: str,
        db: AsyncSession,
    ) -> dict:
        """Create new tokens from a refresh token.

        Args:
            refresh_token: The refresh token
            db: Database session

        Returns:
            Dict containing new token information

        Raises:
            HTTPException: If refresh token is invalid
        """

    # -------------------------------------------------------------------------
    # API Key Security (REQUIRED for all implementations)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def api_key_security(
        self,
        query_param: str | None,
        header_param: str | None,
    ) -> UserRead | None:
        """Validate API key from query or header.

        Args:
            query_param: API key from query parameter
            header_param: API key from header

        Returns:
            UserRead if valid, None otherwise

        Raises:
            HTTPException: If API key validation fails
        """

    @abc.abstractmethod
    async def ws_api_key_security(self, api_key: str | None) -> UserRead:
        """Validate API key for WebSocket connections.

        Args:
            api_key: The API key

        Returns:
            UserRead for the authenticated user

        Raises:
            WebSocketException: If API key is invalid
        """

    # -------------------------------------------------------------------------
    # Webhook Authentication (REQUIRED for all implementations)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def get_webhook_user(self, flow_id: str, request: Request) -> UserRead:
        """Get the user for webhook execution.

        Args:
            flow_id: The flow ID being executed
            request: The FastAPI request object

        Returns:
            UserRead for the webhook user

        Raises:
            HTTPException: If authentication fails
        """

    # -------------------------------------------------------------------------
    # User Management (REQUIRED for all implementations)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def create_super_user(
        self,
        username: str,
        password: str,
        db: AsyncSession,
    ) -> User:
        """Create or get the superuser.

        Args:
            username: Superuser username
            password: Superuser password
            db: Database session

        Returns:
            The superuser User object
        """

    @abc.abstractmethod
    async def create_user_longterm_token(
        self,
        db: AsyncSession,
    ) -> tuple[UUID, dict]:
        """Create a long-term token for auto-login scenarios.

        Args:
            db: Database session

        Returns:
            Tuple of (user_id, token_dict)

        Raises:
            HTTPException: If auto-login is not enabled
        """

    @abc.abstractmethod
    def create_user_api_key(self, user_id: UUID) -> dict:
        """Create an API key for a user.

        Args:
            user_id: The user's ID

        Returns:
            Dict containing the API key
        """

    # -------------------------------------------------------------------------
    # Password Utilities (May not be used by all implementations)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.

        Args:
            plain_password: The plain text password
            hashed_password: The hashed password

        Returns:
            True if password matches, False otherwise
        """

    @abc.abstractmethod
    def get_password_hash(self, password: str) -> str:
        """Hash a password.

        Args:
            password: The plain text password

        Returns:
            The hashed password
        """

    # -------------------------------------------------------------------------
    # API Key Encryption (Shared utility methods)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt an API key for storage.

        Args:
            api_key: The plain API key

        Returns:
            The encrypted API key
        """

    @abc.abstractmethod
    def decrypt_api_key(self, encrypted_api_key: str) -> str:
        """Decrypt a stored API key.

        Args:
            encrypted_api_key: The encrypted API key

        Returns:
            The decrypted API key
        """

    # -------------------------------------------------------------------------
    # MCP-specific Authentication (REQUIRED for MCP support)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def get_current_user_mcp(
        self,
        token: str | Coroutine | None,
        query_param: str | None,
        header_param: str | None,
        db: AsyncSession,
    ) -> User:
        """Get current user for MCP endpoints (more permissive auto-login).

        Args:
            token: JWT/OAuth token
            query_param: API key from query parameter
            header_param: API key from header
            db: Database session

        Returns:
            The authenticated User object

        Raises:
            HTTPException: If authentication fails
        """

    @abc.abstractmethod
    async def get_current_active_user_mcp(self, current_user: User) -> User:
        """Validate that the current MCP user is active.

        Args:
            current_user: The authenticated user

        Returns:
            The user if active

        Raises:
            HTTPException: If user is inactive
        """
