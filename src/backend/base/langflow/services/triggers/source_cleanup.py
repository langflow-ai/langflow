"""Durable, credential-free remote cleanup that survives trigger deletion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease
from lfx.log.logger import logger
from lfx.services.authorization.base import ExecutionPrincipal
from sqlmodel import col, select

from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerSubscription
from langflow.services.deps import get_connection_resolver_service, get_settings_service, session_scope
from langflow.services.triggers import leases
from langflow.services.triggers.lease_guard import run_guarded
from langflow.services.triggers.ownership import is_owned_by


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

    async with session_scope() as session:
        connection = await session.get(Connection, task.connection_id) if task.connection_id else None
        if connection is None or not is_owned_by(connection, task.user_id) or connection.provider_key != task.provider:
            msg = "The original subscription credential is unavailable."
            raise ValueError(msg)
        # This capability is created only by authenticated lifecycle operations
        # and permits this worker's fixed revocation requests, never source reads
        # or flow execution. Withdrawing background-run consent must not prevent
        # the owner from finishing deletion of an already-created watch.
        principal = ExecutionPrincipal(
            kind="flow_owner",
            user_id=str(task.user_id),
            actor_id=str(task.user_id),
            family="trigger_cleanup",
            interactive=True,
            allow_explicit_shares=False,
            actor_label="trigger subscription cleanup",
        )
        lease = CredentialLease(
            get_connection_resolver_service(),
            ConnectionResolutionRequest(
                ref=ConnectionRef(provider=connection.provider_key, name=connection.name),
                principal=principal,
            ),
        )
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
