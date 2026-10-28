"""Salesforce authorization code and refresh parsing for one operator org."""

from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

import httpx
from lfx.integrations.errors import InvalidRequestError
from lfx.utils.ssrf_httpx import ssrf_protected_strict_httpx_client_kwargs_for_url
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx.utils.url_redaction import suppress_sensitive_http_logs
from lfx_salesforce.schema import origin

from langflow.services.connection.oauth.adapter import OAuthAdapter
from langflow.services.connection.oauth.config import OAuthError, OAuthRegistration

_SCOPES = frozenset({"api", "id", "refresh_token"})
_IDENTITY = re.compile(r"^/id/([A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?)/([A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?)$")
_MAX_IDENTITY_BYTES = 65536
_MAX_DISPLAY_LENGTH = 255
_SALESFORCE_ID = re.compile(r"[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?")


def same_identity_id(actual: object, expected: str) -> bool:
    return isinstance(actual, str) and bool(_SALESFORCE_ID.fullmatch(actual)) and actual[:15] == expected[:15]


def identity_http_client(root: str) -> httpx.AsyncClient:
    kwargs = ssrf_protected_strict_httpx_client_kwargs_for_url(root)[1]
    return httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False, **kwargs)


async def account_identity(root: str, path: str, org_id: str, user_id: str, token: str) -> dict:
    unavailable = "The Salesforce account identity could not be verified. Reconnect and retry."
    try:
        async with (
            identity_http_client(root) as client,
            suppress_sensitive_http_logs(),
            client.stream(
                "GET", root + path, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
            ) as response,
        ):
            if response.status_code != httpx.codes.OK:
                raise OAuthError(unavailable, reason="provider-unavailable")
            raw = bytearray()
            async for part in response.aiter_bytes():
                raw.extend(part)
                if len(raw) > _MAX_IDENTITY_BYTES:
                    raise OAuthError(unavailable, reason="provider-unavailable")
            profile = json.loads(raw)
    except (httpx.HTTPError, SSRFProtectionError, ValueError, UnicodeDecodeError):
        raise OAuthError(unavailable, reason="provider-unavailable") from None
    if (
        not isinstance(profile, dict)
        or not same_identity_id(profile.get("organization_id"), org_id)
        or not same_identity_id(profile.get("user_id"), user_id)
        or profile.get("active") is not True
        or profile.get("asserted_user") is not True
    ):
        raise OAuthError(unavailable, reason="provider-unavailable")
    account = {"id": f"{org_id}/{user_id}", "tenant_id": root}
    for field in ("display_name", "email", "username"):
        display = profile.get(field)
        if isinstance(display, str) and display.strip() and len(display) <= _MAX_DISPLAY_LENGTH:
            account["display"] = display.strip()
            break
    return account


def configured_origin() -> str:
    try:
        return origin()
    except InvalidRequestError:
        msg = "The Salesforce deployment org is not configured."
        raise OAuthError(msg, reason="registration-unavailable") from None


def endpoints(_registration: OAuthRegistration) -> tuple[str, str]:
    root = configured_origin()
    return root + "/services/oauth2/authorize", root + "/services/oauth2/token"


def validate_registration(registration: OAuthRegistration) -> None:
    root = configured_origin()
    if (
        registration.profile != "user"
        or registration.client_type != "confidential"
        or registration.context not in {"hosted", "self_managed"}
        or registration.private_key
        or registration.tenant != root
        or set(registration.scopes) != _SCOPES
        or (registration.allowed_tenants and set(registration.allowed_tenants) != {root})
    ):
        msg = "Salesforce requires a confidential registration bound to the configured org and scopes."
        raise OAuthError(msg, reason="registration-unavailable")


async def parse_token(registration: OAuthRegistration, body: dict, *, refresh: bool) -> tuple[dict, dict | None]:
    validate_registration(registration)
    root = configured_origin()
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("instance_url"), str)
        or body["instance_url"] not in {root, root + "/"}
        or not isinstance(body.get("token_type"), str)
        or body["token_type"].lower() != "bearer"
        or not isinstance(body.get("access_token"), str)
        or not body["access_token"]
    ):
        msg = "Salesforce returned an invalid org credential."
        raise OAuthError(msg, reason="provider-unavailable")
    raw_scope = body.get("scope")
    if raw_scope is not None and (not isinstance(raw_scope, str) or not set(raw_scope.split()) >= _SCOPES):
        msg = "Salesforce did not grant the required scopes."
        raise OAuthError(msg, reason="provider-unavailable")
    if not refresh and (
        raw_scope is None or not isinstance(body.get("refresh_token"), str) or not body["refresh_token"]
    ):
        msg = "Salesforce did not grant a refreshable credential."
        raise OAuthError(msg, reason="provider-unavailable")
    token = {key: body[key] for key in ("access_token", "refresh_token", "scope", "expires_in") if key in body}
    if "refresh_token" in token and (not isinstance(token["refresh_token"], str) or not token["refresh_token"]):
        msg = "Salesforce returned an invalid refresh credential."
        raise OAuthError(msg, reason="provider-unavailable")
    account = None
    if not refresh:
        try:
            if not isinstance(body.get("id"), str):
                raise TypeError
            identity = urlsplit(body["id"])
            match = _IDENTITY.fullmatch(identity.path)
            valid = (
                identity.scheme == "https"
                and identity.netloc in {"login.salesforce.com", "test.salesforce.com", urlsplit(root).hostname}
                and not identity.query
                and not identity.fragment
                and match
            )
        except (ValueError, TypeError):
            valid = False
        if not valid:
            msg = "Salesforce returned invalid account metadata."
            raise OAuthError(msg, reason="provider-unavailable")
        account = await account_identity(root, identity.path, match[1], match[2], body["access_token"])
    return token, account


try:
    _ORIGINS = (origin(),)
except InvalidRequestError:
    _ORIGINS = ()

OAUTH = OAuthAdapter(
    endpoints=endpoints,
    allowed_origins=_ORIGINS,
    validate_registration=validate_registration,
    parse_token=parse_token,
    supports_pkce=True,
)
