"""Atlassian 3LO with a verified grant for one operator-configured site."""

from lfx.integrations.errors import IntegrationError
from lfx_jira.client import http_client, send
from lfx_jira.schema import READ, SCOPES, USER, cloud_id

from langflow.services.connection.oauth.adapter import OAuthAdapter
from langflow.services.connection.oauth.config import OAuthError

MAX_TOKEN_LIFETIME = 86400
MAX_ACCOUNT_LENGTH = 255


def endpoints(_registration):
    return "https://auth.atlassian.com/authorize", "https://auth.atlassian.com/oauth/token"


def validate_registration(registration):
    try:
        site = cloud_id()
    except IntegrationError:
        msg = "The Jira Cloud deployment site is not configured."
        raise OAuthError(msg, reason="registration-unavailable") from None
    if (
        registration.profile != "user"
        or registration.client_type != "confidential"
        or registration.private_key
        or registration.context not in {"hosted", "self_managed"}
        or registration.tenant != site
        or set(registration.scopes) != SCOPES
        or (registration.allowed_tenants and set(registration.allowed_tenants) != {site})
    ):
        msg = "Jira requires a confidential OAuth registration bound to the configured site and scopes."
        raise OAuthError(
            msg,
            reason="registration-unavailable",
        )


async def parse_token(registration, body, *, refresh):  # noqa: ARG001 - initial and rotating grants undergo the same validation
    validate_registration(registration)
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("access_token"), str)
        or not body["access_token"]
        or not isinstance(body.get("refresh_token"), str)
        or not body["refresh_token"]
        or type(body.get("expires_in")) is not int
        or not 0 < body["expires_in"] <= MAX_TOKEN_LIFETIME
        or not isinstance(body.get("scope"), str)
        or not {READ, USER} <= set(body["scope"].split())
    ):
        msg = "Atlassian did not return a valid refreshable Jira grant."
        raise OAuthError(msg, reason="provider-unavailable")
    token = {key: body[key] for key in ("access_token", "refresh_token", "expires_in", "scope")}
    # offline_access grants refresh credentials but need not appear in token scope echoes.
    try:
        async with http_client() as http:
            resources = await send(http, "GET", "/oauth/token/accessible-resources", body["access_token"])
            site_grant = (
                next(
                    (
                        resource
                        for resource in resources
                        if (
                            isinstance(resource, dict)
                            and resource.get("id") == cloud_id()
                            and isinstance(resource.get("scopes"), list)
                            and all(isinstance(scope, str) for scope in resource["scopes"])
                            and {READ, USER} <= set(resource["scopes"])
                        )
                    ),
                    None,
                )
                if isinstance(resources, list)
                else None
            )
            if site_grant is None:
                msg = "The Jira grant does not cover the configured site."
                raise OAuthError(msg, reason="provider-unavailable")
            token["scope"] = " ".join(
                sorted(set(body["scope"].split()) & set(site_grant["scopes"]) | {"offline_access"})
            )
            account = await send(http, "GET", f"/ex/jira/{cloud_id()}/rest/api/3/myself", body["access_token"])
            if (
                not isinstance(account, dict)
                or not isinstance(account.get("accountId"), str)
                or not 0 < len(account["accountId"]) <= MAX_ACCOUNT_LENGTH
                or account.get("active") is not True
            ):
                msg = "The Jira grant has no active account identity."
                raise OAuthError(msg, reason="provider-unavailable")
    except IntegrationError:
        msg = "The Jira grant could not be verified."
        raise OAuthError(msg, reason="provider-unavailable") from None
    return token, {"id": account["accountId"], "tenant_id": cloud_id()}


OAUTH = OAuthAdapter(
    endpoints=endpoints,
    allowed_origins=("https://auth.atlassian.com",),
    validate_registration=validate_registration,
    parse_token=parse_token,
    authorization_params=lambda _registration: {"audience": "api.atlassian.com", "prompt": "consent"},
    token_encoding="json",  # noqa: S106 - serialization format
    supports_pkce=False,
)
