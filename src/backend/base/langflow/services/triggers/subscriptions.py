"""Provider-side subscriptions, and the leased job that keeps them alive.

A push trigger only works while the provider still has a live subscription
pointing at Langflow, and every wave-1 provider expires them fast: Microsoft
Graph mail and calendar last seven days, rich notifications one day, files
thirty; Google channels and Gmail watches last seven. Nothing renews itself, so
a trigger that is not renewed ahead of expiry simply stops firing, silently.

Three ideas do the work.

**Renewal is leased, not per replica.** Every API replica may run the loop and
exactly one does at a time, held by the same ``trigger_lease`` row idiom the
dispatcher uses, so a provider never sees N renewals of one subscription. Each
row is additionally claimed with its own short lease before it is renewed, so a
slow provider call cannot be started twice inside one pass.

**The lead time follows the provider, not the clock.** ``renew_after`` is
computed from the subscription's own lifetime - half of it, capped at a day - so
a seven-day mail subscription renews a day early and a one-day rich-notification
subscription renews twelve hours early, without either one needing its own knob.

**The provider call is somebody else's.** TRG-4 owns the store, the schedule,
the lease, and the lifecycle transitions; the HTTP call that actually renews a
Graph subscription or re-creates a Google channel belongs to the provider ticket
that created it. Renewers register here, and a subscription whose provider has
no registered renewer is left alone rather than quietly marked broken - which is
the honest OSS behaviour when no provider bundle is installed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Protocol

from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.connection.schemas import PersistedConnectionStatus
from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerState, TriggerSubscriptionState
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import leases
from langflow.services.triggers.constants import (
    AUDIT_SUBSCRIPTION_RENEW,
    AUDIT_SUBSCRIPTION_REVOKE,
    SUBSCRIPTION_LEASE_NAME,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

#: Graph lifecycle events, as Graph spells them.
LIFECYCLE_REAUTHORIZATION_REQUIRED = "reauthorizationRequired"
LIFECYCLE_SUBSCRIPTION_REMOVED = "subscriptionRemoved"
LIFECYCLE_MISSED = "missed"

#: Connection states that make every subscription behind them dead.
_UNUSABLE_CONNECTION_STATUSES = frozenset(
    {PersistedConnectionStatus.REVOKED.value, PersistedConnectionStatus.EXPIRED.value}
)

#: Renewal failure bookkeeping, kept on ``provider_state`` so no migration is
#: needed and a successful renewal can clear it in one assignment.
_FAILURE_COUNT_KEY = "renew_failures"
_FAILURE_REASON_KEY = "renew_last_error"
_FAILURE_AT_KEY = "renew_last_failed_at"
_FAILURE_KEYS = frozenset({_FAILURE_COUNT_KEY, _FAILURE_REASON_KEY, _FAILURE_AT_KEY})

_NEEDS_RECONNECT_REASON = "The provider subscription needs to be re-authorized. Reconnect the connection."
_REMOVED_REASON = "The provider deleted this subscription. Re-enable the trigger to subscribe again."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class SubscriptionRenewer(Protocol):
    """One provider's renewal call.

    Returns the subscription's new expiry. Raising is how a renewer reports
    failure; the caller records it and retries on the next pass.
    """

    async def __call__(self, session: AsyncSession, subscription: TriggerSubscription) -> datetime: ...


class SubscriptionRevoker(Protocol):
    """One provider's "delete this subscription" call.

    Registered alongside the renewer and for the same reason: TRG-4 owns the
    store, the schedule, and the lifecycle transitions, while the HTTP call that
    actually deletes a Graph subscription or stops a Google channel belongs to
    the provider ticket that created it.

    Raising is not fatal. A local row is retired either way - a trigger the
    owner paused must stop accepting deliveries immediately, whatever the
    provider says - and the failure is logged so the remote object can be
    reconciled later rather than blocking the owner's action now.
    """

    async def __call__(self, session: AsyncSession, subscription: TriggerSubscription) -> None: ...


_RENEWERS: dict[str, SubscriptionRenewer] = {}
_REVOKERS: dict[str, SubscriptionRevoker] = {}


def register_renewer(provider: str, renewer: SubscriptionRenewer) -> None:
    """Register a provider's renewal call. TRG-6 supplies the wave-1 ones."""
    _RENEWERS[provider] = renewer


def unregister_renewer(provider: str) -> None:
    _RENEWERS.pop(provider, None)


def registered_renewers() -> set[str]:
    return set(_RENEWERS)


def register_revoker(provider: str, revoker: SubscriptionRevoker) -> None:
    """Register a provider's deletion call. TRG-6 supplies the wave-1 ones."""
    _REVOKERS[provider] = revoker


def unregister_revoker(provider: str) -> None:
    _REVOKERS.pop(provider, None)


def registered_revokers() -> set[str]:
    return set(_REVOKERS)


