"""Keycloak Authentication API Router.

This module provides API endpoints for Keycloak integration with Langflow,
including configuration retrieval, authentication callback handling,
and token refreshing.

Routes:
    - GET /keycloak/config: Retrieve Keycloak configuration for frontend
    - GET /keycloak/callback: Handle OAuth callback after Keycloak authentication
"""

from __future__ import annotations

from typing import Annotated

from cachetools import LRUCache, cached
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from loguru import logger
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.v1.schemas import Token
from langflow.services.deps import get_keycloak_service, get_session
from langflow.services.keycloak.service import KeycloakService
from langflow.services.keycloak.utils import process_keycloak_login

# Create a FastAPI router for Keycloak-related endpoints
router = APIRouter(tags=["Keycloak"])


class KeycloakConfig(BaseModel):
    """Keycloak configuration model for the frontend.

    Contains all necessary parameters for the frontend to integrate with Keycloak,
    following OpenID Connect standards. Field names use camelCase to match
    frontend JavaScript conventions.
    """

    # Whether Keycloak authentication is enabled
    enabled: bool
    # Base URL of the Keycloak server (e.g., "https://auth.example.com/auth")
    serverUrl: str  # noqa: N815
    # Keycloak realm name
    realm: str
    # Client ID registered in Keycloak
    clientId: str  # noqa: N815
    # URI where Keycloak will redirect after authentication
    redirectUri: str  # noqa: N815
    # Whether to force SSO-only login (hide username/password form)
    forceSSO: bool = False  # noqa: N815


# Cache the Keycloak configuration
@cached(cache=LRUCache(maxsize=1))
def get_cached_keycloak_config(service: KeycloakService) -> KeycloakConfig | dict[str, bool]:
    """A cacheable function that creates and returns the Keycloak configuration.

    This is separated from the route handler to allow for LRU caching without
    risking memory leaks. The function only depends on its arguments, not on
    any class instance.

    Args:
        service: KeycloakService instance injected by FastAPI

    Returns:
        Either a KeycloakConfig object or a dict with {'enabled': False}
    """
    if not service.is_enabled:
        return {"enabled": False}

    return KeycloakConfig(
        enabled=True,
        serverUrl=service.server_url,
        realm=service.realm,
        clientId=service.client_id,
        redirectUri=service.redirect_uri,
        forceSSO=service.force_sso,
    )


@router.get("/keycloak/config", response_model=KeycloakConfig | dict[str, bool])
async def get_keycloak_config(
    keycloak_service: Annotated[KeycloakService, Depends(get_keycloak_service)],
) -> KeycloakConfig | dict[str, bool]:
    """Get Keycloak configuration for the frontend.

    Uses a cached function to generate the configuration object to avoid
    unnecessary computation and database lookups on frequently requested data.

    Args:
        keycloak_service: KeycloakService instance injected by FastAPI

    Returns:
        - When Keycloak is enabled: A KeycloakConfig object with all configuration parameters
        - When Keycloak is disabled: A simple dict with {"enabled": False}
    """
    # Use the cached function to get the configuration
    # This separates the caching from the instance method to avoid memory leaks
    return get_cached_keycloak_config(keycloak_service)


@router.get("/keycloak/callback", response_model=Token)
async def keycloak_callback(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    code: Annotated[str, Query(description="Authorization code")],
    nonce: Annotated[str, Query(description="Client-generated nonce")],
    keycloak_service: Annotated[KeycloakService, Depends(get_keycloak_service)],
) -> Token:
    """Handle Keycloak authentication callback after successful SSO authentication.

    This endpoint is called by the frontend when the user is redirected back from Keycloak
    with an authorization code. It exchanges the code for tokens, creates or updates the user
    in the database, and returns access/refresh tokens for the frontend.

    Args:
        response: FastAPI Response object for setting cookies
        db: Database session for accessing user data
        code: Authorization code received from Keycloak redirect
        nonce: Client-generated nonce for security
        keycloak_service: KeycloakService instance injected by FastAPI

    Returns:
        Token: Object containing the LangFlow access_token and refresh_token

    Raises:
        HTTPException: If Keycloak is not enabled or authentication fails
    """
    # Log the received authorization code (truncated for security)
    logger.debug(f"Received auth code: {code[:10]}...")

    if not keycloak_service.is_enabled:
        logger.error("Attempted Keycloak callback but Keycloak is not enabled")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keycloak is disabled",
        )

    # Process Keycloak login and get tokens using redirect URI from service
    return await process_keycloak_login(code, nonce, keycloak_service.redirect_uri, response, db, keycloak_service)
