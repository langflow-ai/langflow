"""LangFlow Authentication API (Login, Logout, Refresh Tokens).

This module provides authentication endpoints for logging in, refreshing access tokens,
and logging out. It supports both LangFlow's native authentication and Keycloak integration.

Key Features:
- Login via username/password (LangFlow auth)
- Auto-login support
- Refresh tokens (both LangFlow and Keycloak)
- Logout and Keycloak session termination
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import DbSession
from langflow.api.v1.schemas import Token
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.auth.constants import (
    COOKIE_ACCESS_TOKEN,
    COOKIE_API_KEY,
    COOKIE_KEYCLOAK_REFRESH_TOKEN,
    COOKIE_REFRESH_TOKEN,
)
from langflow.services.auth.utils import (
    authenticate_user,
    create_refresh_token,
    create_user_longterm_token,
    create_user_tokens,
)
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_keycloak_service, get_settings_service, get_variable_service
from langflow.services.keycloak.service import KeycloakService
from langflow.services.settings.auth import AuthSettings

router = APIRouter(tags=["Login"])


@router.post("/login", response_model=Token)
async def login_to_get_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
):
    """Handles user login and returns access/refresh tokens."""
    auth_settings = get_settings_service().auth_settings
    try:
        user = await authenticate_user(form_data.username, form_data.password, db)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    if user:
        return await create_and_set_user_tokens(response, db, auth_settings, user)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/auto_login", response_model=dict)
async def auto_login(response: Response, db: DbSession) -> dict:
    """Automatically log in a user when AUTO_LOGIN is enabled.

    Returns:
        - When AUTO_LOGIN is enabled: A dictionary with access_token and token_type
        - When AUTO_LOGIN is disabled: Dictionary with a message indicating auto login is disabled

    Note:
        The frontend checks for the presence of access_token in the response to determine
        if auto login succeeded. When auto login is disabled, we return an empty dictionary
        which the frontend will interpret correctly (setting autoLogin to false).
    """
    auth_settings = get_settings_service().auth_settings

    if not auth_settings.AUTO_LOGIN:
        logger.debug("Auto login is disabled")
        # Return a response that the frontend can safely handle
        return {"message": "Auto login is disabled. Please enable it in the settings", "auto_login": False}

    try:
        logger.debug("Auto login is enabled, creating token")
        user_id, tokens = await create_user_longterm_token(db)

        # Set access token cookie
        response.set_cookie(
            COOKIE_ACCESS_TOKEN,
            tokens["access_token"],
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=None,  # Set to None to make it a session cookie
            domain=auth_settings.COOKIE_DOMAIN,
        )

        # Get user and set API key cookie if available
        user = await get_user_by_id(db, user_id)
        if user:
            api_key = "" if user.store_api_key is None else str(user.store_api_key)

            response.set_cookie(
                COOKIE_API_KEY,
                api_key,
                httponly=auth_settings.ACCESS_HTTPONLY,
                samesite=auth_settings.ACCESS_SAME_SITE,
                secure=auth_settings.ACCESS_SECURE,
                expires=None,  # Set to None to make it a session cookie
                domain=auth_settings.COOKIE_DOMAIN,
            )

        logger.debug(f"Auto login successful for user_id: {user_id}")
    except HTTPException as e:
        logger.error(f"Error during auto login: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Error during auto login.",
                "auto_login": False,
            },
        ) from e
    else:
        return tokens


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: DbSession,
):
    """Refreshes access tokens, also refreshing Keycloak tokens if enabled."""
    auth_settings = get_settings_service().auth_settings
    keycloak_service = get_keycloak_service()

    app_refresh_token = request.cookies.get(COOKIE_REFRESH_TOKEN)

    if not app_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid LangFlow refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tokens = await create_refresh_token(app_refresh_token, db)

    # Set LangFlow access and refresh tokens in cookies
    response.set_cookie(
        COOKIE_REFRESH_TOKEN,
        tokens["refresh_token"],
        httponly=auth_settings.REFRESH_HTTPONLY,
        samesite=auth_settings.REFRESH_SAME_SITE,
        secure=auth_settings.REFRESH_SECURE,
        expires=auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS,
        domain=auth_settings.COOKIE_DOMAIN,
    )
    response.set_cookie(
        COOKIE_ACCESS_TOKEN,
        tokens["access_token"],
        httponly=auth_settings.ACCESS_HTTPONLY,
        samesite=auth_settings.ACCESS_SAME_SITE,
        secure=auth_settings.ACCESS_SECURE,
        expires=auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        domain=auth_settings.COOKIE_DOMAIN,
    )

    if keycloak_service.is_enabled:
        keycloak_refresh_token = request.cookies.get(COOKIE_KEYCLOAK_REFRESH_TOKEN)

        if keycloak_refresh_token:
            try:
                keycloak_tokens = await keycloak_service.refresh_token(keycloak_refresh_token)

                # Store updated Keycloak refresh token in a cookie
                response.set_cookie(
                    COOKIE_KEYCLOAK_REFRESH_TOKEN,
                    keycloak_tokens["refresh_token"],
                    httponly=True,
                    samesite=auth_settings.REFRESH_SAME_SITE,
                    secure=auth_settings.REFRESH_SECURE,
                    expires=auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS,
                    domain=auth_settings.COOKIE_DOMAIN,
                )

            except Exception as e:
                logger.error(f"Keycloak token refresh failed: {e!s}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid LangFlow Keycloak refresh token",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from e

    return tokens


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logs out the user and invalidates Keycloak session."""
    keycloak_service = get_keycloak_service()

    # If Keycloak is enabled, attempt to log out the user
    if keycloak_service.is_enabled:
        await logout_from_keycloak(request, keycloak_service)

    # Delete all authentication-related cookies
    delete_cookies(response)
    return {"message": "Logout successful"}


