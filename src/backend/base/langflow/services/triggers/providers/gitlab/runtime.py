"""Reconcile project webhook creation and durable remote cleanup."""

import asyncio
import re
from urllib.parse import urlsplit

import httpx
from lfx.integrations.errors import (
    ConnectionNotAuthorizedError,
    IntegrationNetworkError,
    ProviderUnavailableError,
    ResourceNotFoundError,
)
from lfx_gitlab.client import GitLabClient, api_origin, positive_id
from sqlmodel import select

from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.trigger.model import TriggerSubscription
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


async def provision(session, trigger):
    project_id = positive_id(trigger.config["project_id"])
    address = await source_ingress_url(session, trigger)
    if not trigger.signing_secret_encrypted:
        msg = "The GitLab signing secret has not been initialized."
        raise ValueError(msg)
    lease = await source_lease(session, trigger, family=FAMILY_TRIGGER_PUSH)
    credential = await lease.get_credential()
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
        hook_id = None
        for page in range(1, 11):
            hooks = await client.request("GET", path + "/hooks", params={"per_page": 100, "page": page})
            if not isinstance(hooks, list):
                raise ProviderUnavailableError(provider="gitlab")
            matches = [hook for hook in hooks if isinstance(hook, dict) and hook.get("url") == address]
            if len(matches) > 1 or (matches and hook_id is not None):
                msg = "Duplicate GitLab callbacks require administrator cleanup before rearming."
                raise ValueError(msg)
            if matches:
                hook_id = positive_id(matches[0].get("id"))
            if len(hooks) < WEBHOOK_PAGE_SIZE:
                break
        else:
            msg = "The project webhook list exceeded the bounded setup scan."
            raise ValueError(msg)
        body = {
            "url": address,
            "name": f"Langflow {trigger.public_id}",
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
            or result.get("enable_ssl_verification") is not True
            or result.get("issues_events") is not body["issues_events"]
            or result.get("merge_requests_events") is not body["merge_requests_events"]
        ):
            raise ProviderUnavailableError(provider="gitlab")
        hook_id = positive_id(result.get("id"))
    return await upsert_subscription(
        session,
        trigger_id=trigger.id,
        connection_id=trigger.connection_id,
        provider="gitlab",
        provider_subscription_id=f"{project_id}:{hook_id}",
        client_state_digest=None,
        expires_at=None,
        provider_state={
            "project_id": project_id,
            "hook_id": hook_id,
            "callback": address,
            "origin": api_origin(),
            "account_id": credential.account.id,
        },
    )


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
    hook_id = positive_id(state["hook_id"])
    account_id = str(positive_id(state["account_id"]))
    if task.provider_subscription_id != f"{project_id}:{hook_id}":
        msg = "The GitLab cleanup identity is invalid."
        raise ValueError(msg)
    path = f"/projects/{project_id}/hooks/{hook_id}"
    credential = await lease.get_credential()
    snapshot = task.encrypted_credential is not None
    if credential.provider != "gitlab" or (
        not snapshot and (credential.account is None or credential.account.id != account_id)
    ):
        raise ConnectionNotAuthorizedError(provider="gitlab")
    try:
        async with GitLabClient(lease) as client:
            if snapshot:
                # The shared resolver has already authenticated this exact cleanup binding and deadline.
                # The retained token can only prove its user and read or delete the recorded callback.
                token = credential.access_token.get_secret_value()
                user = await asyncio.wait_for(client._request("GET", "/user", None, None, token), timeout=25)  # noqa: SLF001
                if not isinstance(user, dict) or str(user.get("id")) != account_id or user.get("bot") is not False:
                    raise ConnectionNotAuthorizedError(provider="gitlab")
                hook = await asyncio.wait_for(client._request("GET", path, None, None, token), timeout=25)  # noqa: SLF001
            else:
                hook = await client.request("GET", path)
            if not isinstance(hook, dict) or hook.get("url") != state.get("callback"):
                msg = "The GitLab webhook callback changed and requires administrator cleanup."
                raise ValueError(msg)
            if snapshot:
                await asyncio.wait_for(client._request("DELETE", path, None, None, token), timeout=25)  # noqa: SLF001
            else:
                await client.request("DELETE", path)
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
    provision=provision,
    revoke=revoke,
    verify=verify,
    ingress_secrets=ingress_secrets,
    api_origins=(api_origin(),),
    validate_manual_credential=validate_manual_credential,
)
