"""Reconcile project webhook creation and durable remote cleanup."""

import asyncio
import hashlib
import hmac
import re
from urllib.parse import urlsplit

import httpx
from lfx.integrations.errors import (
    ConnectionNotAuthorizedError,
    IntegrationNetworkError,
    ProviderUnavailableError,
    ResourceNotFoundError,
)
from lfx.services.deps import session_scope_readonly
from lfx_gitlab.client import GitLabClient, api_origin, positive_id
from sqlmodel import select

from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.connection.schemas import ExecutingIdentityDescriptor
from langflow.services.database.models.trigger.model import TriggerCleanup, TriggerSubscription
from langflow.services.triggers import leases
from langflow.services.triggers.constants import FAMILY_TRIGGER_PUSH
from langflow.services.triggers.ingress.verifiers import IngressSecrets
from langflow.services.triggers.providers.gitlab.config import normalize_config
from langflow.services.triggers.providers.gitlab.credentials import validate_manual_credential
from langflow.services.triggers.providers.gitlab.events import signing_token, verify
from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider
from langflow.services.triggers.source_clients import source_lease
from langflow.services.triggers.source_subscription import source_ingress_url
from langflow.services.triggers.subscriptions import upsert_subscription

WEBHOOK_PAGE_SIZE = 100


def _ownership_tag(secret, project_id, callback):
    message = f"langflow.gitlab.hook-owner.v1.{project_id}.{callback}".encode()
    return "langflow-owner-v1-" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def _intent_id(trigger_id):
    return f"pending:{trigger_id}"


async def _callback_hooks(request, path, state):
    matches = {}
    for page in range(1, 11):
        hooks = await request("GET", path + "/hooks", params={"per_page": WEBHOOK_PAGE_SIZE, "page": page})
        if not isinstance(hooks, list):
            raise ProviderUnavailableError(provider="gitlab")
        for hook in hooks:
            if not isinstance(hook, dict) or hook.get("url") != state["callback"]:
                continue
            if hook.get("description") != state["ownership_tag"]:
                msg = "The GitLab callback has no matching ownership proof and needs administrator review."
                raise ValueError(msg)
            matches[positive_id(hook.get("id"))] = hook
        if len(hooks) < WEBHOOK_PAGE_SIZE:
            return matches
    msg = "The project webhook list exceeded the bounded setup scan."
    raise ValueError(msg)


async def prepare(session, trigger):
    pending_cleanup = (
        await session.exec(
            select(TriggerCleanup.id).where(
                TriggerCleanup.trigger_id == trigger.id,
                TriggerCleanup.provider == "gitlab",
            )
        )
    ).first()
    if pending_cleanup is not None:
        msg = "Finish the previous GitLab webhook cleanup before enabling this trigger again."
        raise ValueError(msg)
    project_id = positive_id(trigger.config["project_id"])
    callback = await source_ingress_url(session, trigger)
    connection = await session.get(Connection, trigger.connection_id)
    if connection is None or connection.provider_key != "gitlab":
        raise ConnectionNotAuthorizedError(provider="gitlab")
    identity = ExecutingIdentityDescriptor.model_validate(connection.executing_identity)
    account = identity.account
    if identity.identity != "user_delegated" or account is None or account.tenant_id != api_origin():
        raise ConnectionNotAuthorizedError(provider="gitlab")
    positive_id(account.id)
    state = {
        "project_id": project_id,
        "hook_id": None,
        "callback": callback,
        "origin": api_origin(),
        "account_id": account.id,
        "ownership_tag": _ownership_tag(decrypt_api_key(trigger.signing_secret_encrypted), project_id, callback),
    }
    existing = (
        await session.exec(
            select(TriggerSubscription).where(
                TriggerSubscription.trigger_id == trigger.id,
                TriggerSubscription.provider == "gitlab",
                TriggerSubscription.state != "expired",
            )
        )
    ).first()
    if existing is not None:
        if existing.connection_id != trigger.connection_id or any(
            existing.provider_state.get(key) != value for key, value in state.items() if key != "hook_id"
        ):
            msg = "Clean up the original GitLab callback before changing its connection or project."
            raise ValueError(msg)
        return
    reservation = await upsert_subscription(
        session,
        trigger_id=trigger.id,
        connection_id=trigger.connection_id,
        provider="gitlab",
        provider_subscription_id=_intent_id(trigger.id),
        client_state_digest=None,
        expires_at=None,
        provider_state=state,
    )
    reservation.state = "pending"
    session.add(reservation)
    await session.flush()


