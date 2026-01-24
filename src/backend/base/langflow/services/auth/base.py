"""Abstract base class for authentication services.

This module defines the interface that all authentication implementations must follow.
Both the default JWT-based authentication and future OIDC/SAML implementations should
extend this base class.

Design Principles:
------------------
1. **Unified Identity Type**: Methods return `User | UserRead` where the caller may
   receive either a full database entity or a lightweight DTO. Callers should handle
   both types appropriately (both have `id`, `username`, `is_active`, `is_superuser`).

2. **Session Consistency**: Database sessions are passed through the auth chain to
   ensure transactional consistency and avoid multiple concurrent connections.

3. **JIT Provisioning**: OIDC/SAML implementations can use `get_or_create_user_from_claims`
   to automatically create users on first login using identity provider claims.

4. **Password Methods**: Password hashing/verification methods have default implementations
   that raise NotImplementedError. OIDC implementations don't manage passwords locally.

5. **Token Abstraction**: Token creation/validation is abstracted to support both local
   JWT tokens and external identity provider tokens.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from langflow.services.base import Service
from langflow.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from datetime import timedelta
    from uuid import UUID

    from fastapi import Request
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User, UserRead


class AuthServiceBase(Service, abc.ABC):
    """Abstract base class for authentication services.

    This defines the contract that any authentication implementation must fulfill.
    Implementations include:
    - Default JWT-based authentication (AuthService)
    - OIDC authentication (for Okta, Auth0, Azure AD, etc.)
    - SAML authentication (for enterprise SSO)

    Type Conventions:
    -----------------
    - `User`: Full SQLModel entity with all fields including password hash.
              Use when you need to modify the user or access relationships.
    - `UserRead`: Lightweight DTO without sensitive fields.
              Use for read-only operations, API responses, and caching.
    - `User | UserRead`: Either type is acceptable. Both share common identity
              fields: `id`, `username`, `is_active`, `is_superuser`.
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
    ) -> User | UserRead:
        """Get the current authenticated user from token or API key.

        This is the primary authentication entry point. It should:
        1. Try token-based auth first (JWT, OIDC token, etc.)
        2. Fall back to API key auth if no token provided
        3. For OIDC: Perform JIT provisioning if user doesn't exist

        Args:
            token: JWT/OAuth token (may be a coroutine that resolves to token)
            query_param: API key from query parameter
            header_param: API key from header
            db: Database session for user lookup/creation

        Returns:
            User or UserRead object representing the authenticated identity.
            Both types have: id, username, is_active, is_superuser.

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
    async def get_current_active_user(self, current_user: User | UserRead) -> User | UserRead:
        """Validate that the current user is active.

        Args:
            current_user: The authenticated user (User or UserRead)

        Returns:
            The same user object if active

        Raises:
            HTTPException: If user is inactive
        """

    @abc.abstractmethod
    async def get_current_active_superuser(self, current_user: User | UserRead) -> User | UserRead:
        """Validate that the current user is an active superuser.

        Args:
            current_user: The authenticated user (User or UserRead)

        Returns:
            The same user object if active and superuser

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
        db: AsyncSession | None = None,
    ) -> UserRead | None:
        """Validate API key from query or header.

        Args:
            query_param: API key from query parameter
            header_param: API key from header
            db: Optional database session. If provided, use this session for
                user lookup to maintain transactional consistency. If None,
                the implementation should create its own session.

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
    # Password Utilities (Optional - not used by OIDC/SAML implementations)
    # -------------------------------------------------------------------------
    # These methods have default implementations that raise NotImplementedError.
    # Override them only if your auth service manages passwords locally (e.g., JWT auth).
    # OIDC/SAML implementations delegate password management to the identity provider.

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.

        Note: OIDC/SAML implementations should NOT override this method.
        Passwords are managed by the external identity provider.

        Args:
            plain_password: The plain text password
            hashed_password: The hashed password

        Returns:
            True if password matches, False otherwise

        Raises:
            NotImplementedError: If called on an implementation that doesn't manage passwords
        """
        msg = f"{self.__class__.__name__} does not manage passwords locally. Use the identity provider."
        raise NotImplementedError(msg)

    def get_password_hash(self, password: str) -> str:
        """Hash a password.

        Note: OIDC/SAML implementations should NOT override this method.
        Passwords are managed by the external identity provider.

        Args:
            password: The plain text password

        Returns:
            The hashed password

        Raises:
            NotImplementedError: If called on an implementation that doesn't manage passwords
        """
        msg = f"{self.__class__.__name__} does not manage passwords locally. Use the identity provider."
        raise NotImplementedError(msg)

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
    ) -> User | UserRead:
        """Get current user for MCP endpoints (more permissive auto-login).

        MCP endpoints may have different authentication requirements than
        regular API endpoints. For example, they may allow auto-login without
        requiring an API key when AUTO_LOGIN is enabled.

        Args:
            token: JWT/OAuth token
            query_param: API key from query parameter
            header_param: API key from header
            db: Database session

        Returns:
            User or UserRead object representing the authenticated identity

        Raises:
            HTTPException: If authentication fails
        """

    @abc.abstractmethod
    async def get_current_active_user_mcp(self, current_user: User | UserRead) -> User | UserRead:
        """Validate that the current MCP user is active.

        Args:
            current_user: The authenticated user (User or UserRead)

        Returns:
            The same user object if active

        Raises:
            HTTPException: If user is inactive
        """

    # -------------------------------------------------------------------------
    # Methods required by public API (utils.py)
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    async def get_current_user_from_access_token(
        self, token: str | Coroutine | None, db: AsyncSession
    ) -> User | UserRead:
        """Get the current user from an access token.

        For OIDC implementations, this method should:
        1. Validate the token (verify signature, check expiration)
        2. Extract claims from the token
        3. Look up or create the user via get_or_create_user_from_claims

        Args:
            token: The access token (JWT, OIDC ID token, etc.), may be None
            db: Database session for user lookup/creation

        Returns:
            User or UserRead object representing the authenticated identity

        Raises:
            HTTPException: If token is invalid or authentication fails
        """

    @abc.abstractmethod
    def create_token(self, data: dict, expires_delta: timedelta) -> str:
        """Create an access token for the given data and expiration.

        Args:
            data: The payload to encode in the token
            expires_delta: Expiration time as a timedelta

        Returns:
            The encoded token as a string
        """

    @abc.abstractmethod
    def get_user_id_from_token(self, token: str) -> UUID:
        """Extract the user ID from a token.

        Args:
            token: The access token

        Returns:
            The user ID as a UUID
        """

    # -------------------------------------------------------------------------
    # JIT (Just-In-Time) User Provisioning (Optional - for OIDC/SAML)
    # -------------------------------------------------------------------------
    # These methods support automatic user creation when authenticating via
    # external identity providers. Override them in OIDC/SAML implementations.

    async def get_or_create_user_from_claims(
        self,
        claims: dict,
        db: AsyncSession,
    ) -> User:
        """Get or create a user based on identity provider claims.

        This method implements JIT (Just-In-Time) provisioning for OIDC/SAML.
        When a user authenticates via an external identity provider for the
        first time, this method creates their local account using the claims
        from the identity token.

        The default implementation raises NotImplementedError. OIDC/SAML
        implementations should override this to extract user info from claims
        and create/update the local user record.

        Standard OIDC claims that may be available:
        - sub: Unique identifier for the user (required)
        - email: User's email address
        - name: User's full name
        - preferred_username: User's preferred username
        - groups: List of groups/roles the user belongs to

        Args:
            claims: Dictionary of claims from the identity token
            db: Database session for user lookup/creation

        Returns:
            User object (either existing or newly created)

        Raises:
            NotImplementedError: If called on an implementation without JIT support
            HTTPException: If required claims are missing or user creation fails
        """
        msg = f"{self.__class__.__name__} does not support JIT provisioning. Override get_or_create_user_from_claims."
        raise NotImplementedError(msg)

    def extract_user_info_from_claims(self, claims: dict) -> dict:  # noqa: ARG002
        """Extract user information from identity provider claims.

        Helper method to normalize claims from different identity providers
        into a consistent format for user creation.

        The default implementation returns an empty dict. Override this in
        OIDC/SAML implementations to map provider-specific claims to user fields.

        Args:
            claims: Raw claims dictionary from the identity provider

        Returns:
            Dict with normalized user fields:
            - username: str (required)
            - email: str | None
            - is_active: bool (default True for JIT-provisioned users)
            - is_superuser: bool (default False)
        """
        return {}
