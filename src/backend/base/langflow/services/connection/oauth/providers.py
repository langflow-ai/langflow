"""Fixed provider endpoints and token response normalization for delegated OAuth."""

from __future__ import annotations

import base64
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from urllib.parse import urlencode
from uuid import uuid4

import httpx
import jwt

from langflow.services.connection.oauth.config import OAuthError

_MAX_TOKEN_LIFETIME_SECONDS = 31536000

if TYPE_CHECKING:
    from langflow.services.connection.oauth.config import OAuthRegistration


def challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def endpoints(registration: OAuthRegistration) -> tuple[str, str]:
    if registration.provider == "google":
        return "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token"
    if registration.provider == "microsoft":
        authority = f"https://login.microsoftonline.com/{registration.tenant}/oauth2/v2.0"
        return f"{authority}/authorize", f"{authority}/token"
    return "https://slack.com/oauth/v2/authorize", "https://slack.com/api/oauth.v2.access"


def authorization_url(registration: OAuthRegistration, *, state: str, verifier: str, scopes: list[str]) -> str:
    params = {
        "client_id": registration.client_id,
        "redirect_uri": registration.redirect_uri,
        "response_type": "code",
        "state": state,
    }
    if registration.provider != "slack" or registration.client_type == "public":
        params.update(code_challenge=challenge(verifier), code_challenge_method="S256")
    scope_key = "user_scope" if registration.provider == "slack" and registration.profile == "user" else "scope"
    params[scope_key] = ("," if registration.provider == "slack" else " ").join(scopes)
    if registration.provider == "google":
        params.update(access_type="offline", prompt="consent")
    return endpoints(registration)[0] + "?" + urlencode(params)


def client_auth(registration: OAuthRegistration) -> dict[str, str]:
    params = {"client_id": registration.client_id}
    if registration.client_secret:
        params["client_secret"] = registration.client_secret.get_secret_value()
    if registration.private_key:
        try:
            thumbprint = base64.urlsafe_b64encode(bytes.fromhex(registration.certificate_thumbprint or ""))
            now = int(time.time())
            params["client_assertion"] = jwt.encode(
                {
                    "aud": endpoints(registration)[1],
                    "iss": registration.client_id,
                    "sub": registration.client_id,
                    "jti": str(uuid4()),
                    "nbf": now,
                    "iat": now,
                    "exp": now + 300,
                },
                registration.private_key.get_secret_value(),
                algorithm="PS256",
                headers={"x5t#S256": thumbprint.rstrip(b"=").decode("ascii")},
            )
        except (ValueError, TypeError, jwt.PyJWTError):
            msg = "OAuth certificate authentication is not configured correctly."
            raise OAuthError(msg) from None
        params["client_assertion_type"] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
    return params


async def _request(
    url: str, data: dict[str, str], *, headers: dict[str, str] | None = None, allow_empty: bool = False
) -> dict:
    # No redirects or response text in errors: provider responses may echo codes/tokens.
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.post(url, data=data, headers=headers)
            if response.status_code != httpx.codes.OK:
                msg = "OAuth provider rejected the request. Reconnect the connection."
                raise OAuthError(msg)
            body = {} if allow_empty and not response.content else response.json()
        if not isinstance(body, dict) or body.get("error") or body.get("ok") is False:
            msg = "OAuth provider rejected the request. Reconnect the connection."
            raise OAuthError(msg)
    except (httpx.HTTPError, ValueError):
        msg = "OAuth provider request failed. Reconnect the connection."
        raise OAuthError(msg) from None
    return body