async def _revoke_remote(session: AsyncSession, row: TriggerSubscription) -> None:
    """Ask the provider to delete the subscription, best effort.

    With no registered revoker - OSS today, before TRG-6 - this is a no-op and
    the remote object is left to expire on the provider's own schedule. That is
    a real gap and it is named here rather than hidden: the local row is retired
    regardless, so Langflow stops acting on the subscription immediately, but
    the provider may keep delivering until its TTL runs out.
    """
    revoker = _REVOKERS.get(row.provider)
    if revoker is None:
        return
    try:
        await revoker(session, row)
    except Exception:  # noqa: BLE001 - the owner's pause must not depend on the provider answering
        await logger.aexception("Subscription %s could not be deleted at provider %s", row.id, row.provider)


def renew_after_for(*, created_at: datetime, expires_at: datetime) -> datetime:
    """When a subscription with this lifetime should be renewed.

    Half its lifetime, capped by the configured lead. Both bounds matter: the
    fraction keeps a short-lived subscription from being renewed at the last
    second, and the cap keeps a thirty-day subscription from being renewed
    fifteen days early and wasting fourteen days of validity.
    """
    settings = get_settings_service().settings
    lifetime = (expires_at - created_at).total_seconds()
    lead = min(lifetime * settings.trigger_subscription_renew_fraction, settings.trigger_subscription_renew_lead_cap_s)
    return expires_at - timedelta(seconds=max(lead, 0))


async def upsert_subscription(
    session: AsyncSession,
    *,
    trigger_id: UUID,
    connection_id: UUID | None,
    provider: str,
    provider_subscription_id: str,
    client_state_digest: str | None,
    expires_at: datetime,
    provider_state: dict[str, Any] | None = None,
) -> TriggerSubscription:
    """Record (or refresh) the provider-side object backing a push trigger."""
    statement = select(TriggerSubscription).where(
        TriggerSubscription.provider == provider,
        TriggerSubscription.provider_subscription_id == provider_subscription_id,
    )
    row = (await session.exec(statement)).first()
    now = _now()
    if row is None:
        row = TriggerSubscription(
            trigger_id=trigger_id,
            connection_id=connection_id,
            provider=provider,
            provider_subscription_id=provider_subscription_id,
        )
    row.client_state_digest = client_state_digest
    row.provider_state = provider_state or {}
    row.expires_at = expires_at
    row.renew_after = renew_after_for(created_at=now, expires_at=expires_at)
    row.state = TriggerSubscriptionState.ACTIVE.value
    row.updated_at = now
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _set_trigger_state(session: AsyncSession, *, trigger_id: UUID, state: str, reason: str) -> None:
    row = await session.get(Trigger, trigger_id)
    if row is None or row.state == state:
        return
    row.state = state
    row.last_error = reason
    row.updated_at = _now()
    session.add(row)
    await session.flush()


async def apply_lifecycle(session: AsyncSession, *, subscription_id: str, event: str) -> bool:
    """Act on one Graph lifecycle notification. True when something changed.

    Graph sends these instead of - not alongside - the notification you were
    expecting, so ignoring them means a trigger that has stopped firing looks
    healthy. ``reauthorizationRequired`` and ``subscriptionRemoved`` both need a
    human, so both move the trigger to ``needs_reconnect``; ``missed`` is a
    resync hint recorded on the subscription for the provider adapter to use.
    """
    statement = select(TriggerSubscription).where(
        TriggerSubscription.provider_subscription_id == subscription_id,
    )
    row = (await session.exec(statement)).first()
    if row is None:
        return False

    if event == LIFECYCLE_MISSED:
        row.provider_state = {**(row.provider_state or {}), "missed_at": _now().isoformat()}
        session.add(row)
        await session.flush()
        return True

    if event == LIFECYCLE_REAUTHORIZATION_REQUIRED:
        await _set_trigger_state(
            session, trigger_id=row.trigger_id, state=TriggerState.NEEDS_RECONNECT.value, reason=_NEEDS_RECONNECT_REASON
        )
        return True

    if event == LIFECYCLE_SUBSCRIPTION_REMOVED:
        row.state = TriggerSubscriptionState.EXPIRED.value
        row.updated_at = _now()
        session.add(row)
        await _set_trigger_state(
            session, trigger_id=row.trigger_id, state=TriggerState.NEEDS_RECONNECT.value, reason=_REMOVED_REASON
        )
        return True

    return False


