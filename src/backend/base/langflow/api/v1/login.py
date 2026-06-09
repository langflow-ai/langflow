from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from langflow.api.utils import DbSession
from langflow.api.v1.schemas import Token
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_auth_service, get_settings_service, get_variable_service

router = APIRouter(tags=["Login"])


class SessionResponse(BaseModel):
    """Session validation response."""

    authenticated: bool
    user: UserRead | None = None
    store_api_key: str | None = None


@router.post("/login", response_model=Token, include_in_schema=False)
async def login_to_get_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
):
    auth_settings = get_settings_service().auth_settings
    try:
        auth = get_auth_service()
        user = await auth.authenticate_user(form_data.username, form_data.password, db)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        # Log the actual error server-side but don't expose it to clients
        from loguru import logger

        logger.error(f"Authentication error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during authentication",
        ) from exc

    if user:
        tokens = await auth.create_user_tokens(user_id=user.id, db=db, update_last_login=True)
        response.set_cookie(
            "refresh_token_lf",
            tokens["refresh_token"],
            httponly=auth_settings.REFRESH_HTTPONLY,
            samesite=auth_settings.REFRESH_SAME_SITE,
            secure=auth_settings.REFRESH_SECURE,
            expires=auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS,
            domain=auth_settings.COOKIE_DOMAIN,
        )
        response.set_cookie(
            "access_token_lf",
            tokens["access_token"],
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS,
            domain=auth_settings.COOKIE_DOMAIN,
        )
        response.set_cookie(
            "apikey_tkn_lflw",
            str(user.store_api_key),
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=None,  # Set to None to make it a session cookie
            domain=auth_settings.COOKIE_DOMAIN,
        )
        await get_variable_service().initialize_user_variables(user.id, db)
        # Initialize agentic variables if agentic experience is enabled
        from langflow.api.utils.mcp.agentic_mcp import initialize_agentic_user_variables

        # Create default project for user if it doesn't exist
        _ = await get_or_create_default_folder(db, user.id)

        if get_settings_service().settings.agentic_experience:
            await initialize_agentic_user_variables(user.id, db)

        return tokens
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/auto_login", include_in_schema=False)
async def auto_login(response: Response, db: DbSession):
    auth_settings = get_settings_service().auth_settings

    if auth_settings.AUTO_LOGIN:
        auth = get_auth_service()
        user_id, tokens = await auth.create_user_longterm_token(db)
        response.set_cookie(
            "access_token_lf",
            tokens["access_token"],
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=None,  # Set to None to make it a session cookie
            domain=auth_settings.COOKIE_DOMAIN,
        )

        user = await get_user_by_id(db, user_id)

        if user:
            if user.store_api_key is None:
                user.store_api_key = ""

            response.set_cookie(
                "apikey_tkn_lflw",
                str(user.store_api_key),  # Ensure it's a string
                httponly=auth_settings.ACCESS_HTTPONLY,
                samesite=auth_settings.ACCESS_SAME_SITE,
                secure=auth_settings.ACCESS_SECURE,
                expires=None,  # Set to None to make it a session cookie
                domain=auth_settings.COOKIE_DOMAIN,
            )

            if get_settings_service().settings.agentic_experience:
                from langflow.api.utils.mcp.agentic_mcp import initialize_agentic_user_variables

                await initialize_agentic_user_variables(user.id, db)

        return tokens

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "message": "Auto login is disabled.",
            "auto_login": False,
        },
    )


@router.post("/refresh", include_in_schema=False)
async def refresh_token(
    request: Request,
    response: Response,
    db: DbSession,
):
    auth_settings = get_settings_service().auth_settings

    token = request.cookies.get("refresh_token_lf")

    if token:
        auth = get_auth_service()
        tokens = await auth.create_refresh_token(token, db)
        response.set_cookie(
            "refresh_token_lf",
            tokens["refresh_token"],
            httponly=auth_settings.REFRESH_HTTPONLY,
            samesite=auth_settings.REFRESH_SAME_SITE,
            secure=auth_settings.REFRESH_SECURE,
            expires=auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS,
            domain=auth_settings.COOKIE_DOMAIN,
        )
        response.set_cookie(
            "access_token_lf",
            tokens["access_token"],
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS,
            domain=auth_settings.COOKIE_DOMAIN,
        )
        return tokens
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/session", include_in_schema=False)
async def get_session(
    request: Request,
    db: DbSession,
) -> SessionResponse:
    """Validate session and return user information.

    This endpoint checks if the user is authenticated via cookie or Authorization header.
    It does not raise an error if unauthenticated, allowing the frontend to gracefully
    handle the session state.
    """
    from langflow.services.auth.utils import oauth2_login

    # Try to get the token from the request (cookie or Authorization header)
    try:
        token = await oauth2_login(request)
        if not token:
            return SessionResponse(authenticated=False)

        # Validate the token and get user
        user = await get_auth_service().get_current_user_from_access_token(token, db)
        if not user or not user.is_active:
            return SessionResponse(authenticated=False)

        return SessionResponse(
            authenticated=True,
            user=UserRead.model_validate(user, from_attributes=True),
        )
    except (HTTPException, ValueError) as _:
        # Any authentication error means not authenticated
        return SessionResponse(authenticated=False)


@router.post("/logout", include_in_schema=False)
async def logout(response: Response):
    auth_settings = get_settings_service().auth_settings

    response.delete_cookie(
        "refresh_token_lf",
        httponly=auth_settings.REFRESH_HTTPONLY,
        samesite=auth_settings.REFRESH_SAME_SITE,
        secure=auth_settings.REFRESH_SECURE,
        domain=auth_settings.COOKIE_DOMAIN,
    )
    response.delete_cookie(
        "access_token_lf",
        httponly=auth_settings.ACCESS_HTTPONLY,
        samesite=auth_settings.ACCESS_SAME_SITE,
        secure=auth_settings.ACCESS_SECURE,
        domain=auth_settings.COOKIE_DOMAIN,
    )
    response.delete_cookie(
        "apikey_tkn_lflw",
        httponly=auth_settings.ACCESS_HTTPONLY,
        samesite=auth_settings.ACCESS_SAME_SITE,
        secure=auth_settings.ACCESS_SECURE,
        domain=auth_settings.COOKIE_DOMAIN,
    )
    return {"message": "Logout successful"}
