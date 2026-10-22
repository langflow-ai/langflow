"""Repository webhook creation and durable remote cleanup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.integrations.errors import ProviderUnavailableError, ResourceNotFoundError
from lfx_github.client import GitHubClient, positive_id, repository_path
from sqlmodel import select

from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerSubscription
from langflow.services.triggers.constants import FAMILY_TRIGGER_PUSH
from langflow.services.triggers.ingress.verifiers import IngressSecrets
from langflow.services.triggers.providers.github.config import normalize_config
from langflow.services.triggers.providers.github.credentials import validate_manual_credential
from langflow.services.triggers.providers.github.events import verify
from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider
from langflow.services.triggers.source_clients import source_lease
from langflow.services.triggers.source_errors import SourceConfigurationError
from langflow.services.triggers.source_subscription import source_ingress_url
from langflow.services.triggers.subscriptions import upsert_subscription

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease
    from sqlmodel.ext.asyncio.session import AsyncSession


WEBHOOK_PAGE_SIZE = 100


def _event(trigger: Trigger) -> str:
    return "issues" if trigger.kind == "github.issue" else "pull_request"


def _hook_id(value: str) -> int:
    return positive_id(value.rsplit(":", 1)[-1])


async def prepare(session: AsyncSession, trigger: Trigger) -> None:
    pending = (
        await session.exec(
            select(TriggerCleanup.id).where(
                TriggerCleanup.provider == "github",
                TriggerCleanup.trigger_id == trigger.id,
            )
        )
    ).first()
    if pending is not None:
        msg = "The previous GitHub webhook is still being removed. Wait for cleanup before enabling this trigger."
        raise SourceConfigurationError(msg)


async def provision(session: AsyncSession, trigger: Trigger) -> TriggerSubscription:
    await prepare(session, trigger)
    repository = trigger.config["repository"]
    path = repository_path(repository)
    address = await source_ingress_url(session, trigger)
    if not trigger.signing_secret_encrypted:
        msg = "The GitHub webhook signing secret has not been initialized."
        raise ValueError(msg)
    signing_secret = decrypt_api_key(trigger.signing_secret_encrypted)
    lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
    async with GitHubClient(lease) as client:
        repo = await client.request("GET", path)
        if not isinstance(repo, dict) or type(repo.get("id")) is not int:
            raise ProviderUnavailableError(provider="github")
        hook_id = None
        # Reconcile a timed-out create by its opaque per-trigger callback before creating another hook.
        for page in range(1, 11):
            hooks = await client.request("GET", path + "/hooks", params={"per_page": 100, "page": page})
            if not isinstance(hooks, list):
                raise ProviderUnavailableError(provider="github")
            matching = [
                hook
                for hook in hooks
                if isinstance(hook, dict)
                and isinstance(hook.get("config"), dict)
                and hook["config"].get("url") == address
            ]
            if len(matching) > 1 or (matching and hook_id is not None):
                msg = "Duplicate GitHub callbacks require administrator cleanup before rearming."
                raise ValueError(msg)
            if matching:
                hook_id = positive_id(matching[0].get("id"))
            if len(hooks) < WEBHOOK_PAGE_SIZE:
                break
        else:
            msg = "The repository webhook list exceeded the bounded setup scan."
            raise ValueError(msg)
        body = {
            "name": "web",
            "active": True,
            "events": [_event(trigger)],
            "config": {"url": address, "content_type": "json", "secret": signing_secret, "insecure_ssl": "0"},
        }
        if hook_id:
            body.pop("name")
        response = await client.request(
            "PATCH" if hook_id else "POST", path + "/hooks" + (f"/{hook_id}" if hook_id else ""), body=body
        )
        if not isinstance(response, dict):
            raise ProviderUnavailableError(provider="github")
        hook_id = positive_id(response.get("id"))
    subscription = await upsert_subscription(
        session,
        trigger_id=trigger.id,
        connection_id=trigger.connection_id,
        provider="github",
        provider_subscription_id=f"{repository}:{hook_id}",
        client_state_digest=None,
        expires_at=None,
        provider_state={
            "repository": repository,
            "repository_id": str(repo["id"]),
            "hook_id": hook_id,
            "callback": address,
        },
    )
    session.add(subscription)
    return subscription


async def ingress_secrets(session: AsyncSession, trigger: Trigger) -> IngressSecrets:
    subscription = (
        await session.exec(
            select(TriggerSubscription).where(
                TriggerSubscription.trigger_id == trigger.id,
                TriggerSubscription.provider == "github",
                TriggerSubscription.state == "active",
            )
        )
    ).first()
    if subscription is None or not trigger.signing_secret_encrypted:
        return IngressSecrets()
    return IngressSecrets(
        signing_secret=decrypt_api_key(trigger.signing_secret_encrypted),
        resource_id=subscription.provider_state.get("repository_id"),
        target_config=dict(trigger.config),
        target_kind=trigger.kind,
    )


async def revoke(task: TriggerCleanup, lease: CredentialLease) -> None:
    path = repository_path(task.provider_state["repository"]) + f"/hooks/{_hook_id(task.provider_subscription_id)}"
    try:
        async with GitHubClient(lease) as client:
            await client.request("DELETE", path)
    except ResourceNotFoundError:
        return


PROVIDER = TriggerProvider(
    provider_id="github",
    bundle="github",
    kinds=(
        TriggerKind(
            kind="github.issue",
            component="GitHubOnIssueTriggerComponent",
            display_name="GitHub: On Issue",
            config_fields=("connection", "repository", "actions", "delivery_mode", "include_bot_events"),
            required_scopes=(),
            identity="service",
            push_mechanism="github.repository_webhook",
        ),
        TriggerKind(
            kind="github.pull_request",
            component="GitHubOnPullRequestTriggerComponent",
            display_name="GitHub: On Pull Request",
            config_fields=("connection", "repository", "actions", "delivery_mode", "include_bot_events"),
            required_scopes=(),
            identity="service",
            push_mechanism="github.repository_webhook",
        ),
    ),
    normalize_config=normalize_config,
    provision=provision,
    revoke=revoke,
    verify=verify,
    ingress_secrets=ingress_secrets,
    api_origins=("https://api.github.com",),
    validate_manual_credential=validate_manual_credential,
    manual_token_requires_expiry=True,
    prepare=prepare,
)