async def revoke_for_trigger(session: AsyncSession, *, trigger_id: UUID) -> int:
    """Retire every subscription behind one trigger. Returns how many."""
    statement = select(TriggerSubscription).where(
        TriggerSubscription.trigger_id == trigger_id,
        TriggerSubscription.state != TriggerSubscriptionState.EXPIRED.value,
    )
    rows = (await session.exec(statement)).all()
    for row in rows:
        await _revoke_remote(session, row)
        row.state = TriggerSubscriptionState.EXPIRED.value
        row.renew_after = None
        row.updated_at = _now()
        session.add(row)
    if rows:
        await session.flush()
        await _audit_subscription(AUDIT_SUBSCRIPTION_REVOKE, trigger_id=trigger_id, count=len(rows))
    return len(rows)


async def revoke_unusable_connections(session: AsyncSession) -> int:
    """Retire subscriptions whose connection the owner revoked or let expire.

    A revoked connection cannot be renewed and its deliveries can no longer be
    acted on, so the subscription is retired and the trigger says why - rather
    than the trigger sitting in ``active`` while nothing arrives.
    """
    statement = (
        select(TriggerSubscription, Connection)
        .join(Connection, Connection.id == TriggerSubscription.connection_id)
        .where(
            TriggerSubscription.state != TriggerSubscriptionState.EXPIRED.value,
            col(Connection.status).in_(sorted(_UNUSABLE_CONNECTION_STATUSES)),
        )
    )
    retired = 0
    for subscription, _connection in (await session.exec(statement)).all():
        # Best effort only: the credential this call would need is the one the
        # owner just revoked, so it will usually fail. The local row is retired
        # regardless, which is what stops Langflow acting on it.
        await _revoke_remote(session, subscription)
        subscription.state = TriggerSubscriptionState.EXPIRED.value
        subscription.renew_after = None
        subscription.updated_at = _now()
        session.add(subscription)
        await _set_trigger_state(
            session,
            trigger_id=subscription.trigger_id,
            state=TriggerState.NEEDS_RECONNECT.value,
            reason=_NEEDS_RECONNECT_REASON,
        )
        retired += 1
    if retired:
        await session.flush()
    return retired


async def claim_due(session: AsyncSession, *, owner: str, limit: int, lease_ttl_s: float) -> list[UUID]:
    """Claim subscriptions that are due for renewal. Returns their ids.

    The claim is a guarded conditional UPDATE per row, exactly like the
    dispatcher's event claim, so a renewal in flight on one replica is invisible
    to another even inside the same pass.
    """
    from sqlmodel import update

    now = _now()
    statement = (
        select(TriggerSubscription.id)
        .where(
            TriggerSubscription.state == TriggerSubscriptionState.ACTIVE.value,
            col(TriggerSubscription.renew_after).is_not(None),
            col(TriggerSubscription.renew_after) <= now,
        )
        .order_by(col(TriggerSubscription.renew_after))
        .limit(limit)
    )
    candidates = list((await session.exec(statement)).all())
    claimed: list[UUID] = []
    for subscription_id in candidates:
        guard = update(TriggerSubscription).where(
            TriggerSubscription.id == subscription_id,
            TriggerSubscription.state == TriggerSubscriptionState.ACTIVE.value,
        )
        # Only take a row whose lease is free or expired.
        guard = guard.where(
            (col(TriggerSubscription.lease_until).is_(None)) | (col(TriggerSubscription.lease_until) <= now)
        )
        result = await session.exec(  # type: ignore[call-overload]
            guard.values(lease_owner=owner, lease_until=now + timedelta(seconds=lease_ttl_s))
        )
        if result.rowcount == 1:
            claimed.append(subscription_id)
    await session.flush()
    return claimed


async def renew_one(session: AsyncSession, *, subscription_id: UUID) -> bool:
    """Renew one claimed subscription. True when its expiry moved.

    A provider with no registered renewer is left exactly as it was - claimed,
    then released - because "no bundle installed" is not the same as "renewal
    failed", and recording it as a failure would fill an operator's audit log
    with a problem they do not have.
    """
    row = await session.get(TriggerSubscription, subscription_id)
    if row is None:
        return False
    renewer = _RENEWERS.get(row.provider)
    if renewer is None:
        row.lease_owner = None
        row.lease_until = None
        session.add(row)
        await session.flush()
        return False
    try:
        expires_at = await renewer(session, row)
    except Exception as exc:  # noqa: BLE001 - a provider failure is retried, not raised
        await _record_renewal_failure(session, row=row, exc=exc)
        return False

    expires_at = _as_aware(expires_at) or _now()
    row.expires_at = expires_at
    row.renew_after = renew_after_for(created_at=_now(), expires_at=expires_at)
    row.state = TriggerSubscriptionState.ACTIVE.value
    row.provider_state = {key: value for key, value in (row.provider_state or {}).items() if key not in _FAILURE_KEYS}
    row.lease_owner = None
    row.lease_until = None
    row.updated_at = _now()
    session.add(row)
    await session.flush()
    await _clear_renewal_error(session, trigger_id=row.trigger_id)
    await _audit_subscription(AUDIT_SUBSCRIPTION_RENEW, trigger_id=row.trigger_id, count=1)
    return True