async def logout_from_keycloak(request: Request, keycloak_service: KeycloakService) -> None:
    """Logs out the user from Keycloak by invalidating their session.

    Args:
        request (Request): FastAPI request object to extract cookies.
        keycloak_service (KeycloakService): Keycloak authentication service.
    """
    # Get refresh token from cookies
    refresh_token = request.cookies.get(COOKIE_KEYCLOAK_REFRESH_TOKEN)

    if refresh_token:
        try:
            await keycloak_service.logout(refresh_token)
            logger.info("Successfully logged out from Keycloak")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to log out from Keycloak: {e!s}")


def delete_cookies(response: Response) -> None:
    """Deletes all authentication-related cookies."""
    response.delete_cookie(COOKIE_REFRESH_TOKEN)
    response.delete_cookie(COOKIE_ACCESS_TOKEN)
    response.delete_cookie(COOKIE_API_KEY)
    response.delete_cookie(COOKIE_KEYCLOAK_REFRESH_TOKEN)


async def create_and_set_user_tokens(
    response: Response, db: AsyncSession, auth_settings: AuthSettings, user: User
) -> Token:
    """Generate JWT tokens for a user and set them as HTTP-only cookies.

    This function creates access and refresh tokens for the user, stores them in cookies,
    and initializes user-specific settings such as API keys and default folders.

    Args:
        response (Response): FastAPI response object used to set cookies.
        db (AsyncSession): Database session for persisting user-related data.
        auth_settings (AuthSettings): Authentication settings containing cookie configurations.
        user (User): The authenticated user for whom tokens are generated.

    Returns:
        Token: Object containing the LangFlow access_token and refresh_token
    """
    tokens = Token(**await create_user_tokens(user_id=user.id, db=db, update_last_login=True))
    response.set_cookie(
        COOKIE_REFRESH_TOKEN,
        tokens.refresh_token,
        httponly=auth_settings.REFRESH_HTTPONLY,
        samesite=auth_settings.REFRESH_SAME_SITE,
        secure=auth_settings.REFRESH_SECURE,
        expires=auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS,
        domain=auth_settings.COOKIE_DOMAIN,
    )
    response.set_cookie(
        COOKIE_ACCESS_TOKEN,
        tokens.access_token,
        httponly=auth_settings.ACCESS_HTTPONLY,
        samesite=auth_settings.ACCESS_SAME_SITE,
        secure=auth_settings.ACCESS_SECURE,
        expires=auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        domain=auth_settings.COOKIE_DOMAIN,
    )

    if user.store_api_key:
        response.set_cookie(
            COOKIE_API_KEY,
            str(user.store_api_key),
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=None,  # Set to None to make it a session cookie
            domain=auth_settings.COOKIE_DOMAIN,
        )
    await get_variable_service().initialize_user_variables(user.id, db)
    # Create default folder for user if it doesn't exist
    _ = await get_or_create_default_folder(db, user.id)
    return tokens
