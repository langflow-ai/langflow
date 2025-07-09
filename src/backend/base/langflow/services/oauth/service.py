from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request, status
from loguru import logger
from starlette.config import Config

from langflow.services.base import Service
from langflow.services.database.models.user.crud import get_user_by_email, get_user_by_oauth_id
from langflow.services.database.models.user.model import User

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.settings.service import SettingsService

# HTTP status codes
HTTP_OK = 200
HTTP_FORBIDDEN = 403

# Username constants
MIN_USERNAME_LENGTH = 3

# OAuth provider configurations
GOOGLE_CONFIG = {
    "name": "google",
    "client_kwargs": {
        "scope": "openid email profile",
    },
    "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
}

MICROSOFT_CONFIG = {
    "name": "microsoft",
    "client_kwargs": {
        "scope": "openid email profile",
    },
    "server_metadata_url": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
}


class OAuthService(Service):
    name = "oauth_service"

    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.settings_service = settings_service
        self.oauth = None
        self._initialize_oauth()

    def _initialize_oauth(self):
        """Initialize OAuth client if OAuth is enabled."""
        if not self.settings_service.auth_settings.ENABLE_OAUTH:
            return

        # Create config with OAuth settings
        config_data = {}

        # Configure Google OAuth
        if self.settings_service.auth_settings.GOOGLE_OAUTH_CLIENT_ID:
            google_secret = self.settings_service.auth_settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value()
            config_data.update(
                {
                    "GOOGLE_CLIENT_ID": self.settings_service.auth_settings.GOOGLE_OAUTH_CLIENT_ID,
                    "GOOGLE_CLIENT_SECRET": google_secret,
                }
            )

        # Configure Microsoft OAuth
        if self.settings_service.auth_settings.MICROSOFT_OAUTH_CLIENT_ID:
            microsoft_secret = self.settings_service.auth_settings.MICROSOFT_OAUTH_CLIENT_SECRET.get_secret_value()
            config_data.update(
                {
                    "MICROSOFT_CLIENT_ID": self.settings_service.auth_settings.MICROSOFT_OAUTH_CLIENT_ID,
                    "MICROSOFT_CLIENT_SECRET": microsoft_secret,
                }
            )

        config = Config(environ=config_data)

        self.oauth = OAuth(config)

        # Register Google OAuth
        if self.settings_service.auth_settings.GOOGLE_OAUTH_CLIENT_ID:
            self.oauth.register(**GOOGLE_CONFIG)

        # Register Microsoft OAuth
        if self.settings_service.auth_settings.MICROSOFT_OAUTH_CLIENT_ID:
            microsoft_config = MICROSOFT_CONFIG.copy()
            if self.settings_service.auth_settings.MICROSOFT_OAUTH_TENANT_ID:
                # Use specific tenant instead of common
                tenant_id = self.settings_service.auth_settings.MICROSOFT_OAUTH_TENANT_ID
                microsoft_config["server_metadata_url"] = (
                    f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
                )
            self.oauth.register(**microsoft_config)

    def is_oauth_enabled(self) -> bool:
        """Check if OAuth is enabled and configured."""
        return self.settings_service.auth_settings.ENABLE_OAUTH and bool(
            self.settings_service.auth_settings.GOOGLE_OAUTH_CLIENT_ID
            or self.settings_service.auth_settings.MICROSOFT_OAUTH_CLIENT_ID
        )

    def get_oauth_providers(self) -> list[str]:
        """Get list of available OAuth providers."""
        providers = []
        if self.settings_service.auth_settings.GOOGLE_OAUTH_CLIENT_ID:
            providers.append("google")
        if self.settings_service.auth_settings.MICROSOFT_OAUTH_CLIENT_ID:
            providers.append("microsoft")
        return providers

    async def get_authorization_url(self, provider: str, request: Request) -> str:
        """Get authorization URL for the specified OAuth provider."""
        if not self.is_oauth_enabled():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth is not enabled")

        if not self.oauth:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="OAuth client not initialized"
            )

        if provider not in self.get_oauth_providers():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth provider '{provider}' not configured"
            )

        # Generate state parameter for CSRF protection
        state = secrets.token_urlsafe(32)
        request.session["oauth_state"] = state

        redirect_uri = self._get_redirect_uri(provider)

        return await self.oauth.create_client(provider).authorize_redirect(request, redirect_uri, state=state)

    async def handle_oauth_callback(
        self, provider: str, request: Request, db: AsyncSession, create_user_tokens_func: Callable
    ) -> dict:
        """Handle OAuth callback and authenticate user."""
        if not self.is_oauth_enabled() or not self.oauth:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth is not enabled")

        # Verify state parameter
        state = request.session.get("oauth_state")
        if not state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state - session may have expired"
            )

        try:
            # Get token and user info
            token = await self.oauth.create_client(provider).authorize_access_token(request)
            user_info = await self._get_user_info(provider, token)

            # Find or create user
            user = await self._get_or_create_user(db, provider, user_info)

            # Create tokens
            tokens = await create_user_tokens_func(user_id=user.id, db=db, update_last_login=True)

            # Clear OAuth state
            request.session.pop("oauth_state", None)

        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except (ValueError, RuntimeError, KeyError) as e:
            logger.error(f"OAuth callback error for {provider}: {e!s}")
            # Provide more specific error messages based on the exception type
            if "authorize_access_token" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth token exchange failed: {e!s}"
                ) from e
            if "user info" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to get user info from {provider}: {e!s}"
                ) from e
            if "database" in str(e).lower() or "user" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"User creation/retrieval failed: {e!s}"
                ) from e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"OAuth authentication failed: {e!s}"
            ) from e
        else:
            return tokens

    async def _get_user_info(self, provider: str, token: dict) -> dict:
        """Get user information from OAuth provider."""
        async with httpx.AsyncClient() as client:
            if provider == "google":
                resp = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {token['access_token']}"},
                )
            elif provider == "microsoft":
                # Try Microsoft Graph first, fall back to OpenID Connect
                resp = await client.get(
                    "https://graph.microsoft.com/v1.0/me", headers={"Authorization": f"Bearer {token['access_token']}"}
                )

                if resp.status_code == HTTP_FORBIDDEN:
                    # Fall back to OpenID Connect user info endpoint
                    resp = await client.get(
                        "https://graph.microsoft.com/oidc/userinfo",
                        headers={"Authorization": f"Bearer {token['access_token']}"},
                    )
            else:
                error_msg = f"Unsupported OAuth provider: {provider}"
                raise ValueError(error_msg)

            if resp.status_code != HTTP_OK:
                error_detail = f"Failed to get user info from {provider} (HTTP {resp.status_code})"
                try:
                    error_data = resp.json()
                    if "error" in error_data:
                        error_detail += f": {error_data['error'].get('message', 'Unknown error')}"
                except (ValueError, KeyError):
                    error_detail += f": {resp.text[:200]}"

                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)

            user_data = resp.json()

            # Normalize user data
            if provider == "google":
                return {
                    "id": user_data["id"],
                    "email": user_data["email"],
                    "name": user_data.get("name", ""),
                    "picture": user_data.get("picture"),
                }
            if provider == "microsoft":
                # Handle both Microsoft Graph API and OpenID Connect responses
                # Microsoft Graph API returns "id", OpenID Connect returns "sub"
                user_id = user_data.get("id") or user_data.get("sub")
                if not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="No user ID found in Microsoft OAuth response"
                    )

                return {
                    "id": user_id,
                    "email": user_data.get("mail") or user_data.get("userPrincipalName") or user_data.get("email"),
                    "name": user_data.get("displayName") or user_data.get("name", ""),
                    "picture": None,  # Microsoft Graph doesn't provide profile picture by default
                }
        return {}

    async def _get_or_create_user(self, db: AsyncSession, provider: str, user_info: dict) -> User:
        """Get existing user or create new one from OAuth data."""
        # Try to find user by OAuth ID first
        user = await get_user_by_oauth_id(db, provider, user_info["id"])
        if user:
            return user

        # Try to find user by email
        if user_info["email"]:
            user = await get_user_by_email(db, user_info["email"])
            if user:
                # Update existing user with OAuth info
                user.oauth_provider = provider
                user.oauth_id = user_info["id"]
                user.oauth_email = user_info["email"]
                await db.commit()
                await db.refresh(user)
                return user

        # Create new user if auto-creation is enabled
        if not self.settings_service.auth_settings.OAUTH_AUTO_CREATE_USERS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User not found and auto-creation is disabled"
            )

        # Generate username from email or name
        username = self._generate_username(user_info["email"], user_info["name"])

        user = User(
            username=username,
            email=user_info["email"],
            password="",  # OAuth users don't have passwords
            profile_image=user_info.get("picture"),
            is_active=self.settings_service.auth_settings.OAUTH_DEFAULT_IS_ACTIVE,
            is_superuser=self.settings_service.auth_settings.OAUTH_DEFAULT_IS_SUPERUSER,
            oauth_provider=provider,
            oauth_id=user_info["id"],
            oauth_email=user_info["email"],
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(f"Created new OAuth user: {user.username} ({provider})")
        return user

    def _generate_username(self, email: str, name: str) -> str:
        """Generate a unique username from email or name."""
        username = email.split("@")[0] if email else name.lower().replace(" ", "_")

        # Ensure username is valid (alphanumeric and underscores only)
        username = "".join(c for c in username if c.isalnum() or c == "_")

        # Add random suffix if needed to ensure uniqueness
        if len(username) < MIN_USERNAME_LENGTH:
            username += "_" + secrets.token_hex(3)

        return username

    def _get_redirect_uri(self, provider: str) -> str:
        """Get redirect URI for the specified provider."""
        if provider == "google":
            return self.settings_service.auth_settings.GOOGLE_OAUTH_REDIRECT_URI
        if provider == "microsoft":
            return self.settings_service.auth_settings.MICROSOFT_OAUTH_REDIRECT_URI
        error_msg = f"Unsupported OAuth provider: {provider}"
        raise ValueError(error_msg)
