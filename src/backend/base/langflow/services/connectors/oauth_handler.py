"""OAuth 2.0 handler for connector authentication."""

import hashlib
import secrets
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from lfx.log import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.connector import (
    get_connection,
    update_connection,
)

from .encryption import encrypt_sensitive_field


class OAuthHandler:
    """Handles OAuth 2.0 flow for connectors."""

    # OAuth configuration for different providers
    OAUTH_CONFIGS = {
        "google_drive": {
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": [
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/drive.metadata.readonly",
            ],
        },
        "onedrive": {
            "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "scopes": ["Files.Read", "Files.Read.All", "Sites.Read.All"],
        },
    }

    def __init__(self, connector_type: str, client_id: str, client_secret: str, redirect_uri: str):
        """Initialize OAuth handler.

        Args:
            connector_type: Type of connector (google_drive, onedrive, etc.)
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Redirect URI for OAuth callback
        """
        self.connector_type = connector_type
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.config = self.OAUTH_CONFIGS.get(connector_type, {})

    def generate_auth_url(self, connection_id: UUID, user_id: UUID) -> tuple[str, str]:
        """Generate OAuth authorization URL.

        Args:
            connection_id: Connection ID for state tracking
            user_id: User ID for state tracking

        Returns:
            Tuple of (authorization URL, state token)
        """
        # Generate secure state token
        state_data = f"{connection_id}:{user_id}:{secrets.token_urlsafe(32)}"
        state = hashlib.sha256(state_data.encode()).hexdigest()

        if self.connector_type == "google_drive":
            # Use Google's OAuth library
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": self.config["auth_uri"],
                        "token_uri": self.config["token_uri"],
                    }
                },
                scopes=self.config["scopes"],
                state=state,
            )
            flow.redirect_uri = self.redirect_uri

            auth_url, _ = flow.authorization_url(
                access_type="offline",  # Request refresh token
                include_granted_scopes="true",
                prompt="consent",  # Force consent to get refresh token
            )

            return auth_url, state

        if self.connector_type == "onedrive":
            # Build Microsoft OAuth URL
            params = {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "scope": " ".join(self.config["scopes"]),
                "state": state,
                "access_type": "offline",
            }
            auth_url = f"{self.config['auth_uri']}?{urlencode(params)}"
            return auth_url, state

        msg = f"OAuth not configured for {self.connector_type}"
        raise ValueError(msg)

    async def handle_callback(
        self,
        session: AsyncSession,
        connection_id: UUID,
        code: str,
        state: str,
    ) -> dict[str, Any]:
        """Handle OAuth callback and exchange code for tokens.

        Args:
            session: Database session
            connection_id: Connection ID
            code: Authorization code from OAuth provider
            state: State token for verification

        Returns:
            Token data dictionary
        """
        try:
            if self.connector_type == "google_drive":
                # Exchange code for tokens using Google's library
                flow = Flow.from_client_config(
                    {
                        "web": {
                            "client_id": self.client_id,
                            "client_secret": self.client_secret,
                            "auth_uri": self.config["auth_uri"],
                            "token_uri": self.config["token_uri"],
                        }
                    },
                    scopes=self.config["scopes"],
                    state=state,
                )
                flow.redirect_uri = self.redirect_uri

                # Exchange authorization code for tokens
                flow.fetch_token(code=code)

                credentials = flow.credentials
                token_data = {
                    "access_token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                    "token_uri": credentials.token_uri,
                    "client_id": credentials.client_id,
                    "client_secret": credentials.client_secret,
                    "scopes": credentials.scopes,
                    "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
                }

                # Store tokens in database (encrypted)
                await self._store_tokens(session, connection_id, token_data)

                return token_data

            if self.connector_type == "onedrive":
                # Exchange code for tokens using Microsoft's endpoint
                import aiohttp

                token_url = self.config["token_uri"]
                data = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                }

                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(token_url, data=data) as response:
                        if response.status == 200:
                            token_response = await response.json()
                            token_data = {
                                "access_token": token_response["access_token"],
                                "refresh_token": token_response.get("refresh_token"),
                                "expires_in": token_response.get("expires_in"),
                                "scope": token_response.get("scope"),
                            }

                            # Store tokens
                            await self._store_tokens(session, connection_id, token_data)
                            return token_data
                        error = await response.text()
                        msg = f"Token exchange failed: {error}"
                        raise RuntimeError(msg)

            else:
                msg = f"OAuth not configured for {self.connector_type}"
                raise ValueError(msg)

        except Exception as e:
            logger.error(f"OAuth callback failed for connection {connection_id}: {e}")
            raise

    async def refresh_token(
        self,
        session: AsyncSession,
        connection_id: UUID,
        refresh_token: str,
    ) -> dict[str, Any]:
        """Refresh an expired access token.

        Args:
            session: Database session
            connection_id: Connection ID
            refresh_token: Refresh token

        Returns:
            Updated token data
        """
        try:
            if self.connector_type == "google_drive":
                # Use Google's library to refresh
                credentials = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri=self.config["token_uri"],
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                )

                # Refresh the token
                credentials.refresh(Request())

                token_data = {
                    "access_token": credentials.token,
                    "refresh_token": credentials.refresh_token or refresh_token,
                    "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
                }

                # Update stored tokens
                await self._store_tokens(session, connection_id, token_data)
                return token_data

            if self.connector_type == "onedrive":
                import aiohttp

                token_url = self.config["token_uri"]
                data = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }

                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(token_url, data=data) as response:
                        if response.status == 200:
                            token_response = await response.json()
                            token_data = {
                                "access_token": token_response["access_token"],
                                "refresh_token": token_response.get("refresh_token", refresh_token),
                                "expires_in": token_response.get("expires_in"),
                            }

                            # Update stored tokens
                            await self._store_tokens(session, connection_id, token_data)
                            return token_data
                        error = await response.text()
                        msg = f"Token refresh failed: {error}"
                        raise RuntimeError(msg)

            else:
                msg = f"OAuth not configured for {self.connector_type}"
                raise ValueError(msg)

        except Exception as e:
            logger.error(f"Token refresh failed for connection {connection_id}: {e}")
            raise

    async def _store_tokens(
        self,
        session: AsyncSession,
        connection_id: UUID,
        token_data: dict[str, Any],
    ):
        """Store OAuth tokens securely in the database.

        Args:
            session: Database session
            connection_id: Connection ID
            token_data: Token data to store
        """
        # Get the connection
        connection = await get_connection(session, connection_id)
        if not connection:
            msg = f"Connection {connection_id} not found"
            raise ValueError(msg)

        # Update connection config with encrypted tokens
        # Create a NEW dict to ensure SQLAlchemy detects the change
        config = dict(connection.config or {})

        # Encrypt sensitive data
        if "access_token" in token_data:
            config["access_token"] = encrypt_sensitive_field(token_data["access_token"])
            logger.debug(f"Encrypted access_token for {connection_id}")
        if "refresh_token" in token_data:
            config["refresh_token"] = encrypt_sensitive_field(token_data["refresh_token"])
            logger.debug(f"Encrypted refresh_token for {connection_id}")
        if "client_secret" in token_data:
            config["client_secret"] = encrypt_sensitive_field(token_data["client_secret"])

        # Store non-sensitive data as-is
        for key in ["token_uri", "client_id", "scopes", "expiry", "expires_in", "scope"]:
            if key in token_data:
                config[key] = token_data[key]

        logger.debug(f"Config keys before update: {list(config.keys())}")

        # Update the connection with the NEW config dict
        update_data = {"config": config}
        result = await update_connection(session, connection_id, connection.user_id, update_data)

        if result:
            logger.debug(f"update_connection returned: config keys = {list(result.config.keys())}")
        else:
            logger.error(f"update_connection returned None for {connection_id}")

        logger.info(f"OAuth tokens stored for connection {connection_id}")

    async def revoke_tokens(
        self,
        session: AsyncSession,
        connection_id: UUID,
        access_token: str,
    ) -> bool:
        """Revoke OAuth tokens.

        Args:
            session: Database session
            connection_id: Connection ID
            access_token: Access token to revoke

        Returns:
            True if revocation successful
        """
        try:
            if self.connector_type == "google_drive":
                import aiohttp

                revoke_url = "https://oauth2.googleapis.com/revoke"
                params = {"token": access_token}

                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(revoke_url, params=params) as response:
                        success = response.status == 200
                        if success:
                            # Clear tokens from database
                            connection = await get_connection(session, connection_id)
                            if connection:
                                config = connection.config or {}
                                config.pop("access_token", None)
                                config.pop("refresh_token", None)
                                update_data = {"config": config, "is_authenticated": False}
                                await update_connection(
                                    session, connection_id, connection.user_id, update_data
                                )
                        return success

            elif self.connector_type == "onedrive":
                # Microsoft doesn't have a revoke endpoint, just clear tokens
                connection = await get_connection(session, connection_id)
                if connection:
                    config = connection.config or {}
                    config.pop("access_token", None)
                    config.pop("refresh_token", None)
                    update_data = {"config": config, "is_authenticated": False}
                    await update_connection(session, connection_id, connection.user_id, update_data)
                return True

            else:
                return False

        except Exception as e:
            logger.error(f"Token revocation failed for connection {connection_id}: {e}")
            return False
