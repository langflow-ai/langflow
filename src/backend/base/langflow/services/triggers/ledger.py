"""Append-and-read half of the trigger event ledger.

The ledger is at-least-once. Producers append freely and rely on
``uq_trigger_event_trigger_dedupe`` to collapse duplicates: a second row with
the same ``(trigger_id, dedupe_key)`` raises ``IntegrityError`` inside a
SAVEPOINT, which :func:`append_event` translates into "the row already exists"
without poisoning the caller's transaction.

The claim/lease half lives in ``dispatcher.py`` so a producer (an ingress route,
a tick) never imports the dispatch machinery.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, select

from langflow.services.database.models.trigger.model import TriggerEvent
from langflow.services.database.models.trigger.schemas import TERMINAL_EVENT_STATES, TriggerEventState
from langflow.services.triggers.constants import REPLAY_DEDUPE_PREFIX
from langflow.services.triggers.errors import ReplayWindowExpiredError, TriggerEventNotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    """Read a timestamp back as UTC-aware.

    SQLite hands back naive datetimes even for ``DateTime(timezone=True)``
    columns, so every comparison in this module goes through here.
    """
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def append_event(
    session: AsyncSession,
    *,
    trigger_id: UUID,
    dedupe_key: str,
    payload: dict[str, Any] | None = None,
    available_at: datetime | None = None,
    replay_of_event_id: UUID | None = None,
) -> tuple[TriggerEvent, bool]:
    """Append one ledger row. Returns ``(row, created)``.

    ``created`` is False when the database rejected the insert because the
    ``(trigger_id, dedupe_key)`` pair already exists — the deduplication path.
    The existing row is returned so a caller can report the original event id
    (a redelivered provider event should link to the run it already made).
    """
    event = TriggerEvent(
        trigger_id=trigger_id,
        dedupe_key=dedupe_key,
        state=TriggerEventState.PENDING.value,
        attempt=0,
        available_at=available_at or _now(),
        payload=payload or {},
        replay_of_event_id=replay_of_event_id,
    )
    try:
        async with session.begin_nested():
            session.add(event)
            await session.flush()
    except IntegrityError:
        # The unique index did its job. Nothing was written; the SAVEPOINT
        # rollback leaves the caller's transaction usable.
        existing = await get_event_by_dedupe_key(session, trigger_id=trigger_id, dedupe_key=dedupe_key)
        if existing is None:  # pragma: no cover - only reachable if the row was deleted mid-race
            raise
        await logger.adebug("Trigger %s: duplicate event %s collapsed by the ledger", trigger_id, dedupe_key)
        return existing, False
    return event, True


async def get_event_by_dedupe_key(session: AsyncSession, *, trigger_id: UUID, dedupe_key: str) -> TriggerEvent | None:
    statement = select(TriggerEvent).where(
        TriggerEvent.trigger_id == trigger_id,
        TriggerEvent.dedupe_key == dedupe_key,
    )
    return (await session.exec(statement)).first()


async def get_event(session: AsyncSession, *, trigger_id: UUID, event_id: UUID) -> TriggerEvent:
    """Fetch one ledger row scoped to its trigger (never by id alone)."""
    statement = select(TriggerEvent).where(TriggerEvent.id == event_id, TriggerEvent.trigger_id == trigger_id)
    row = (await session.exec(statement)).first()
    if row is None:
        raise TriggerEventNotFoundError(str(event_id))
    return row


async def list_events(
    session: AsyncSession,
    *,
    trigger_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[TriggerEvent]:
    statement = (
        select(TriggerEvent)
        .where(TriggerEvent.trigger_id == trigger_id)
        .order_by(col(TriggerEvent.created_at).desc(), col(TriggerEvent.id).desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await session.exec(statement)).all())


async def replay_event(
    session: AsyncSession,
    *,
    trigger_id: UUID,
    event_id: UUID,
    replay_window_days: int,
) -> TriggerEvent:
    """Append a NEW pending row carrying the original payload.

    Replay never rewinds the original row: the ledger is an audit trail. The new
    row links back through ``replay_of_event_id`` and takes a fresh dedupe key,
    so it flows through the same claim/dispatch path as a first delivery. A
    second replay of the same event is itself deduplicated, by generation.
    """
    original = await get_event(session, trigger_id=trigger_id, event_id=event_id)
    created_at = _as_aware(original.created_at)
    if created_at is not None and created_at < _now() - timedelta(days=replay_window_days):
        raise ReplayWindowExpiredError(replay_window_days)

    generation = await _replay_generation(session, trigger_id=trigger_id, event_id=event_id)
    dedupe_key = f"{REPLAY_DEDUPE_PREFIX}:{event_id}:{generation}"
    replay, _created = await append_event(
        session,
        trigger_id=trigger_id,
        dedupe_key=dedupe_key,
        payload=original.payload,
        replay_of_event_id=original.id,
    )
    return replay


async def _replay_generation(session: AsyncSession, *, trigger_id: UUID, event_id: UUID) -> int:
    """Number of replays already made of this event, so each gets a fresh key."""
    statement = select(TriggerEvent).where(
        TriggerEvent.trigger_id == trigger_id,
        TriggerEvent.replay_of_event_id == event_id,
    )
    return len((await session.exec(statement)).all())


async def purge_events(
    session: AsyncSession,
    *,
    retention_days: int,
    now: datetime | None = None,
) -> int:
    """Delete terminal ledger rows older than the retention window.

    Only terminal rows are purged: a pending or in-flight row is work that has
    not happened yet, however old it looks. Returns the number of rows removed.
    """
    cutoff = (now or _now()) - timedelta(days=retention_days)
    statement = delete(TriggerEvent).where(
        col(TriggerEvent.state).in_(sorted(TERMINAL_EVENT_STATES)),
        col(TriggerEvent.created_at) < cutoff,
    )
    result = await session.exec(statement)  # type: ignore[call-overload]
    return int(result.rowcount or 0)
