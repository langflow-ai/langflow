"""OIDC Authentication Service.

This module implements OpenID Connect (OIDC) authentication for Langflow.
It supports any OIDC-compliant identity provider (W3ID, Okta, Azure AD, Google, etc.).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

import httpx
import jwt
from fastapi import HTTPException, Request, status
from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError

from langflow.services.auth.base import AuthServiceBase
from langflow.services.auth.service import AuthService
from langflow.services.auth.sso_config import OIDCConfig
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.settings.service import SettingsService


class OIDCAuthService(AuthServiceBase):
    """OIDC authentication service.

    This service handles authentication via OpenID Connect providers.
    It supports:
    - OIDC discovery for automatic endpoint configuration
    - JWT token validation
    - Just-In-Time (JIT) user provisioning
    - Custom claim mapping
    """

    name = ServiceType.AUTH_SERVICE.value

    def __init__(self, settings_service: SettingsService, oidc_config: OIDCConfig):
        """Initialize OIDC auth service.

        Args:
            settings_service: Settings service instance
            oidc_config: OIDC provider configuration
        """
        self.settings_service = settings_service
        self.oidc_config = oidc_config
        self._discovery_cache: dict | None = None
        self._jwks_cache: dict | None = None

        # Delegate to base AuthService for non-OIDC operations
        self._base_auth = AuthService(settings_service)

        self.set_ready()

    @property
    def settings(self) -> SettingsService:
        return self.settings_service

    # =========================================================================
    # OIDC-Specific Methods
    # =========================================================================

    async def get_oidc_discovery(self) -> dict:
        """Fetch OIDC discovery document from IdP.

        Returns:
            Discovery document with endpoints and configuration

        Raises:
            HTTPException: If discovery fails
        """
        if self._discovery_cache is not None:
            return self._discovery_cache

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.oidc_config.discovery_url, timeout=10.0)
                response.raise_for_status()
                self._discovery_cache = response.json()
                logger.info(f"OIDC discovery successful for {self.oidc_config.provider_name}")
                return self._discovery_cache
        except Exception as e:
            logger.error(f"OIDC discovery failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to connect to identity provider: {e}",
            ) from e

    async def get_authorization_url(self, state: str) -> str:
        """Generate OIDC authorization URL for login redirect.

        Args:
            state: CSRF protection state parameter

        Returns:
            Authorization URL to redirect user to
        """
        discovery = await self.get_oidc_discovery()
        auth_endpoint = self.oidc_config.authorization_endpoint or discovery.get("authorization_endpoint")

        if not auth_endpoint:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authorization endpoint not configured",
            )

        # Build authorization URL
        params = {
            "client_id": self.oidc_config.client_id,
            "response_type": "code",
            "scope": " ".join(self.oidc_config.scopes),
            "redirect_uri": self.oidc_config.redirect_uri,
            "state": state,
        }

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{auth_endpoint}?{query_string}"

    async def exchange_code_for_tokens(self, code: str) -> dict:
        """Exchange authorization code for access and ID tokens.

        Args:
            code: Authorization code from IdP callback

        Returns:
            Token response with access_token, id_token, etc.

        Raises:
            HTTPException: If token exchange fails
        """
        discovery = await self.get_oidc_discovery()
        token_endpoint = self.oidc_config.token_endpoint or discovery.get("token_endpoint")

        if not token_endpoint:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token endpoint not configured",
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.oidc_config.redirect_uri,
                        "client_id": self.oidc_config.client_id,
                        "client_secret": self.oidc_config.client_secret,
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Failed to exchange authorization code: {e}",
            ) from e

    async def validate_id_token(self, id_token: str) -> dict:
        """Validate and decode OIDC ID token.

        Args:
            id_token: JWT ID token from IdP

        Returns:
            Decoded token claims

        Raises:
            HTTPException: If token validation fails
        """
        try:
            # For POC, we'll do basic validation
            # Production should verify signature with JWKS
            decoded = jwt.decode(
                id_token,
                options={"verify_signature": False},  # TODO: Implement JWKS verification
            )

            # Validate issuer if configured
            if self.oidc_config.issuer and decoded.get("iss") != self.oidc_config.issuer:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token issuer",
                )

            # Validate expiration
            exp = decoded.get("exp")
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                )

            return decoded
        except jwt.InvalidTokenError as e:
            logger.error(f"Token validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid ID token: {e}",
            ) from e

    # =========================================================================
    # JIT User Provisioning
    # =========================================================================

    async def get_or_create_user_from_claims(self, claims: dict, db: AsyncSession) -> User:
        """Get or create user from OIDC claims (JIT provisioning).

        Args:
            claims: ID token claims from IdP
            db: Database session

        Returns:
            User object (existing or newly created)
        """
        # Extract user info from claims
        sso_user_id = claims.get(self.oidc_config.user_id_claim)
        email = claims.get(self.oidc_config.email_claim)
        username = claims.get(self.oidc_config.username_claim) or email

        if not sso_user_id or not email or not username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required claims: {self.oidc_config.user_id_claim} or {self.oidc_config.email_claim}",
            )

        # Try to find existing user by SSO user ID
        from sqlmodel import select

        statement = select(User).where(
            User.sso_provider == "oidc",
            User.sso_user_id == sso_user_id,
        )
        result = await db.exec(statement)
        user = result.first()

        if user:
            # Update last SSO login
            user.sso_last_login_at = datetime.now(timezone.utc)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Existing SSO user logged in: {username}")
            return user

        # Create new user (JIT provisioning)
        try:
            new_user = User(
                username=username,
                email=email,
                password=secrets.token_urlsafe(32),  # Random password (not used for SSO)
                is_active=True,
                is_superuser=False,
                sso_provider="oidc",
                sso_user_id=sso_user_id,
                sso_last_login_at=datetime.now(timezone.utc),
                optins={},  # Empty optins for SSO users
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            logger.info(f"New SSO user provisioned: {username}")
            return new_user
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Failed to create SSO user: {e}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email or username already exists",
            ) from e

    # =========================================================================
    # AuthServiceBase Implementation (Required Methods)
    # =========================================================================

    async def get_current_user(
        self,
        token: str | Coroutine | None,
        query_param: str | None,
        header_param: str | None,
        db: AsyncSession,
    ) -> User | UserRead:
        """Get current user from OIDC token or API key."""
        if token:
            return await self.get_current_user_from_access_token(token, db)
        # Fall back to API key auth
        return await self._base_auth.get_current_user(token, query_param, header_param, db)

    async def get_current_user_from_access_token(
        self,
        token: str | Coroutine | None,
        db: AsyncSession,
    ) -> User | UserRead:
        """Get user from OIDC ID token."""
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
            )

        if isinstance(token, Coroutine):
            token = await token

        if not isinstance(token, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        # Validate and decode ID token
        claims = await self.validate_id_token(token)

        # Get or create user from claims (JIT provisioning)
        user = await self.get_or_create_user_from_claims(claims, db)
        return user

    # Delegate remaining methods to base AuthService
    async def get_current_user_for_websocket(
        self, token: str | None, api_key: str | None, db: AsyncSession
    ) -> User | UserRead:
        return await self._base_auth.get_current_user_for_websocket(token, api_key, db)

    async def authenticate_user(self, username: str, password: str, db: AsyncSession) -> User | None:
        # OIDC doesn't use password authentication
        # Check if SSO enforcement is enabled via settings
        if self.settings_service.auth_settings.SSO_ENABLED:
            # For now, allow password fallback unless explicitly disabled
            pass
        return await self._base_auth.authenticate_user(username, password, db)

    async def get_current_active_user(self, current_user: User | UserRead) -> User | UserRead:
        return await self._base_auth.get_current_active_user(current_user)

    async def get_current_active_superuser(self, current_user: User | UserRead) -> User | UserRead:
        return await self._base_auth.get_current_active_superuser(current_user)

    async def create_user_tokens(self, user_id: UUID, db: AsyncSession, *, update_last_login: bool = False) -> dict:
        return await self._base_auth.create_user_tokens(user_id, db, update_last_login=update_last_login)

    async def create_refresh_token(self, refresh_token: str, db: AsyncSession) -> dict:
        return await self._base_auth.create_refresh_token(refresh_token, db)

    async def api_key_security(
        self, query_param: str | None, header_param: str | None, db: AsyncSession | None = None
    ) -> UserRead | None:
        return await self._base_auth.api_key_security(query_param, header_param, db)

    async def ws_api_key_security(self, api_key: str | None) -> UserRead:
        return await self._base_auth.ws_api_key_security(api_key)

    async def get_webhook_user(self, flow_id: str, request: Request) -> UserRead:
        return await self._base_auth.get_webhook_user(flow_id, request)

    async def create_super_user(self, username: str, password: str, db: AsyncSession) -> User:
        return await self._base_auth.create_super_user(username, password, db)

    async def create_user_longterm_token(self, db: AsyncSession) -> tuple[UUID, dict]:
        return await self._base_auth.create_user_longterm_token(db)

    def create_user_api_key(self, user_id: UUID) -> dict:
        return self._base_auth.create_user_api_key(user_id)

    def encrypt_api_key(self, api_key: str) -> str:
        return self._base_auth.encrypt_api_key(api_key)

    def decrypt_api_key(self, encrypted_api_key: str) -> str:
        return self._base_auth.decrypt_api_key(encrypted_api_key)

    async def get_current_user_mcp(
        self, token: str | Coroutine | None, query_param: str | None, header_param: str | None, db: AsyncSession
    ) -> User | UserRead:
        return await self._base_auth.get_current_user_mcp(token, query_param, header_param, db)

    async def get_current_active_user_mcp(self, current_user: User | UserRead) -> User | UserRead:
        return await self._base_auth.get_current_active_user_mcp(current_user)

    def create_token(self, data: dict, expires_delta: timedelta) -> str:
        return self._base_auth.create_token(data, expires_delta)

    def get_user_id_from_token(self, token: str) -> UUID:
        return self._base_auth.get_user_id_from_token(token)
