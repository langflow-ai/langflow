"""Validate personal access tokens against their configured GitLab instance."""

from datetime import datetime, timezone

from lfx.integrations.errors import InvalidRequestError
from lfx.integrations.models import (
    ConnectionAccount,
    ConnectionRef,
    ConnectionResolutionRequest,
    CredentialLease,
    ResolvedCredential,
)
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_gitlab.client import GitLabClient, api_origin, positive_id

from langflow.services.database.models.connection.schemas import ExecutingIdentityDescriptor


class ManualResolver:
    def __init__(self, credential):
        self.credential = credential

    async def resolve(self, _request):
        return self.credential


async def validate_manual_credential(payload, *, context):
    credentials = payload.credentials
    if (
        payload.provider_key != "gitlab"
        or context not in {"hosted", "self_managed", "desktop", "headless"}
        or credentials is None
        or credentials.refresh_token is not None
        or credentials.token_type.lower() != "bearer"
    ):
        msg = "Use a personal access token with the api scope."
        raise InvalidRequestError(msg, provider="gitlab")
    origin = api_origin()
    # These provisional claims only permit introspection. Returned metadata replaces all user claims.
    credential = ResolvedCredential(
        access_token=credentials.access_token,
        provider="gitlab",
        identity="user_delegated",
        account=ConnectionAccount(id="validation", tenant_id=origin),
        granted_scopes=frozenset({"api"}),
        scopes_verified=True,
        expires_at=datetime.max.replace(tzinfo=timezone.utc),
    )
    lease = CredentialLease(
        ManualResolver(credential),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="gitlab", name=payload.name),
            principal=ExecutionPrincipal(kind="actor", user_id="manual-validation", interactive=True),
        ),
    )
    async with GitLabClient(lease) as client:
        info = await client.request("GET", "/personal_access_tokens/self")
        user = await client.request("GET", "/user")
    if (
        not isinstance(info, dict)
        or not isinstance(user, dict)
        or info.get("active") is not True
        or info.get("revoked") is not False
        or not isinstance(info.get("scopes"), list)
        or "api" not in info["scopes"]
        or user.get("bot") is not False
        or user.get("state") != "active"
    ):
        msg = "Choose an active personal access token with the api scope."
        raise InvalidRequestError(msg, provider="gitlab")
    user_id = str(positive_id(user.get("id")))
    if str(info.get("user_id")) != user_id:
        msg = "The token and user identities do not match."
        raise InvalidRequestError(msg, provider="gitlab")
    try:
        expiry = datetime.strptime(info["expires_at"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        msg = "The GitLab token must have a provider expiration date."
        raise InvalidRequestError(msg, provider="gitlab") from None
    if expiry <= datetime.now(timezone.utc):
        msg = "The GitLab personal access token has expired."
        raise InvalidRequestError(msg, provider="gitlab")
    if credentials.expires_at is not None:
        supplied = credentials.expires_at
        if supplied.tzinfo is None or supplied <= datetime.now(timezone.utc):
            msg = "Provide a future expiration with its time zone."
            raise InvalidRequestError(msg, provider="gitlab")
        expiry = min(expiry, supplied)
    account = ConnectionAccount(id=user_id, display=str(user.get("username", user_id)), tenant_id=origin)
    return payload.model_copy(
        update={
            "granted_scopes": ["api"],
            "executing_identity": ExecutingIdentityDescriptor(identity="user_delegated", account=account),
            "credentials": credentials.model_copy(update={"expires_at": expiry}),
        }
    )
