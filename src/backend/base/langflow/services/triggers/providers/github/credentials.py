"""Validate manual GitHub App installation identity without trusting scope claims."""

from datetime import datetime, timedelta, timezone

from lfx.integrations.errors import AuthExpiredError, ConnectionNotAuthorizedError, IntegrationError, RateLimitedError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease, ResolvedCredential
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_github.client import GitHubClient

from langflow.services.connection.slack_credentials import ManualCredentialError
from langflow.services.database.models.connection.schemas import ConnectionCreate, ExecutingIdentityDescriptor


class _ManualResolver:
    def __init__(self, credential: ResolvedCredential):
        self.credential = credential

    async def resolve(self, _request: ConnectionResolutionRequest) -> ResolvedCredential:
        return self.credential


async def validate_manual_credential(payload: ConnectionCreate, *, context: str) -> ConnectionCreate:
    credentials = payload.credentials
    if (
        payload.provider_key != "github"
        or context not in {"hosted", "self_managed", "desktop", "headless"}
        or credentials is None
        or credentials.refresh_token is not None
        or credentials.token_type.lower() != "bearer"
    ):
        msg = "Use a GitHub App installation access token with its expiration."
        raise ManualCredentialError(msg)
    now = datetime.now(timezone.utc)
    expiry = credentials.expires_at
    if expiry is None:
        msg = "GitHub installation access tokens require their actual expiration."
        raise ManualCredentialError(msg)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= now:
        msg = "The GitHub installation access token has expired."
        raise ManualCredentialError(msg)
    expiry = min(expiry, now + timedelta(hours=1))
    request = ConnectionResolutionRequest(
        ref=ConnectionRef(provider="github", name=payload.name),
        principal=ExecutionPrincipal(kind="actor", user_id="manual-validation", interactive=True),
    )
    credential = ResolvedCredential(
        access_token=credentials.access_token, expires_at=expiry, identity="service", provider="github"
    )
    lease = CredentialLease(_ManualResolver(credential), request)
    try:
        async with GitHubClient(lease) as client:
            await client.request("GET", "/installation/repositories", params={"per_page": 1})
    except AuthExpiredError:
        msg = "GitHub rejected this token. Paste a valid GitHub App installation token and try again."
        raise ManualCredentialError(msg) from None
    except ConnectionNotAuthorizedError:
        msg = "GitHub rejected this token. Use a GitHub App installation token with repository access."
        raise ManualCredentialError(msg) from None
    except RateLimitedError:
        msg = "GitHub rate limited this token check. Wait and try again."
        raise ManualCredentialError(msg) from None
    except IntegrationError:
        msg = "GitHub could not check this token. Try again."
        raise ManualCredentialError(msg) from None
    # Permissions are enforced by GitHub endpoints. Claimed OAuth scope grants are discarded.
    return payload.model_copy(
        update={
            "granted_scopes": [],
            "executing_identity": ExecutingIdentityDescriptor(identity="service"),
            "credentials": credentials.model_copy(update={"expires_at": expiry}),
        }
    )
