"""Durable, fixed-operation remote cleanup that survives owner deletion."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx
from lfx.integrations.errors import AuthExpiredError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease, ResolvedCredential
from lfx.log.logger import logger
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import SecretStr
from sqlalchemy import or_
from sqlmodel import col, select, update

from langflow.services.connection.service import (
    ConnectionSecretError,
    _decrypt_credential_payload,
    _encrypt_credential_payload,
    _parse_expiry,
    enforce_integration_policy_for_provider,
)
from langflow.services.database.models.connection.model import Connection, ConnectionSecret
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerSubscription
from langflow.services.deps import get_connection_resolver_service, get_settings_service, session_scope
from langflow.services.triggers import leases
from langflow.services.triggers.lease_guard import run_guarded
from langflow.services.triggers.ownership import is_owned_by

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.integrations.models import ConnectionStatus
    from sqlmodel.ext.asyncio.session import AsyncSession

# Cleanup never retains refresh tokens or extends the deleted owner's access.
_CREDENTIAL_RETENTION = timedelta(hours=1)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _credential_binding(task: TriggerCleanup) -> dict:
    return {
        "id": str(task.id),
        "user_id": str(task.user_id),
        "connection_id": str(task.connection_id),
        "provider": task.provider,
        "kind": task.kind,
        "provider_subscription_id": task.provider_subscription_id,
        "provider_state": task.provider_state,
    }


async def preserve_user_cleanup_credentials(session: AsyncSession, *, user_id: UUID) -> None:
    """Seal valid access tokens for outstanding intents before owner cascades.

    Read/decrypt only: resolving a credential here could refresh OAuth while a
    deletion writer is open. Expired or revoked credentials leave cleanup to
    provider expiration. Neither refresh tokens nor consent bindings survive.
    """
    await session.flush()
    tasks = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.user_id == user_id))).all()
    now = datetime.now(timezone.utc)
    for task in tasks:
        if task.encrypted_credential is not None or task.connection_id is None:
            continue
        connection = await session.get(Connection, task.connection_id)
        if (
            connection is None
            or not is_owned_by(connection, user_id)
            or connection.provider_key != task.provider
            or connection.status in {"revoked", "expired"}
        ):
            continue
        secret = await session.get(ConnectionSecret, connection.id)
        if secret is None:
            continue
        try:
            payload = _decrypt_credential_payload(secret.encrypted_payload)
            token_expiry = _parse_expiry(payload.get("expires_at"))
            deadline = min(
                now + _CREDENTIAL_RETENTION,
                token_expiry or now + _CREDENTIAL_RETENTION,
                _aware(task.expires_at) if task.expires_at else now + _CREDENTIAL_RETENTION,
            )
            if deadline <= now:
                continue
            task.encrypted_credential = _encrypt_credential_payload(
                json.dumps(
                    {
                        "version": 1,
                        "access_token": payload["access_token"],
                        "expires_at": deadline.isoformat(),
                        "cleanup_binding": _credential_binding(task),
                    }
                )
            )
            task.credential_expires_at = deadline
            # Attempt while the retained access token is still usable, even if
            # a previous failure had moved the intent into a later retry slot.
            task.available_at = now
            session.add(task)
        except ConnectionSecretError:
            await logger.awarning("Trigger cleanup %s could not retain a usable access token", task.id)
    await session.flush()


class _CleanupSnapshotResolver:
    """An unrefreshable credential capability confined to one cleanup intent."""

    def __init__(self, task: TriggerCleanup) -> None:
        self._task = task

    async def describe(self, ref: ConnectionRef, principal: ExecutionPrincipal) -> ConnectionStatus | None:  # noqa: ARG002
        return None

    async def resolve(self, request: ConnectionResolutionRequest) -> ResolvedCredential:
        task = self._task
        if (
            request.principal.family != "trigger_cleanup"
            or request.principal.user_id != str(task.user_id)
            or request.ref.provider != task.provider
            or request.rejected_token_digest is not None
        ):
            raise AuthExpiredError(provider=task.provider)
        await enforce_integration_policy_for_provider(task.provider, user_id=str(task.user_id))
        payload = _decrypt_credential_payload(task.encrypted_credential or "")
        expiry = _parse_expiry(payload.get("expires_at"))
        if (
            payload.get("cleanup_binding") != _credential_binding(task)
            or expiry is None
            or task.credential_expires_at is None
            or expiry != _aware(task.credential_expires_at)
            or expiry <= datetime.now(timezone.utc)
        ):
            raise AuthExpiredError(provider=task.provider)
        return ResolvedCredential(
            access_token=SecretStr(payload["access_token"]),
            expires_at=expiry,
            connection_id=str(task.connection_id),
            provider=task.provider,
            name=request.ref.name,
            owner_kind="user",
        )


async def _cleanup_lease(task: TriggerCleanup) -> CredentialLease:
    # Created only by authenticated lifecycle operations; this worker exposes
    # fixed revocations, never source reads or flow execution.
    principal = ExecutionPrincipal(
        kind="flow_owner",
        user_id=str(task.user_id),
        actor_id=str(task.user_id),
        family="trigger_cleanup",
        interactive=True,
        allow_explicit_shares=False,
        actor_label="trigger subscription cleanup",
    )
    if task.encrypted_credential is not None:
        return CredentialLease(
            _CleanupSnapshotResolver(task),
            ConnectionResolutionRequest(ref=ConnectionRef(provider=task.provider, name="cleanup"), principal=principal),
        )
    async with session_scope() as session:
        connection = await session.get(Connection, task.connection_id) if task.connection_id else None
        if connection is None or not is_owned_by(connection, task.user_id) or connection.provider_key != task.provider:
            msg = "The original subscription credential is unavailable."
            raise ValueError(msg)
        return CredentialLease(
            get_connection_resolver_service(),
            ConnectionResolutionRequest(
                ref=ConnectionRef(provider=connection.provider_key, name=connection.name), principal=principal
            ),
        )


async def enqueue_cleanup(session, subscription: TriggerSubscription) -> None:
    """Record only provider identifiers; never copy credential material."""
    if await session.get(TriggerCleanup, subscription.id) is not None:
        return
    trigger = await session.get(Trigger, subscription.trigger_id)
    if trigger is None:
        return
    connection_id = subscription.connection_id or trigger.connection_id
    session.add(
        TriggerCleanup(
            id=subscription.id,
            trigger_id=trigger.id,
            connection_id=connection_id,
            user_id=trigger.user_id,
            provider=subscription.provider,
            kind=trigger.kind,
            provider_subscription_id=subscription.provider_subscription_id,
            provider_state=dict(subscription.provider_state or {}),
            expires_at=subscription.expires_at,
        )
    )


async def _revoke(task: TriggerCleanup) -> None:
    try:
        await _revoke_existing(task)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in {404, 410}:
            raise


async def _revoke_existing(task: TriggerCleanup) -> None:
    from langflow.services.triggers.source_clients import (
        GOOGLE_CALENDAR_ORIGIN,
        GOOGLE_DRIVE_ORIGIN,
        GOOGLE_GMAIL_ORIGIN,
        GRAPH_ORIGIN,
        SourceHTTP,
    )
    from langflow.services.triggers.source_subscription import gmail_mailbox_key

    lease = await _cleanup_lease(task)
    if task.provider == "microsoft":
        async with SourceHTTP(lease, origin=GRAPH_ORIGIN) as client:
            await client.request("DELETE", f"v1.0/subscriptions/{quote(task.provider_subscription_id, safe='')}")
    elif task.kind == "google.gmail":
        key = await gmail_mailbox_key(lease)
        if task.provider_state.get("mailbox_key") != key:
            # Legacy watches or a reauthorized connection must not stop an
            # unrelated account. They expire at their provider-side deadline.
            msg = "The original Gmail mailbox identity cannot be verified."
            raise ValueError(msg)

        async def stop_mailbox():
            async with session_scope() as session:
                siblings = (
                    await session.exec(
                        select(TriggerSubscription).where(
                            TriggerSubscription.provider == "google",
                            TriggerSubscription.state == "active",
                        )
                    )
                ).all()
                if any((row.provider_state or {}).get("mailbox_key") == key for row in siblings):
                    return
            async with SourceHTTP(lease, origin=GOOGLE_GMAIL_ORIGIN) as client:
                await client.request("POST", "gmail/v1/users/me/stop")

        await with_mailbox_lease(key, stop_mailbox)
    else:
        resource = task.provider_state.get("resource_id")
        if resource:
            calendar = task.kind == "google.calendar"
            async with SourceHTTP(lease, origin=GOOGLE_CALENDAR_ORIGIN if calendar else GOOGLE_DRIVE_ORIGIN) as client:
                await client.request(
                    "POST",
                    "calendar/v3/channels/stop" if calendar else "drive/v3/channels/stop",
                    body={"id": task.provider_subscription_id, "resourceId": resource},
                )


async def with_mailbox_lease(key, work):
    """Serialize watch changes across connections to the same provider mailbox."""
    name = f"gm:{key[:60]}"  # Keep the lease name within its 64-character database column.
    owner = leases.new_owner_token("mailbox")
    ttl = get_settings_service().settings.trigger_lease_ttl_s
    async with session_scope() as session:
        if not await leases.acquire(session, name=name, owner=owner, ttl_s=ttl):
            msg = "This mailbox watch is being changed. Retry shortly."
            raise ValueError(msg)
    try:
        return await run_guarded(work(), name=name, owner=owner, ttl_s=ttl)
    finally:
        async with session_scope() as session:
            await leases.forget(session, name=name, owner=owner)


async def run_cleanup_pass(*, limit: int = 25) -> int:
    """Retry cleanup without a trigger row or an open writer during provider I/O."""
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        # Purge independently of available_at: retry backoff must never extend
        # credential retention. The non-secret intent can await provider TTL.
        await session.exec(
            update(TriggerCleanup)
            .where(
                col(TriggerCleanup.encrypted_credential).is_not(None),
                or_(TriggerCleanup.credential_expires_at <= now, col(TriggerCleanup.credential_expires_at).is_(None)),
            )
            .values(encrypted_credential=None, credential_expires_at=None)
        )
        ids = (
            await session.exec(
                select(TriggerCleanup.id)
                .where(TriggerCleanup.available_at <= now)
                .order_by(col(TriggerCleanup.available_at))
                .limit(limit)
            )
        ).all()
    completed = 0
    for task_id in ids:
        owner = leases.new_owner_token("cleanup")
        name = f"trigger-cleanup:{task_id}"
        ttl = get_settings_service().settings.trigger_lease_ttl_s
        async with session_scope() as session:
            if not await leases.acquire(session, name=name, owner=owner, ttl_s=ttl):
                continue
            task = await session.get(TriggerCleanup, task_id)
        if task is None:
            async with session_scope() as session:
                await leases.forget(session, name=name, owner=owner)
            continue
        try:
            expiry = task.expires_at
            expiry = expiry.replace(tzinfo=timezone.utc) if expiry and not expiry.tzinfo else expiry
            if expiry is None or expiry > now:
                await run_guarded(_revoke(task), name=name, owner=owner, ttl_s=ttl)
        except Exception as exc:  # noqa: BLE001 - durable cleanup is retryable
            await logger.awarning("Trigger remote cleanup %s failed: %s", task_id, type(exc).__name__)
            async with session_scope() as session:
                if not await leases.fence(session, name=name, owner=owner):
                    continue
                current = await session.get(TriggerCleanup, task_id)
                if current is not None:
                    current.attempt += 1
                    current.last_error = type(exc).__name__
                    current.available_at = datetime.now(timezone.utc) + timedelta(
                        seconds=min(60 * 2 ** min(current.attempt, 6), 3600)
                    )
                    session.add(current)
        else:
            async with session_scope() as session:
                if not await leases.fence(session, name=name, owner=owner):
                    continue
                current = await session.get(TriggerCleanup, task_id)
                if current is not None:
                    await session.delete(current)
            completed += 1
        finally:
            async with session_scope() as session:
                await leases.forget(session, name=name, owner=owner)
    return completed
