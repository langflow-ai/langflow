"""Authorization-code credentials are bound to one configured instance."""

from lfx.integrations.errors import InvalidRequestError
from lfx_servicenow.schema import READ_SCOPE, WRITE_SCOPE, origin

from langflow.services.connection.oauth.adapter import OAuthAdapter
from langflow.services.connection.oauth.config import OAuthError, OAuthRegistration


def configured_origin() -> str:
    try:
        return origin()
    except InvalidRequestError:
        msg = "The ServiceNow deployment instance is unavailable."
        raise OAuthError(msg, reason="registration-unavailable") from None


def validate_registration(registration: OAuthRegistration) -> None:
    root = configured_origin()
    if (
        registration.profile != "user"
        or registration.client_type != "confidential"
        or registration.context not in {"self_managed", "hosted"}
        or registration.private_key
        or registration.tenant != root
        or not set(registration.scopes) <= {READ_SCOPE, WRITE_SCOPE}
        or READ_SCOPE not in registration.scopes
        or (registration.allowed_tenants and set(registration.allowed_tenants) != {root})
    ):
        msg = "ServiceNow requires a confidential registration bound to its configured instance and scopes."
        raise OAuthError(msg, reason="registration-unavailable")


def endpoints(registration: OAuthRegistration) -> tuple[str, str]:
    validate_registration(registration)
    root = configured_origin()
    return root + "/oauth_auth.do", root + "/oauth_token.do"


async def parse_token(registration: OAuthRegistration, body: dict, *, refresh: bool) -> tuple[dict, dict | None]:
    validate_registration(registration)
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("access_token"), str)
        or not body["access_token"]
        or str(body.get("token_type", "")).lower() != "bearer"
        or "expires_in" not in body
        or (not refresh and (not isinstance(body.get("refresh_token"), str) or not body["refresh_token"]))
        or ("refresh_token" in body and (not isinstance(body["refresh_token"], str) or not body["refresh_token"]))
        or (
            "scope" in body
            and (not isinstance(body["scope"], str) or not set(body["scope"].split()) <= set(registration.scopes))
        )
        or (not refresh and (not isinstance(body.get("scope"), str) or READ_SCOPE not in body["scope"].split()))
    ):
        msg = "ServiceNow returned an invalid credential response."
        raise OAuthError(msg, reason="provider-unavailable")
    token = {key: body[key] for key in ("access_token", "refresh_token", "scope", "expires_in") if key in body}
    root = configured_origin()
    # The token response does not identify the user. Account metadata names only the issuing instance.
    account = None if refresh else {"id": root, "tenant_id": root, "display": "ServiceNow instance"}
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
