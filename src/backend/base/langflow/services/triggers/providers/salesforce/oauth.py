"""Salesforce authorization code and refresh parsing for one operator org."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from lfx.integrations.errors import InvalidRequestError
from lfx_salesforce.schema import origin

from langflow.services.connection.oauth.adapter import OAuthAdapter
from langflow.services.connection.oauth.config import OAuthError, OAuthRegistration

_SCOPES = frozenset({"api", "id", "refresh_token"})
_IDENTITY = re.compile(r"^/id/([A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?)/([A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?)$")


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
        account = {"id": f"{match[1]}/{match[2]}", "tenant_id": root}
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