async def provision(session, trigger):
    reservation = (
        await session.exec(
            select(TriggerSubscription).where(
                TriggerSubscription.trigger_id == trigger.id,
                TriggerSubscription.provider == "gitlab",
                TriggerSubscription.state == "pending",
            )
        )
    ).first()
    if reservation is None or reservation.connection_id != trigger.connection_id:
        msg = "Enable the GitLab trigger to reserve its callback before provisioning."
        raise ValueError(msg)
    state = dict(reservation.provider_state)
    project_id = positive_id(state["project_id"])
    address = state["callback"]
    if state["origin"] != api_origin() or project_id != positive_id(trigger.config["project_id"]):
        msg = "The original GitLab callback settings changed before provisioning."
        raise ValueError(msg)
    if not trigger.signing_secret_encrypted:
        msg = "The GitLab signing secret has not been initialized."
        raise ValueError(msg)
    if state["ownership_tag"] != _ownership_tag(decrypt_api_key(trigger.signing_secret_encrypted), project_id, address):
        msg = "The GitLab callback ownership proof changed before provisioning."
        raise ValueError(msg)
    lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
    credential = await lease.get_credential()
    if credential.account is None or credential.account.id != state["account_id"]:
        raise ConnectionNotAuthorizedError(provider="gitlab")
    path = f"/projects/{project_id}"
    async with GitLabClient(lease) as client:
        version = await client.request("GET", "/version")
        match = re.match(r"^(\d+)\.(\d+)\.", version.get("version", "")) if isinstance(version, dict) else None
        if not match or tuple(map(int, match.groups())) < (19, 1):
            msg = "Signed GitLab project triggers require GitLab 19.1 or newer."
            raise ValueError(msg)
        project = await client.request("GET", path)
        if not isinstance(project, dict) or project.get("id") != project_id:
            raise ProviderUnavailableError(provider="gitlab")
        matches = await _callback_hooks(client.request, path, state)
        if len(matches) > 1:
            msg = "Duplicate GitLab callbacks require administrator cleanup before rearming."
            raise ValueError(msg)
        hook_id = next(iter(matches), None)
        body = {
            "url": address,
            "name": f"Langflow {trigger.public_id}",
            "description": state["ownership_tag"],
            "signing_token": signing_token(decrypt_api_key(trigger.signing_secret_encrypted)),
            "token": "",
            "enable_ssl_verification": True,
            "issues_events": trigger.kind == "gitlab.issue",
            "merge_requests_events": trigger.kind == "gitlab.merge_request",
            "push_events": False,
            "confidential_issues_events": False,
            "confidential_note_events": False,
            "note_events": False,
            "custom_headers": [],
            "custom_webhook_template": "",
        }
        result = await client.request(
            "PUT" if hook_id else "POST", path + "/hooks" + (f"/{hook_id}" if hook_id else ""), body=body
        )
        if (
            not isinstance(result, dict)
            or result.get("url") != address
            or result.get("description") != state["ownership_tag"]
            or result.get("enable_ssl_verification") is not True
            or result.get("issues_events") is not body["issues_events"]
            or result.get("merge_requests_events") is not body["merge_requests_events"]
        ):
            raise ProviderUnavailableError(provider="gitlab")
        hook_id = positive_id(result.get("id"))
    # A pause or delete can retire the durable intent while provider I/O is in flight.
    await session.refresh(reservation)
    if reservation.state != "pending":
        return reservation
    reservation.provider_subscription_id = f"{project_id}:{hook_id}"
    reservation.provider_state = {**state, "hook_id": hook_id}
    reservation.state = "active"
    session.add(reservation)
    await session.flush()
    return reservation


