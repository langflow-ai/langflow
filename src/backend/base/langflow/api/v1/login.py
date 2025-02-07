from __future__ import annotations

import secrets
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger

from langflow.api.utils import DbSession
from langflow.api.v1.schemas import Token
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.auth.utils import (
    authenticate_user,
    create_refresh_token,
    create_user_longterm_token,
    create_user_tokens,
)
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.deps import get_settings_service, get_variable_service

router = APIRouter(tags=["Login"])


@router.post("/login", response_model=Token)
async def login_to_get_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
):
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
        tokens = await create_user_tokens(user_id=user.id, db=db, update_last_login=True)
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
        # Create default folder for user if it doesn't exist
        _ = await get_or_create_default_folder(db, user.id)
        return tokens
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/auto_login")
async def auto_login(response: Response, db: DbSession):
    auth_settings = get_settings_service().auth_settings

    if auth_settings.AUTO_LOGIN:
        user_id, tokens = await create_user_longterm_token(db)
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

        return tokens

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "message": "Auto login is disabled. Please enable it in the settings",
            "auto_login": False,
        },
    )


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: DbSession,
):
    auth_settings = get_settings_service().auth_settings

    token = request.cookies.get("refresh_token_lf")

    if token:
        tokens = await create_refresh_token(token, db)
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


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token_lf")
    response.delete_cookie("access_token_lf")
    response.delete_cookie("apikey_tkn_lflw")
    return {"message": "Logout successful"}


@router.get("/sso/login")
async def sso_login():
    auth_settings = get_settings_service().auth_settings
    if not auth_settings.SSO_ENABLED:
        raise HTTPException(status_code=400, detail="SSO is not enabled")

    # Generate a state token and store it in a cookie for CSRF protection
    state = secrets.token_urlsafe(16)

    # Build the SSO authorization URL using the configured endpoints and scopes
    params = {
        "client_id": auth_settings.SSO_CLIENT_ID.get_secret_value() if auth_settings.SSO_CLIENT_ID else "",
        "response_type": "code",
        "scope": auth_settings.SSO_SCOPES,
        "redirect_uri": auth_settings.SSO_REDIRECT_URI,
        "state": state,
    }
    auth_url = f"{auth_settings.SSO_AUTH_URL}?{urlencode(params)}"
    logger.debug(f"Redirecting to SSO provider: {auth_url}")

    # Create the redirect response and set the cookie on it
    redirect_response = RedirectResponse(auth_url)
    redirect_response.set_cookie("sso_state", state, httponly=True)
    return redirect_response


@router.get("/sso/callback")
async def sso_callback(
    request: Request,
    response: Response,
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
):
    auth_settings = get_settings_service().auth_settings
    if not auth_settings.SSO_ENABLED:
        raise HTTPException(status_code=400, detail="SSO is not enabled")

    # Verify that the state from the query matches the state from the cookie
    cookie_state = request.cookies.get("sso_state")
    if not state or state != cookie_state:
        raise HTTPException(status_code=400, detail="Invalid state parameter in SSO callback")

    # Remove the temporary SSO state cookie
    response.delete_cookie("sso_state")

    # Exchange the authorization code for an access token at the SSO provider's token endpoint
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            auth_settings.SSO_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": auth_settings.SSO_REDIRECT_URI,
                "client_id": auth_settings.SSO_CLIENT_ID.get_secret_value() if auth_settings.SSO_CLIENT_ID else "",
                "client_secret": auth_settings.SSO_CLIENT_SECRET.get_secret_value()
                if auth_settings.SSO_CLIENT_SECRET
                else "",
            },
        )
    if token_response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token with SSO provider")

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    # Optionally, retrieve "id_token" if needed: id_token = token_data.get("id_token")

    # Fetch user information from the SSO provider
    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            auth_settings.SSO_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
    if userinfo_response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=400, detail="Failed to fetch user information from SSO provider")
    userinfo = userinfo_response.json()

    sub = userinfo.get("sub")
    if not sub:
        raise HTTPException(status_code=400, detail="SSO provider did not return a subject identifier.")

    # Retrieve an existing user by sub or create a new one using the SSO user info.
    from langflow.api.utils import get_or_create_user_by_sub

    user = await get_or_create_user_by_sub(sub=sub, userinfo=userinfo, db=db)

    # Generate traditional tokens for the user (same as the normal login flow)
    tokens = await create_user_tokens(user_id=user.id, db=db, update_last_login=True)
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
        expires=None,
        domain=auth_settings.COOKIE_DOMAIN,
    )

    await get_variable_service().initialize_user_variables(user.id, db)
    _ = await get_or_create_default_folder(db, user.id)
    return tokens
