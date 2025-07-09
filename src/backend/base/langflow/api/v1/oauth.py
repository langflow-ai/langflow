from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from langflow.api.utils import DbSession
from langflow.api.v1.schemas import OAuthProvidersResponse
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.auth.utils import create_user_tokens
from langflow.services.deps import get_oauth_service, get_variable_service
from langflow.services.oauth.service import OAuthService

router = APIRouter(tags=["OAuth"], prefix="/oauth")


@router.get("/providers", response_model=OAuthProvidersResponse)
async def get_oauth_providers(
    oauth_service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> OAuthProvidersResponse:
    """Get available OAuth providers."""
    return OAuthProvidersResponse(
        enabled=oauth_service.is_oauth_enabled(), providers=oauth_service.get_oauth_providers()
    )


@router.get("/{provider}/login")
async def oauth_login(
    provider: str, request: Request, oauth_service: Annotated[OAuthService, Depends(get_oauth_service)]
) -> RedirectResponse:
    """Initiate OAuth login for the specified provider."""
    try:
        return await oauth_service.get_authorization_url(provider, request)
    except HTTPException:
        raise
    except (ValueError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to initiate OAuth login: {e!s}"
        ) from e


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    db: DbSession,
    oauth_service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> RedirectResponse:
    """Handle OAuth callback and authenticate user."""
    try:
        tokens = await oauth_service.handle_oauth_callback(provider, request, db, create_user_tokens)

        # Get auth settings for cookie configuration
        auth_settings = oauth_service.settings_service.auth_settings

        # Get user info to set the API key cookie
        from langflow.services.auth.utils import get_user_id_from_token

        user_id = get_user_id_from_token(tokens["access_token"])

        # Get user to access store_api_key
        from langflow.services.database.models.user.crud import get_user_by_id

        user = await get_user_by_id(db, user_id)

        # Initialize user variables and create default folder
        await get_variable_service().initialize_user_variables(user_id, db)
        await get_or_create_default_folder(db, user_id)

        # Determine frontend URL
        frontend_url = None

        # Try to get from referer header
        referer = request.headers.get("referer")
        if referer and "/api/" in referer:
            frontend_url = referer.split("/api/")[0]

        # Fallback to common frontend URLs
        if not frontend_url:
            host = request.headers.get("host", "")
            if "localhost" in host or "127.0.0.1" in host:
                frontend_url = "http://localhost:3000"
            else:
                scheme = request.headers.get("x-forwarded-proto", "http")
                frontend_url = f"{scheme}://{host.split(':')[0]}"

        redirect_url = f"{frontend_url}/oauth-callback?success=true"

        # Create RedirectResponse and set cookies directly on it
        redirect_response = RedirectResponse(url=redirect_url, status_code=302)

        # Set cookies directly on the redirect response
        redirect_response.set_cookie(
            "refresh_token_lf",  # Same name as regular login
            tokens["refresh_token"],
            httponly=auth_settings.REFRESH_HTTPONLY,
            samesite=auth_settings.REFRESH_SAME_SITE,
            secure=auth_settings.REFRESH_SECURE,
            expires=auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS,
            domain=auth_settings.COOKIE_DOMAIN,
        )

        redirect_response.set_cookie(
            "access_token_lf",  # Same name as regular login
            tokens["access_token"],
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS,
            domain=auth_settings.COOKIE_DOMAIN,
        )

        # Set API key cookie - EXACT same as regular login
        if user and user.store_api_key is not None:
            redirect_response.set_cookie(
                "apikey_tkn_lflw",  # Same name as regular login
                str(user.store_api_key),
                httponly=auth_settings.ACCESS_HTTPONLY,
                samesite=auth_settings.ACCESS_SAME_SITE,
                secure=auth_settings.ACCESS_SECURE,
                expires=None,  # Set to None to make it a session cookie
                domain=auth_settings.COOKIE_DOMAIN,
            )

    except HTTPException:
        raise
    except (ValueError, RuntimeError, KeyError):
        # Redirect to login page with error
        frontend_url = None
        referer = request.headers.get("referer")
        if referer and "/api/" in referer:
            frontend_url = referer.split("/api/")[0]

        if not frontend_url:
            host = request.headers.get("host", "")
            if "localhost" in host or "127.0.0.1" in host:
                frontend_url = "http://localhost:3000"
            else:
                scheme = request.headers.get("x-forwarded-proto", "http")
                frontend_url = f"{scheme}://{host.split(':')[0]}"

        error_redirect_url = f"{frontend_url}/oauth-callback?error=oauth_failed"
        return RedirectResponse(url=error_redirect_url, status_code=302)
    else:
        return redirect_response
