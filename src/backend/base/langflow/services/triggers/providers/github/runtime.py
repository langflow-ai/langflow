"""Repository webhook creation and durable remote cleanup."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from lfx.integrations.errors import ProviderUnavailableError, ResourceNotFoundError
from lfx.services.deps import session_scope_readonly
from lfx_github.client import GitHubClient, positive_id, repository_path
from sqlmodel import select

from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerSubscription
from langflow.services.triggers import leases
from langflow.services.triggers.constants import FAMILY_TRIGGER_PUSH
from langflow.services.triggers.ingress.verifiers import IngressSecrets
from langflow.services.triggers.locking import lock_trigger
from langflow.services.triggers.providers.github.config import normalize_config
from langflow.services.triggers.providers.github.credentials import validate_manual_credential
from langflow.services.triggers.providers.github.events import verify
from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider
from langflow.services.triggers.source_clients import source_lease
from langflow.services.triggers.source_errors import SourceConfigurationError
from langflow.services.triggers.source_subscription import source_ingress_url

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease
    from sqlmodel.ext.asyncio.session import AsyncSession


WEBHOOK_PAGE_SIZE = 100


def _event(trigger: Trigger) -> str:
    return "issues" if trigger.kind == "github.issue" else "pull_request"


async def _check_cleanup(session: AsyncSession, trigger: Trigger) -> None:
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


async def _reservation(session: AsyncSession, trigger: Trigger) -> TriggerSubscription | None:
    rows = (
        await session.exec(
            select(TriggerSubscription).where(
                TriggerSubscription.trigger_id == trigger.id,
                TriggerSubscription.provider == "github",
                TriggerSubscription.state != "expired",
            )
        )
    ).all()
    if len(rows) > 1:
        msg = "Multiple GitHub webhook reservations require cleanup before enabling this trigger."
        raise SourceConfigurationError(msg)
    return rows[0] if rows else None


def _matches(subscription: TriggerSubscription, trigger: Trigger, address: str) -> bool:
    return (
        subscription.connection_id == trigger.connection_id
        and subscription.provider_state.get("repository") == trigger.config["repository"]
        and subscription.provider_state.get("callback") == address
    )


async def prepare(session: AsyncSession, trigger: Trigger) -> None:
    """Reserve cleanup ownership in the committed enable transaction, before remote I/O."""
    await _check_cleanup(session, trigger)
    repository = trigger.config["repository"]
    repository_path(repository)
    address = await source_ingress_url(session, trigger)
    existing = await _reservation(session, trigger)
    if existing is not None:
        if not _matches(existing, trigger, address):
            msg = "The original GitHub webhook must be cleaned up before changing its connection or repository."
            raise SourceConfigurationError(msg)
        existing.state = "pending"
        session.add(existing)
        return
    reservation_id = uuid4()
    session.add(
        TriggerSubscription(
            id=reservation_id,
            trigger_id=trigger.id,
            connection_id=trigger.connection_id,
            provider="github",
            provider_subscription_id=f"pending:{reservation_id}",
            provider_state={"repository": repository, "callback": address},
            state="pending",
        )
    )
    await session.flush()


async def _matching_hooks(client: GitHubClient, path: str, address: str) -> list[int]:
    matches = []
    for page in range(1, 11):
        hooks = await client.request("GET", path + "/hooks", params={"per_page": WEBHOOK_PAGE_SIZE, "page": page})
        if not isinstance(hooks, list):
            raise ProviderUnavailableError(provider="github")
        matches.extend(
            positive_id(hook.get("id"))
            for hook in hooks
            if isinstance(hook, dict) and isinstance(hook.get("config"), dict) and hook["config"].get("url") == address
        )
        if len(hooks) < WEBHOOK_PAGE_SIZE:
            return matches
    msg = "The repository webhook list exceeded the bounded setup scan."
    raise SourceConfigurationError(msg)


async def provision(session: AsyncSession, trigger: Trigger) -> TriggerSubscription:
    await _check_cleanup(session, trigger)
    repository = trigger.config["repository"]
    path = repository_path(repository)
    address = await source_ingress_url(session, trigger)
    subscription = await _reservation(session, trigger)
    if subscription is None or subscription.state != "pending" or not _matches(subscription, trigger, address):
        msg = "Enable the GitHub trigger to reserve its webhook before setup."
        raise SourceConfigurationError(msg)
    expected_config = dict(trigger.config)
    if not trigger.signing_secret_encrypted:
        msg = "The GitHub webhook signing secret has not been initialized."
        raise ValueError(msg)
    signing_secret = decrypt_api_key(trigger.signing_secret_encrypted)
    lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
    async with GitHubClient(lease) as client:
        repo = await client.request("GET", path)
        if not isinstance(repo, dict) or type(repo.get("id")) is not int:
            raise ProviderUnavailableError(provider="github")
        # An earlier POST may have succeeded even when its response or local commit failed.
        matching = await _matching_hooks(client, path, address)
        if len(matching) > 1:
            msg = "Duplicate GitHub callbacks require administrator cleanup before rearming."
            raise SourceConfigurationError(msg)
        hook_id = matching[0] if matching else None
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
    # Follow the shared trigger -> subscription lock order only after provider I/O.
    current = await lock_trigger(session, trigger.id)
    subscription = await session.get(TriggerSubscription, subscription.id, populate_existing=True, with_for_update=True)
    if (
        current is None
        or current.state not in {"pending", "active"}
        or current.config != expected_config
        or subscription is None
        or subscription.state != "pending"
        or not _matches(subscription, current, address)
    ):
        msg = "GitHub webhook setup was superseded. Its original cleanup reservation is retained."
        raise SourceConfigurationError(msg)
    await _check_cleanup(session, current)
    subscription.provider_subscription_id = f"{repository}:{hook_id}"
    subscription.provider_state = {
        "repository": repository,
        "repository_id": str(repo["id"]),
        "hook_id": hook_id,
        "callback": address,
    }
    subscription.state = "active"
    session.add(subscription)
    await session.flush()
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


async def _setup_in_progress(task: TriggerCleanup) -> bool:
    async with session_scope_readonly() as session:
        return await leases.holder(session, name=f"trigger-source:{task.trigger_id}") is not None


async def revoke(task: TriggerCleanup, lease: CredentialLease) -> None:
    # Do not finish an empty scan while an initializer can still create the hook.
    if await _setup_in_progress(task):
        msg = "GitHub webhook setup is still settling. Cleanup will retry after its source lease is released."
        raise SourceConfigurationError(msg)
    path = repository_path(task.provider_state["repository"])
    address = task.provider_state.get("callback")
    if not isinstance(address, str) or not address.startswith("https://"):
        msg = "The original GitHub callback cannot be verified."
        raise SourceConfigurationError(msg)
    async with GitHubClient(lease) as client:
        if task.provider_subscription_id == f"pending:{task.id}":
            try:
                hook_ids = await _matching_hooks(client, path, address)
            except ResourceNotFoundError:
                return
        else:
            prefix = task.provider_state["repository"] + ":"
            if not task.provider_subscription_id.startswith(prefix):
                msg = "The original GitHub repository cannot be verified."
                raise SourceConfigurationError(msg)
            hook_ids = [positive_id(task.provider_subscription_id[len(prefix) :])]
        for hook_id in hook_ids:
            hook_path = path + f"/hooks/{hook_id}"
            try:
                hook = await client.request("GET", hook_path)
                if (
                    not isinstance(hook, dict)
                    or type(hook.get("id")) is not int
                    or hook["id"] != hook_id
                    or not isinstance(hook.get("config"), dict)
                    or hook["config"].get("url") != address
                ):
                    msg = "The GitHub hook no longer belongs to this callback. Administrator cleanup is required."
                    raise SourceConfigurationError(msg)
                await client.request("DELETE", hook_path)
            except ResourceNotFoundError:
                continue


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
