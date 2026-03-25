from __future__ import annotations

import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from langflow.api.utils.core import DbSession
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_settings_service

from .keycloak_client import KeycloakClient
from .mapping import (
    create_mapping,
    delete_mapping,
    ensure_table,
    find_langflow_username,
    get_or_create_shared_user,
    list_mappings,
)
from .models import KeycloakGroupMappingCreate, KeycloakGroupMappingRead
from .settings import get_keycloak_settings

router = APIRouter(prefix="/api/v1/keycloak", tags=["Keycloak SSO"])

_STATE_ALGORITHM = "HS256"
_STATE_TTL_SECONDS = 300  # 5 minutes


def _get_state_secret() -> str:
    settings = get_keycloak_settings()
    if settings.STATE_SECRET:
        return settings.STATE_SECRET
    # Fall back to Langflow's own secret key (SecretStr → unwrap)
    secret = get_settings_service().auth_settings.SECRET_KEY
    return secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)


def _create_state_token(redirect_after: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL_SECONDS)
    payload = {
        "redirect_after": redirect_after,
        "nonce": secrets.token_hex(16),
        "exp": exp,
    }
    return pyjwt.encode(payload, _get_state_secret(), algorithm=_STATE_ALGORITHM)


def _decode_state_token(state: str) -> dict:
    try:
        return pyjwt.decode(state, _get_state_secret(), algorithms=[_STATE_ALGORITHM])
    except pyjwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SSO state expired") from exc
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid SSO state") from exc


def _get_keycloak_client() -> KeycloakClient:
    s = get_keycloak_settings()
    return KeycloakClient(
        token_endpoint=s.token_endpoint,
        jwks_uri=s.jwks_uri,
        client_id=s.CLIENT_ID,
        client_secret=s.CLIENT_SECRET,
    )


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@router.get("/config", include_in_schema=True)
async def keycloak_config():
    """Return Keycloak SSO feature flags for the frontend."""
    s = get_keycloak_settings()
    return {"enabled": s.ENABLED, "button_text": s.BUTTON_TEXT}


@router.get("/login", include_in_schema=False)
async def keycloak_login(redirect_after: str = "/"):
    """Redirect the browser to the Keycloak authorization endpoint."""
    s = get_keycloak_settings()
    if not s.ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keycloak SSO is not enabled")

    state = _create_state_token(redirect_after)
    params = {
        "client_id": s.CLIENT_ID,
        "redirect_uri": s.REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    url = s.authorization_endpoint + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/callback", include_in_schema=False)
async def keycloak_callback(
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Handle the Keycloak authorization callback."""
    s = get_keycloak_settings()
    if not s.ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keycloak SSO is not enabled")

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Keycloak returned an error: {error}",
        )
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code or state")

    # 1. Validate state (CSRF protection)
    state_payload = _decode_state_token(state)
    redirect_after = state_payload.get("redirect_after", "/")

    # 2. Exchange code for tokens
    client = _get_keycloak_client()
    try:
        token_response = await client.exchange_code(code, s.REDIRECT_URI)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    # 3. Verify JWT signature using Keycloak JWKS
    access_token: str = token_response.get("access_token", "")
    try:
        payload = client.verify_and_decode(access_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Keycloak token verification failed: {exc}",
        ) from exc

    # 4. Extract groups from JWT claim
    groups = client.extract_groups(payload, s.GROUPS_CLAIM)

    # 5. Map group → shared Langflow username
    await ensure_table(db)
    langflow_username = await find_langflow_username(db, groups)
    if langflow_username is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your Keycloak groups are not mapped to any Langflow account. "
                "Please contact your administrator."
            ),
        )

    # 6. Get or create the shared Langflow user
    user = await get_or_create_shared_user(db, langflow_username)
    await db.commit()

    # 7. Create Langflow session tokens
    auth = get_auth_service()
    tokens = await auth.create_user_tokens(user_id=user.id, db=db, update_last_login=True)

    # 8. Build redirect response and set Langflow auth cookies on it directly.
    # NOTE: Cookies must be set on the RedirectResponse object itself —
    # setting them on a separate Response parameter is ignored by FastAPI
    # when a different response object is returned.
    auth_settings = get_settings_service().auth_settings
    redirect = RedirectResponse(url=redirect_after, status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        "refresh_token_lf",
        tokens["refresh_token"],
        httponly=auth_settings.REFRESH_HTTPONLY,
        samesite=auth_settings.REFRESH_SAME_SITE,
        secure=auth_settings.REFRESH_SECURE,
        expires=auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS,
        domain=auth_settings.COOKIE_DOMAIN,
    )
    redirect.set_cookie(
        "access_token_lf",
        tokens["access_token"],
        httponly=auth_settings.ACCESS_HTTPONLY,
        samesite=auth_settings.ACCESS_SAME_SITE,
        secure=auth_settings.ACCESS_SECURE,
        expires=auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        domain=auth_settings.COOKIE_DOMAIN,
    )
    redirect.set_cookie(
        "apikey_tkn_lflw",
        str(user.store_api_key or ""),
        httponly=auth_settings.ACCESS_HTTPONLY,
        samesite=auth_settings.ACCESS_SAME_SITE,
        secure=auth_settings.ACCESS_SECURE,
        expires=None,
        domain=auth_settings.COOKIE_DOMAIN,
    )
    return redirect


# ---------------------------------------------------------------------------
# Admin-only mapping management endpoints
# ---------------------------------------------------------------------------

SuperUser = Annotated[User, Depends(get_current_active_superuser)]


@router.get("/mappings", response_model=list[KeycloakGroupMappingRead])
async def get_mappings(db: DbSession, _: SuperUser):
    """List all Keycloak group → Langflow account mappings (superuser only)."""
    await ensure_table(db)
    return await list_mappings(db)


@router.post("/mappings", response_model=KeycloakGroupMappingRead, status_code=status.HTTP_201_CREATED)
async def add_mapping(body: KeycloakGroupMappingCreate, db: DbSession, _: SuperUser):
    """Create a new group mapping (superuser only)."""
    await ensure_table(db)
    try:
        mapping = await create_mapping(db, body.keycloak_group, body.langflow_username)
        await db.commit()
        return mapping
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_mapping(mapping_id: UUID, db: DbSession, _: SuperUser):
    """Delete a group mapping by ID (superuser only)."""
    await ensure_table(db)
    deleted = await delete_mapping(db, mapping_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    await db.commit()
