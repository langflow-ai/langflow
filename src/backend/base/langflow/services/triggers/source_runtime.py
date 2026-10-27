"""Source I/O orchestration with short, independent database transactions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from lfx.integrations.errors import ConnectionUnresolvedError
from lfx.services.deps import session_scope_readonly
from sqlmodel import update

from langflow.services.database.models.trigger.model import Trigger
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import leases
from langflow.services.triggers.constants import FAMILY_TRIGGER_PUSH
from langflow.services.triggers.lease_guard import LeaseLostError, run_guarded
from langflow.services.triggers.listeners.supervisor import is_local_configuration_failure
from langflow.services.triggers.source_errors import SourceConfigurationError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


def source_failure_detail(exc: BaseException) -> str:
    """Expose operator guidance only for known local reasons; keep provider details private."""
    if isinstance(exc, SourceConfigurationError):
        return str(exc).removesuffix(".")
    if isinstance(exc, ConnectionUnresolvedError) and is_local_configuration_failure(exc):
        return (
            f"{type(exc).__name__} ({exc.reason}). The source worker must use the same LANGFLOW_SECRET_KEY and "
            "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS as the Langflow API"
        )
    return type(exc).__name__


async def _clear_source_reconciliation_error(
    session: AsyncSession, *, trigger_id: UUID, observed_error: str | None
) -> None:
    """Clear the pre-I/O source failure without erasing a concurrent error."""
    if not (observed_error or "").startswith("Source reconciliation failed:"):
        return
    await session.exec(
        update(Trigger)
        .where(
            Trigger.id == trigger_id,
            Trigger.state == "active",
            Trigger.last_error == observed_error,
        )
        .values(last_error=None)
        .execution_options(synchronize_session=False)
    )


async def sync_source(trigger_id: UUID) -> int:
    """Collect without a database transaction; atomically commit items and cursor."""
    from langflow.services.triggers.source_clients import source_lease
    from langflow.services.triggers.source_poll import collect_source, commit_source

    async with session_scope_readonly() as session:
        row = await session.get(Trigger, trigger_id)
        if row is None or row.state not in {"active", "pending"}:
            return 0
        from langflow.services.triggers.providers.registry import get_kind, get_provider

        extension = get_provider(row.provider or "")
        if extension is not None:
            spec = get_kind(row.kind)
            if extension.collect is None or (
                spec is not None
                and (row.config or {}).get("mechanism_id") == spec.push_mechanism
                and not extension.ingress_is_hint
            ):
                return 0
        lease = await source_lease(session, row, family=FAMILY_TRIGGER_PUSH)
        snapshot = Trigger(**row.model_dump())
    result = await collect_source(snapshot, lease)
    async with session_scope() as session:
        return await commit_source(session, trigger_id=trigger_id, source_round=result)


async def ensure_subscription(trigger_id: UUID) -> None:
    """Provision in a fresh transaction with no preceding trigger writes."""
    from langflow.services.triggers.source_subscription import provision_source

    async with session_scope_readonly() as session:
        row = await session.get(Trigger, trigger_id)
        if row is None or row.state not in {"active", "pending"}:
            return
        gmail = row.kind == "google.gmail"
        key = None
        if gmail:
            from langflow.services.triggers.source_clients import source_lease

            lease = await source_lease(session, row, family=FAMILY_TRIGGER_PUSH)
    if gmail:
        from langflow.services.triggers.source_subscription import gmail_mailbox_key

        key = await gmail_mailbox_key(lease)

    async def provision():
        from sqlmodel import select

        from langflow.services.database.models.trigger.model import TriggerSubscription
        from langflow.services.triggers.subscriptions import revoke_for_trigger

        async with session_scope() as session:
            row = await session.get(Trigger, trigger_id)
            if row is None or row.state not in {"active", "pending"}:
                return
            existing = (
                await session.exec(
                    select(TriggerSubscription).where(
                        TriggerSubscription.trigger_id == trigger_id,
                        TriggerSubscription.state == "active",
                    )
                )
            ).first()
            expiry = existing.expires_at if existing is not None else None
            if expiry is not None and expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if existing is not None and (
                existing.connection_id != row.connection_id
                or (expiry is not None and expiry <= datetime.now(timezone.utc))
            ):
                await revoke_for_trigger(session, trigger_id=trigger_id)
        async with session_scope() as session:
            row = await session.get(Trigger, trigger_id)
            if row is None or row.state not in {"active", "pending"}:
                return
            expected = dict(row.config or {})
            if key:
                session.info["gmail_mailbox_key"] = key
            subscription = await provision_source(session, row)
            await session.refresh(row)
            if row.config != expected or row.state not in {"active", "pending"}:
                # Preserve compensation even if a pause raced the remote create.
                from langflow.services.triggers.source_cleanup import enqueue_cleanup

                if subscription is not None:
                    await enqueue_cleanup(session, subscription)
                    subscription.state = "expired"
                    subscription.renew_after = None
                    session.add(subscription)

    if key:
        from langflow.services.triggers.source_cleanup import with_mailbox_lease

        await with_mailbox_lease(key, provision)
    else:
        await provision()


async def initialize_source(trigger_id: UUID) -> None:
    """Finish a persisted pending activation; failed stages remain retryable."""
    owner = leases.new_owner_token("source-enable")
    name = f"trigger-source:{trigger_id}"
    ttl = get_settings_service().settings.trigger_lease_ttl_s
    async with session_scope() as session:
        if not await leases.acquire(session, name=name, owner=owner, ttl_s=ttl):
            msg = "This source is already being enabled. Check its status before retrying."
            raise SourceConfigurationError(msg)
        row = await session.get(Trigger, trigger_id)
        if row is None:
            await leases.forget(session, name=name, owner=owner)
            return
        expected = dict(row.config or {})

    async def initialize():
        await sync_source(trigger_id)
        await ensure_subscription(trigger_id)
        await sync_source(trigger_id)
        async with session_scope() as session:
            if not await leases.fence(session, name=name, owner=owner):
                msg = "Source activation lost its lease."
                raise LeaseLostError(msg)
            row = await session.get(Trigger, trigger_id, populate_existing=True, with_for_update=True)
            if row is None or row.config != expected or row.state != "pending":
                msg = "Source settings or state changed during activation. Enable it again."
                raise SourceConfigurationError(msg)
            row.state = "active"
            row.last_error = None
            session.add(row)

    try:
        await run_guarded(initialize(), name=name, owner=owner, ttl_s=ttl)
    except Exception as exc:
        async with session_scope() as session:
            owned = await leases.fence(session, name=name, owner=owner)
            row = await session.get(Trigger, trigger_id)
            if owned and row is not None and row.state == "pending":
                row.state = "error"
                row.last_error = f"Source activation failed: {source_failure_detail(exc)}. Enable the trigger to retry."
                session.add(row)
        if isinstance(exc, ValueError):
            raise
        msg = "Source activation failed. Check the trigger status and retry."
        raise ValueError(msg) from exc
    finally:
        async with session_scope() as session:
            await leases.forget(session, name=name, owner=owner)


async def mark_interrupted_activations(*, limit: int = 5) -> None:
    """Expose abandoned push setup without arming nodes that were only saved."""
    from sqlmodel import col, select

    from langflow.services.database.models.trigger.model import TriggerSubscription
    from langflow.services.triggers.providers.registry import push_mechanisms, source_kinds

    ttl = get_settings_service().settings.trigger_lease_ttl_s
    stale_before = datetime.now(timezone.utc) - timedelta(seconds=ttl)
    async with session_scope_readonly() as session:
        ids = (
            await session.exec(
                select(Trigger.id)
                .join(TriggerSubscription, TriggerSubscription.trigger_id == Trigger.id)
                .where(
                    Trigger.state == "pending",
                    col(Trigger.kind).in_(source_kinds()),
                    Trigger.config["mechanism_id"].as_string().in_(push_mechanisms()),
                    TriggerSubscription.provider == Trigger.provider,
                    col(TriggerSubscription.state).in_({"pending", "active"}),
                    Trigger.updated_at <= stale_before,
                )
                .distinct()
                .limit(limit)
            )
        ).all()
    for trigger_id in ids:
        name = f"trigger-source:{trigger_id}"
        owner = leases.new_owner_token("source-interrupted")
        async with session_scope() as session:
            if not await leases.acquire(session, name=name, owner=owner, ttl_s=ttl):
                continue
            await session.exec(
                update(Trigger)
                .where(Trigger.id == trigger_id, Trigger.state == "pending", Trigger.updated_at <= stale_before)
                .values(state="error", last_error="Source activation was interrupted. Enable the trigger to retry.")
                .execution_options(synchronize_session=False)
            )
            await leases.forget(session, name=name, owner=owner)


async def reconcile_source(trigger_id: UUID, *, repair_subscription: bool = False) -> int:
    """Serialize recovery with interactive activation on every replica."""
    name = f"trigger-source:{trigger_id}"
    owner = leases.new_owner_token("source-reconcile")
    ttl = get_settings_service().settings.trigger_lease_ttl_s
    async with session_scope() as session:
        if not await leases.acquire(session, name=name, owner=owner, ttl_s=ttl):
            msg = "Source activation or recovery is already in progress."
            raise SourceConfigurationError(msg)
        row = await session.get(Trigger, trigger_id)
        observed_error = row.last_error if row is not None else None

    async def reconcile():
        created = await sync_source(trigger_id)
        if repair_subscription:
            await ensure_subscription(trigger_id)
        async with session_scope() as session:
            if not await leases.fence(session, name=name, owner=owner):
                msg = "Source reconciliation lost its lease."
                raise LeaseLostError(msg)
            await _clear_source_reconciliation_error(session, trigger_id=trigger_id, observed_error=observed_error)
        return created

    try:
        return await run_guarded(reconcile(), name=name, owner=owner, ttl_s=ttl)
    finally:
        async with session_scope() as session:
            await leases.forget(session, name=name, owner=owner)
