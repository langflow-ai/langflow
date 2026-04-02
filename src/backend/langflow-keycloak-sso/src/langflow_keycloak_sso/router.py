from __future__ import annotations

import base64
import hashlib
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from langflow.api.utils.core import DbSession
from langflow.services.deps import get_auth_service, get_settings_service

from .hcp_client import fetch_allowed_employees
from .keycloak_client import KeycloakClient
from .mapping import get_or_create_shared_user
from .settings import get_keycloak_settings

router = APIRouter(prefix="/api/v1/keycloak", tags=["Keycloak SSO"])

_STATE_ALGORITHM = "HS256"
_STATE_TTL_SECONDS = 300  # 5 minutes


def _get_state_secret() -> str:
    settings = get_keycloak_settings()
    if settings.STATE_SECRET:
        return settings.STATE_SECRET
    secret = get_settings_service().auth_settings.SECRET_KEY
    return secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)


def _generate_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _create_state_token(redirect_after: str, nonce: str, code_verifier: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL_SECONDS)
    payload = {
        "redirect_after": redirect_after,
        "nonce": nonce,
        "code_verifier": code_verifier,
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

    nonce = secrets.token_hex(16)
    code_verifier, code_challenge = _generate_pkce()
    state = _create_state_token(redirect_after, nonce=nonce, code_verifier=code_verifier)
    params = {
        "client_id": s.CLIENT_ID,
        "redirect_uri": s.REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
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
    """Handle the Keycloak authorization callback.

    Authorization (who may access this instance) is fully enforced by Keycloak.
    Any user who successfully passes Keycloak is logged into the single shared
    Langflow account configured via KEYCLOAK_SHARED_USERNAME.
    """
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
    nonce = state_payload.get("nonce", "")
    code_verifier = state_payload.get("code_verifier", "") or None

    # 2. Exchange code for tokens (with PKCE code_verifier if present)
    client = _get_keycloak_client()
    try:
        token_response = await client.exchange_code(code, s.REDIRECT_URI, code_verifier=code_verifier)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    # 3. Verify JWT signature using Keycloak JWKS
    access_token: str = token_response.get("access_token", "")
    try:
        client.verify_and_decode(access_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Keycloak token verification failed: {exc}",
        ) from exc

    # 3b. Verify nonce in id_token to prevent replay attacks
    id_token: str = token_response.get("id_token", "")
    id_claims: dict = {}
    if id_token:
        id_claims = pyjwt.decode(id_token, options={"verify_signature": False})
        if nonce and id_claims.get("nonce") != nonce:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nonce mismatch in id_token")

    # 3c. Extract employee number from token
    employee_number = ""
    if id_claims:
        employee_number = str(id_claims.get(s.EMPLOYEE_CLAIM, ""))
    if not employee_number:
        access_claims = client.verify_and_decode(access_token)
        employee_number = str(access_claims.get(s.EMPLOYEE_CLAIM, ""))

    # 3d. Per-instance employee check (ingress-based deployment)
    if s.ALLOWED_EMPLOYEE:
        if not employee_number:
            return RedirectResponse(
                url="/login?error=no_employee_id",
                status_code=status.HTTP_302_FOUND,
            )
        if employee_number.upper() != s.ALLOWED_EMPLOYEE.upper():
            return RedirectResponse(
                url=f"/login?error=unauthorized&employee={employee_number}",
                status_code=status.HTTP_302_FOUND,
            )

    # 3e. HCP API authorization — check employee number against project roles
    if s.HCP_API_URL:
        if not employee_number:
            return RedirectResponse(
                url="/login?error=no_employee_id",
                status_code=status.HTTP_302_FOUND,
            )
        try:
            allowed = await fetch_allowed_employees(s.HCP_API_URL)
        except Exception:
            return RedirectResponse(
                url="/login?error=hcp_unavailable",
                status_code=status.HTTP_302_FOUND,
            )
        if employee_number.upper() not in allowed:
            return RedirectResponse(
                url=f"/login?error=unauthorized&employee={employee_number}",
                status_code=status.HTTP_302_FOUND,
            )

    # 4. Log into the shared account (auto-created on first login)
    user = await get_or_create_shared_user(db, s.SHARED_USERNAME)
    await db.commit()

    # 5. Issue Langflow session tokens and set cookies
    auth = get_auth_service()
    tokens = await auth.create_user_tokens(user_id=user.id, db=db, update_last_login=True)

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
    if id_token:
        redirect.set_cookie(
            "kc_id_token_lf",
            id_token,
            httponly=True,
            samesite=auth_settings.ACCESS_SAME_SITE,
            secure=auth_settings.ACCESS_SECURE,
            expires=auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS,
            domain=auth_settings.COOKIE_DOMAIN,
        )
    return redirect


@router.get("/logout", include_in_schema=False)
async def keycloak_logout(request: Request):
    """Clear Langflow session cookies and redirect to the login page.

    When Keycloak SSO end_session_endpoint is available and an id_token cookie
    is present, also terminates the upstream Keycloak SSO session so that the
    user is fully logged out across all applications sharing the same realm.

    Using a server-side redirect (rather than a JS fetch) guarantees that the
    Set-Cookie headers that expire the cookies are delivered to the browser
    even when the frontend's IS_AUTO_LOGIN constant skips the normal logout
    API call.
    """
    s = get_keycloak_settings()
    auth_settings = get_settings_service().auth_settings
    id_token = request.cookies.get("kc_id_token_lf", "")

    redirect = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    for name, httponly, samesite, secure in [
        (
            "refresh_token_lf",
            auth_settings.REFRESH_HTTPONLY,
            auth_settings.REFRESH_SAME_SITE,
            auth_settings.REFRESH_SECURE,
        ),
        ("access_token_lf", auth_settings.ACCESS_HTTPONLY, auth_settings.ACCESS_SAME_SITE, auth_settings.ACCESS_SECURE),
        ("apikey_tkn_lflw", auth_settings.ACCESS_HTTPONLY, auth_settings.ACCESS_SAME_SITE, auth_settings.ACCESS_SECURE),
        ("kc_id_token_lf", True, auth_settings.ACCESS_SAME_SITE, auth_settings.ACCESS_SECURE),
    ]:
        redirect.delete_cookie(
            name,
            httponly=httponly,
            samesite=samesite,
            secure=secure,
            domain=auth_settings.COOKIE_DOMAIN,
        )

    if s.end_session_endpoint and id_token:
        # Determine where Keycloak should send the browser after its logout page.
        if s.LOGOUT_REDIRECT_URI:
            post_logout_uri = s.LOGOUT_REDIRECT_URI
        else:
            # Try to derive the origin from REDIRECT_URI (e.g. https://app.company.com/api/v1/keycloak/callback
            # → https://app.company.com/login).
            try:
                parsed = urllib.parse.urlparse(s.REDIRECT_URI)
                post_logout_uri = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/login", "", "", ""))
            except Exception:
                post_logout_uri = "/login"

        kc_logout_params = {
            "id_token_hint": id_token,
            "post_logout_redirect_uri": post_logout_uri,
        }
        kc_logout_url = s.end_session_endpoint + "?" + urllib.parse.urlencode(kc_logout_params)
        redirect = RedirectResponse(url=kc_logout_url, status_code=status.HTTP_302_FOUND)
        # Re-delete the cookies on the new redirect response as well.
        for name, httponly, samesite, secure in [
            (
                "refresh_token_lf",
                auth_settings.REFRESH_HTTPONLY,
                auth_settings.REFRESH_SAME_SITE,
                auth_settings.REFRESH_SECURE,
            ),
            (
                "access_token_lf",
                auth_settings.ACCESS_HTTPONLY,
                auth_settings.ACCESS_SAME_SITE,
                auth_settings.ACCESS_SECURE,
            ),
            (
                "apikey_tkn_lflw",
                auth_settings.ACCESS_HTTPONLY,
                auth_settings.ACCESS_SAME_SITE,
                auth_settings.ACCESS_SECURE,
            ),
            ("kc_id_token_lf", True, auth_settings.ACCESS_SAME_SITE, auth_settings.ACCESS_SECURE),
        ]:
            redirect.delete_cookie(
                name,
                httponly=httponly,
                samesite=samesite,
                secure=secure,
                domain=auth_settings.COOKIE_DOMAIN,
            )

    return redirect