async def exchange(
    registration: OAuthRegistration,
    *,
    code: str | None = None,
    verifier: str = "",
    refresh_token: str | None = None,
    previous_scopes: list[str],
) -> tuple[dict, list[str], dict | None]:
    data = client_auth(registration)
    if refresh_token:
        data.update(grant_type="refresh_token", refresh_token=refresh_token)
    else:
        data.update(grant_type="authorization_code", code=code or "", redirect_uri=registration.redirect_uri)
        if registration.provider != "slack" or registration.client_type == "public":
            data["code_verifier"] = verifier
    body = await _request(endpoints(registration)[1], data)
    token = body
    account = None
    if registration.provider == "slack":
        team = body.get("team") or {}
        if not isinstance(team, dict):
            msg = "OAuth provider returned invalid workspace metadata."
            raise OAuthError(msg)
        # Refresh replies need not contain team; it was checked during consent.
        if registration.allowed_tenants and team.get("id") not in registration.allowed_tenants and not refresh_token:
            msg = "OAuth account is outside the configured tenant restriction."
            raise OAuthError(msg)
        if registration.profile == "user" and not refresh_token:
            token = body.get("authed_user") or {}
        if not isinstance(token, dict):
            msg = "OAuth provider returned an invalid user token response."
            raise OAuthError(msg)
        if token.get("token_type") != ("bot" if registration.profile == "bot" else "user"):
            msg = "OAuth provider returned the wrong identity type."
            raise OAuthError(msg)
        if not refresh_token:
            account = {
                "id": str(token.get("id") or body.get("bot_user_id") or ""),
                "tenant_id": team.get("id"),
                "display": team.get("name"),
            }
    if registration.provider == "google" and registration.allowed_tenants and not refresh_token:
        account = await _google_account(registration, body.get("id_token"))
    access_token = token.get("access_token")
    refresh = token.get("refresh_token", refresh_token)
    if not isinstance(access_token, str) or not access_token or (refresh is not None and not isinstance(refresh, str)):
        msg = "OAuth provider returned an invalid credential response."
        raise OAuthError(msg)
    raw_scopes = token.get("scope")
    if raw_scopes is not None and not isinstance(raw_scopes, str):
        msg = "OAuth provider returned invalid scopes."
        raise OAuthError(msg)
    scopes = sorted(set(raw_scopes.replace(",", " ").split())) if raw_scopes is not None else previous_scopes
    expiry = None
    if "expires_in" in token:
        try:
            seconds = int(token["expires_in"])
            if seconds <= 0 or seconds > _MAX_TOKEN_LIFETIME_SECONDS:
                raise ValueError
            expiry = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
        except (ValueError, TypeError, OverflowError):
            msg = "OAuth provider returned an invalid token expiry."
            raise OAuthError(msg) from None
    return (
        {
            "version": 1,
            "access_token": access_token,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_at": expiry,
        },
        scopes,
        account,
    )


async def revoke(registration: OAuthRegistration, payload: dict) -> bool:
    if registration.provider == "google":
        await _request(
            "https://oauth2.googleapis.com/revoke",
            {"token": payload.get("refresh_token") or payload["access_token"]},
            allow_empty=True,
        )
        return True
    if registration.provider == "slack":
        await _request(
            "https://slack.com/api/auth.revoke", {}, headers={"Authorization": f"Bearer {payload['access_token']}"}
        )
        return True
    # Entra has no RFC 7009 endpoint for revoking just this delegated grant.
    return False


async def _google_account(registration: OAuthRegistration, id_token: object) -> dict:
    """Verify the signed hosted-domain claim; the authorization URL's hd hint is not enforcement."""
    try:
        if not isinstance(id_token, str):
            raise TypeError
        header = jwt.get_unverified_header(id_token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise ValueError
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.get("https://www.googleapis.com/oauth2/v3/certs")
            response.raise_for_status()
            keys = jwt.PyJWKSet.from_dict(response.json())
        key = keys[header["kid"]]
        claims = jwt.decode(
            id_token,
            key.key,
            algorithms=["RS256"],
            audience=registration.client_id,
            issuer=["https://accounts.google.com", "accounts.google.com"],
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
        if claims.get("hd") not in registration.allowed_tenants:
            raise ValueError
        return {"id": claims["sub"], "tenant_id": claims["hd"], "display": claims.get("email")}
    except (ValueError, KeyError, TypeError, jwt.PyJWTError, httpx.HTTPError):
        msg = "OAuth account is outside the configured tenant restriction."
        raise OAuthError(msg) from None