async def ingress_secrets(session, trigger):
    subscription = (
        await session.exec(
            select(TriggerSubscription).where(
                TriggerSubscription.trigger_id == trigger.id,
                TriggerSubscription.provider == "gitlab",
                TriggerSubscription.state == "active",
            )
        )
    ).first()
    if (
        subscription is None
        or not trigger.signing_secret_encrypted
        or subscription.provider_state.get("origin") != api_origin()
    ):
        return IngressSecrets()
    return IngressSecrets(
        signing_secret=decrypt_api_key(trigger.signing_secret_encrypted),
        resource_id=str(subscription.provider_state["project_id"]),
        channel_id=subscription.provider_state["account_id"],
        target_config=dict(trigger.config),
        target_kind=trigger.kind,
    )


async def revoke(task, lease):
    state = task.provider_state
    if state.get("origin") != api_origin():
        msg = "Restore the original configured GitLab origin before remote cleanup."
        raise ValueError(msg)
    project_id = positive_id(state["project_id"])
    hook_id = positive_id(state["hook_id"]) if state.get("hook_id") is not None else None
    account_id = str(positive_id(state["account_id"]))
    expected_id = f"{project_id}:{hook_id}" if hook_id else _intent_id(task.trigger_id)
    if task.provider_subscription_id != expected_id or not isinstance(state.get("ownership_tag"), str):
        msg = "The GitLab cleanup identity is invalid."
        raise ValueError(msg)
    async with session_scope_readonly() as session:
        if await leases.holder(session, name=f"trigger-source:{task.trigger_id}") is not None:
            msg = "The GitLab activation is still in progress. Cleanup will retry after it stops."
            raise ValueError(msg)
    credential = await lease.get_credential()
    snapshot = task.encrypted_credential is not None
    if credential.provider != "gitlab" or (
        not snapshot and (credential.account is None or credential.account.id != account_id)
    ):
        raise ConnectionNotAuthorizedError(provider="gitlab")
    try:
        async with GitLabClient(lease) as client:
            token = credential.access_token.get_secret_value()

            async def request(method, path, *, params=None):
                if snapshot:
                    # The shared resolver already authenticated this exact cleanup binding and deadline.
                    return await asyncio.wait_for(
                        client._request(method, path, None, params, token),  # noqa: SLF001
                        timeout=25,
                    )
                return await client.request(method, path, params=params)

            user = await request("GET", "/user")
            if not isinstance(user, dict) or str(user.get("id")) != account_id or user.get("bot") is not False:
                raise ConnectionNotAuthorizedError(provider="gitlab")
            project_path = f"/projects/{project_id}"
            hooks = {hook_id: None} if hook_id else await _callback_hooks(request, project_path, state)
            for identifier in hooks:
                path = f"{project_path}/hooks/{identifier}"
                try:
                    hook = await request("GET", path)
                except ResourceNotFoundError:
                    continue
                if (
                    not isinstance(hook, dict)
                    or hook.get("url") != state["callback"]
                    or hook.get("description") != state["ownership_tag"]
                ):
                    msg = "The GitLab callback ownership changed and requires administrator cleanup."
                    raise ValueError(msg)
                await request("DELETE", path)
    except ResourceNotFoundError:
        return
    except (asyncio.TimeoutError, httpx.TimeoutException):
        raise IntegrationNetworkError(
            reason="timeout", provider="gitlab", host=urlsplit(api_origin()).hostname
        ) from None
    except httpx.TransportError:
        raise IntegrationNetworkError(
            reason="connection", provider="gitlab", host=urlsplit(api_origin()).hostname
        ) from None


PROVIDER = TriggerProvider(
    provider_id="gitlab",
    bundle="gitlab",
    kinds=tuple(
        TriggerKind(
            kind=f"gitlab.{kind}",
            component=f"GitLabOn{label}TriggerComponent",
            display_name=f"GitLab On {label}",
            config_fields=(
                "connection",
                "project_id",
                "actions",
                "delivery_mode",
                "include_self_events",
                "include_bot_events",
            ),
            required_scopes=("api",),
            identity="user_delegated",
            push_mechanism="gitlab.project_webhook",
        )
        for kind, label in (("issue", "Issue"), ("merge_request", "MergeRequest"))
    ),
    normalize_config=normalize_config,
    prepare=prepare,
    provision=provision,
    revoke=revoke,
    verify=verify,
    ingress_secrets=ingress_secrets,
    api_origins=(api_origin(),),
    validate_manual_credential=validate_manual_credential,
)
