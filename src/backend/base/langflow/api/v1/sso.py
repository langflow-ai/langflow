"""SSO authentication endpoints for OIDC, SAML, and LDAP providers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, status
from lfx.log.logger import logger

from langflow.api.utils import DbSession
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.auth.utils import create_user_tokens
from langflow.services.deps import get_settings_service, get_variable_service

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User

router = APIRouter(tags=["SSO"], prefix="/sso")


@router.get("/login")
async def sso_login_redirect(
    provider: str = Query(default="oidc", description="SSO provider type (oidc, saml, ldap)"),
) -> dict:
    """Initiate SSO login by redirecting to the identity provider.

    Args:
        provider: SSO provider type (currently only 'oidc' is supported)

    Returns:
        Redirect URL to the identity provider's authorization endpoint

    Raises:
        HTTPException: If SSO is not enabled or configured
    """
    settings_service = get_settings_service()
    auth_settings = settings_service.auth_settings

    # Check if SSO is enabled
    if not auth_settings.SSO_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO is not enabled. Please enable it in the settings.",
        )

    # Only OIDC is supported in Phase 1
    if provider.lower() != "oidc":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider}' is not supported. Currently only 'oidc' is available.",
        )

    # Load SSO configuration
    from langflow.services.auth.sso_service import SSOConfigService

    sso_service = SSOConfigService(settings_service)

    # Try to load config from file
    if not auth_settings.SSO_CONFIG_FILE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO configuration file not specified. Set LANGFLOW_SSO_CONFIG_FILE environment variable.",
        )

    try:
        sso_config = sso_service._load_from_file(auth_settings.SSO_CONFIG_FILE)
    except Exception as e:
        logger.error(f"Failed to load SSO configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load SSO configuration. Please check server logs.",
        ) from e

    if not sso_config or not sso_config.oidc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC configuration not found or invalid.",
        )

    oidc_config = sso_config.oidc

    # Build authorization URL
    # Format: {authorization_endpoint}?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scopes}&state={state}

    # Generate state parameter for CSRF protection (in production, this should be stored in session/cache)
    import secrets

    state = secrets.token_urlsafe(32)

    # Build query parameters
    params = {
        "client_id": oidc_config.client_id,
        "redirect_uri": oidc_config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(oidc_config.scopes),
        "state": state,
    }

    # Get authorization endpoint from discovery or use configured one
    from langflow.services.auth.oidc_service import OIDCAuthService

    oidc_service = OIDCAuthService(settings_service, oidc_config)

    try:
        discovery_data = await oidc_service.get_oidc_discovery()
        authorization_endpoint = discovery_data.get("authorization_endpoint")

        if not authorization_endpoint:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authorization endpoint not found in OIDC discovery document.",
            )
    except Exception as e:
        logger.error(f"Failed to fetch OIDC discovery document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect to identity provider. Please check configuration.",
        ) from e

    # Build full authorization URL
    auth_url = f"{authorization_endpoint}?{urlencode(params)}"

    return {
        "authorization_url": auth_url,
        "state": state,
        "provider": provider,
    }


@router.get("/callback")
async def sso_callback(
    db: DbSession,
    code: str = Query(..., description="Authorization code from IdP"),
    state: str = Query(..., description="State parameter for CSRF protection"),
):
    """Handle SSO callback from identity provider.

    This endpoint receives the authorization code from the IdP, exchanges it for tokens,
    validates the ID token, and creates/updates the user in Langflow.

    After successful authentication, redirects to the frontend with authentication cookies set.

    Args:
        code: Authorization code from the identity provider
        state: State parameter for CSRF protection
        db: Database session

    Returns:
        RedirectResponse to frontend with authentication cookies

    Raises:
        HTTPException: If authentication fails
    """
    settings_service = get_settings_service()
    auth_settings = settings_service.auth_settings

    # Verify SSO is enabled
    if not auth_settings.SSO_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO is not enabled.",
        )

    # TODO: Validate state parameter (requires session/cache storage)
    # For POC, we'll skip state validation but log a warning
    logger.warning("State parameter validation not implemented - CSRF protection disabled for POC")

    # Load SSO configuration
    from langflow.services.auth.sso_service import SSOConfigService

    sso_service = SSOConfigService(settings_service)

    if not auth_settings.SSO_CONFIG_FILE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SSO configuration not available.",
        )

    try:
        sso_config = sso_service._load_from_file(auth_settings.SSO_CONFIG_FILE)
    except Exception as e:
        logger.error(f"Failed to load SSO configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load SSO configuration.",
        ) from e

    if not sso_config or not sso_config.oidc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OIDC configuration not found.",
        )

    # Initialize OIDC service
    from langflow.services.auth.oidc_service import OIDCAuthService

    oidc_service = OIDCAuthService(settings_service, sso_config.oidc)

    try:
        # Authenticate user via OIDC (exchanges code for tokens, validates, and provisions user)
        user: User = await oidc_service.authenticate_with_oidc(code, db)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed. User could not be created or found.",
            )

        # Create Langflow tokens for the user
        tokens = await create_user_tokens(user_id=user.id, db=db, update_last_login=True)

        # Initialize user variables
        await get_variable_service().initialize_user_variables(user.id, db)

        # Create default project for user
        _ = await get_or_create_default_folder(db, user.id)

        # Initialize agentic variables if enabled
        if get_settings_service().settings.agentic_experience:
            from langflow.api.utils.mcp.agentic_mcp import initialize_agentic_user_variables

            await initialize_agentic_user_variables(user.id, db)

        logger.info(f"SSO authentication successful for user: {user.username}")

        # Create redirect response and set cookies
        from starlette.responses import RedirectResponse

        redirect_url = auth_settings.SSO_REDIRECT_URL
        logger.info(f"Redirecting to frontend: {redirect_url}")
        redirect_response = RedirectResponse(url=redirect_url, status_code=302)

        # Set cookies on the redirect response
        redirect_response.set_cookie(
            "refresh_token_lf",
            tokens["refresh_token"],
            httponly=auth_settings.REFRESH_HTTPONLY,
            samesite=auth_settings.REFRESH_SAME_SITE,
            secure=auth_settings.REFRESH_SECURE,
            expires=auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS,
            domain=auth_settings.COOKIE_DOMAIN,
        )
        redirect_response.set_cookie(
            "access_token_lf",
            tokens["access_token"],
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS,
            domain=auth_settings.COOKIE_DOMAIN,
        )
        redirect_response.set_cookie(
            "apikey_tkn_lflw",
            str(user.store_api_key) if user.store_api_key else "",
            httponly=auth_settings.ACCESS_HTTPONLY,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=None,  # Session cookie
            domain=auth_settings.COOKIE_DOMAIN,
        )

        return redirect_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SSO callback error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed. Please try again or contact support.",
        ) from e


@router.get("/config")
async def get_sso_config():
    """Get SSO configuration status (for frontend to determine if SSO is available).

    Returns:
        SSO configuration status including enabled state and available providers
    """
    settings_service = get_settings_service()
    auth_settings = settings_service.auth_settings

    if not auth_settings.SSO_ENABLED:
        return {
            "enabled": False,
            "providers": [],
        }

    # Load configuration to determine available providers
    from langflow.services.auth.sso_service import SSOConfigService

    sso_service = SSOConfigService(settings_service)

    providers = []

    if auth_settings.SSO_CONFIG_FILE:
        try:
            sso_config = sso_service._load_from_file(auth_settings.SSO_CONFIG_FILE)
            if sso_config:
                if sso_config.oidc:
                    providers.append(
                        {
                            "type": "oidc",
                            "name": sso_config.oidc.provider_name,
                            "enabled": True,
                        }
                    )
                # Future: Add SAML and LDAP providers here
        except Exception as e:
            logger.error(f"Failed to load SSO config for status check: {e}")

    return {
        "enabled": True,
        "providers": providers,
    }