async def _record_renewal_failure(session: AsyncSession, *, row: TriggerSubscription, exc: Exception) -> None:
    """Back off and stay claimable. Retire only once the provider has expired it.

    A transient failure must not be terminal. ``claim_due`` only claims ACTIVE
    rows and ``intake._subscription_secrets`` only reads an ACTIVE row's
    ``client_state_digest``, so moving to ERROR on the first bad renewal would
    do two things at once: stop the subscription ever being retried, and start
    rejecting deliveries that are still perfectly valid - the exact silent stop
    this module exists to prevent, arrived at from the other direction.

    So the row stays ACTIVE with ``renew_after`` pushed out by an exponential
    backoff, and only becomes ERROR once ``expires_at`` has actually passed, at
    which point there is nothing left to renew. Consecutive failures are counted
    on ``provider_state`` and surfaced on the trigger past the threshold, so an
    owner sees a subscription that is struggling before it dies.
    """
    settings = get_settings_service().settings
    failures = int((row.provider_state or {}).get(_FAILURE_COUNT_KEY, 0)) + 1
    delay = min(
        settings.trigger_subscription_retry_backoff_base_s * (2 ** (failures - 1)),
        settings.trigger_subscription_retry_backoff_cap_s,
    )
    now = _now()
    expires_at = _as_aware(row.expires_at)
    expired = expires_at is not None and expires_at <= now

    row.provider_state = {
        **(row.provider_state or {}),
        _FAILURE_COUNT_KEY: failures,
        _FAILURE_REASON_KEY: type(exc).__name__,
        _FAILURE_AT_KEY: now.isoformat(),
    }
    if expired:
        # Nothing left to renew: the provider has already dropped it, and the
        # owner has to re-subscribe. Stop spending renewal attempts on it.
        row.state = TriggerSubscriptionState.ERROR.value
        row.renew_after = None
    else:
        row.renew_after = now + timedelta(seconds=delay)
    row.lease_owner = None
    row.lease_until = None
    row.updated_at = now
    session.add(row)
    await session.flush()

    await logger.aexception(
        "Subscription %s renewal failed for provider %s (attempt %s)", row.id, row.provider, failures
    )
    if expired or failures >= settings.trigger_subscription_failure_threshold:
        await _set_trigger_error(
            session,
            trigger_id=row.trigger_id,
            message=(
                "The provider subscription behind this trigger could not be renewed after "
                f"{failures} attempts. Reconnect the connection if this persists."
            ),
        )
    await _audit_subscription(AUDIT_SUBSCRIPTION_RENEW, trigger_id=row.trigger_id, count=0, result="deny")


async def _set_trigger_error(session: AsyncSession, *, trigger_id: UUID, message: str) -> None:
    """Surface a persistent renewal problem without disarming the trigger.

    The state is left alone for the same reason TRG-3's listener leaves it
    alone: a struggling provider is not an owner misconfiguration, and taking
    the trigger out of ``active`` would stop the retry that is meant to fix it.
    """
    row = await session.get(Trigger, trigger_id)
    if row is None or row.last_error == message:
        return
    row.last_error = message
    row.updated_at = _now()
    session.add(row)
    await session.flush()


async def _clear_renewal_error(session: AsyncSession, *, trigger_id: UUID) -> None:
    """A successful renewal disproves the banner a failing one raised."""
    row = await session.get(Trigger, trigger_id)
    if row is None or not row.last_error or "could not be renewed" not in row.last_error:
        return
    row.last_error = None
    row.updated_at = _now()
    session.add(row)
    await session.flush()


async def run_renewal_pass(*, owner: str) -> int:
    """Take the renewal lease and, when held, renew everything that is due."""
    settings = get_settings_service().settings
    async with session_scope() as session:
        held = await leases.acquire(
            session, name=SUBSCRIPTION_LEASE_NAME, owner=owner, ttl_s=settings.trigger_lease_ttl_s
        )
    if not held:
        return 0

    async with session_scope() as session:
        await revoke_unusable_connections(session)
        claimed = await claim_due(
            session,
            owner=owner,
            limit=settings.trigger_subscription_max_per_poll,
            lease_ttl_s=settings.trigger_lease_ttl_s,
        )

    renewed = 0
    for subscription_id in claimed:
        # One transaction per subscription: a provider that fails on one must
        # not roll back the renewals that already succeeded.
        async with session_scope() as session:
            renewed += int(await renew_one(session, subscription_id=subscription_id))
    return renewed


async def _audit_subscription(action: str, *, trigger_id: UUID, count: int, result: str = "allow") -> None:
    from langflow.services.authorization.audit import audit_decision

    await audit_decision(
        user_id=None,
        action=action,
        obj=f"trigger:{trigger_id}",
        result=result,
        details={"subscriptions": count},
    )
