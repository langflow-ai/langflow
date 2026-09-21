"""One live listener per provider connection.

``trigger_lease`` elects one holder for a *named loop*; this module elects one
holder for a *connection*. The row is keyed by ``connection_id``, so the number
of leases follows the number of connections users have armed, not the number of
replicas an operator runs.

Every mutation is one conditional UPDATE guarded on the exact value the caller
read, the same primitive ``langflow.services.triggers.leases`` uses, so two
replicas racing an expired lease see exactly one ``rowcount == 1`` on both
SQLite and PostgreSQL.

Expiry is a Langflow recovery bound and nothing more. It says the previous
holder stopped heartbeating; it does not prove that its socket closed, so an
adapter must tolerate bounded overlap during handover
(``decisions/process-model.md``, "Bounded Socket Mode overlap during handover").
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import exists, false
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, select, update

from langflow.services.database.models.trigger.model import TriggerListenerLease

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.sql.elements import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    """Read a timestamp back as UTC-aware (SQLite returns naive datetimes)."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _is_live(row: TriggerListenerLease, *, ttl_s: float, now: datetime) -> bool:
    heartbeat = _as_aware(row.heartbeat_at)
    if heartbeat is None:  # pragma: no cover - server_default always fills it
        return False
    return heartbeat + timedelta(seconds=ttl_s) > now


async def claim_generation(session: AsyncSession, *, connection_id: UUID, holder: str, ttl_s: float) -> datetime | None:
    """Take or renew the lease, returning the *generation* this holder now owns.

    ``trigger_listener_lease`` carries no ``expires_at`` column: the TTL is a
    runtime policy applied to ``heartbeat_at``, which is what lets an operator
    lengthen the TTL without a migration and without stranding rows written
    under the old one.

    The corollary is that liveness is judged by the *claimant's* TTL, not by the
    dead holder's. Every process is expected to read the same
    ``listener_lease_ttl_s``; a replica configured with a longer one simply
    waits longer before taking over, which is the safe direction.

    ``acquired_at`` is the fencing token. It is written when a lease is taken or
    stolen and left alone by every renewal, so it names one uninterrupted period
    of ownership: a holder that lost the connection and won it back gets a new
    generation, which is exactly the distinction a fence has to make. Pair it
    with :func:`held_clause` to make a write conditional on still owning it.

    Returns ``None`` when another replica holds the lease. The value is always
    UTC-aware, whatever the backend hands back (SQLite reads datetimes naive),
    so a generation read on one path compares equal to the same generation read
    on another.
    """
    now = _now()
    row = (
        await session.exec(select(TriggerListenerLease).where(TriggerListenerLease.connection_id == connection_id))
    ).first()

    if row is None:
        try:
            async with session.begin_nested():
                session.add(
                    TriggerListenerLease(connection_id=connection_id, holder=holder, acquired_at=now, heartbeat_at=now)
                )
                await session.flush()
        except IntegrityError:
            # Another replica inserted first. Not an error: it holds the lease.
            return None
        return _as_aware(now)

    if row.holder == holder:
        statement = (
            update(TriggerListenerLease)
            .where(
                TriggerListenerLease.connection_id == connection_id,
                TriggerListenerLease.holder == holder,
            )
            .values(heartbeat_at=now)
        )
        # A renewal does not start a new generation: the adapter never stopped.
        generation = _as_aware(row.acquired_at)
    elif _is_live(row, ttl_s=ttl_s, now=now):
        return None
    else:
        # Steal, guarded on the exact stale heartbeat we read so only one of
        # several replicas racing the same dead holder wins.
        statement = (
            update(TriggerListenerLease)
            .where(
                TriggerListenerLease.connection_id == connection_id,
                TriggerListenerLease.heartbeat_at == row.heartbeat_at,
                TriggerListenerLease.holder == row.holder,
            )
            .values(holder=holder, acquired_at=now, heartbeat_at=now)
        )
        generation = _as_aware(now)
    result = await session.exec(statement)  # type: ignore[call-overload]
    await session.flush()
    return generation if result.rowcount == 1 else None


async def claim(session: AsyncSession, *, connection_id: UUID, holder: str, ttl_s: float) -> bool:
    """Take or renew the lease on one connection. True when this holder has it."""
    generation = await claim_generation(session, connection_id=connection_id, holder=holder, ttl_s=ttl_s)
    return generation is not None


def held_clause(*, connection_id: UUID, holder: str, generation: datetime | None) -> ColumnElement[bool]:
    """A predicate that is true only while ``holder`` still owns ``generation``.

    Composed into another statement's ``WHERE`` so that the fence and the write
    it guards are a single atomic mutation. Lease expiry is a Langflow recovery
    bound, not proof that the previous holder stopped: without a fence, an old
    adapter can land a stale write *after* its successor saved a newer one and
    silently rewind a provider cursor. With one, the stale write matches no rows.
    """
    if generation is None:
        # No generation means no proven ownership, so nothing may be written.
        return false()
    return exists(
        select(TriggerListenerLease.connection_id).where(
            TriggerListenerLease.connection_id == connection_id,
            TriggerListenerLease.holder == holder,
            TriggerListenerLease.acquired_at == generation,
        )
    )


async def release(session: AsyncSession, *, connection_id: UUID, holder: str) -> bool:
    """Drop the lease so another replica takes over without waiting the TTL.

    Guarded on ``holder``: a replica that already lost the connection must not
    delete the new holder's row on its way out.
    """
    statement = delete(TriggerListenerLease).where(
        col(TriggerListenerLease.connection_id) == connection_id,
        col(TriggerListenerLease.holder) == holder,
    )
    result = await session.exec(statement)  # type: ignore[call-overload]
    await session.flush()
    return bool(result.rowcount == 1)


async def release_all(session: AsyncSession, *, holder: str) -> int:
    """Drop every lease this holder owns. The clean-shutdown path."""
    statement = delete(TriggerListenerLease).where(col(TriggerListenerLease.holder) == holder)
    result = await session.exec(statement)  # type: ignore[call-overload]
    await session.flush()
    return int(result.rowcount or 0)


async def current_holder(session: AsyncSession, *, connection_id: UUID, ttl_s: float) -> str | None:
    """The live holder of one connection, or None when the lease is free."""
    row = (
        await session.exec(select(TriggerListenerLease).where(TriggerListenerLease.connection_id == connection_id))
    ).first()
    if row is None or not _is_live(row, ttl_s=ttl_s, now=_now()):
        return None
    return row.holder


async def held_by(session: AsyncSession, *, holder: str, ttl_s: float) -> set[UUID]:
    """Every connection this holder currently holds a live lease on."""
    rows = (await session.exec(select(TriggerListenerLease).where(TriggerListenerLease.holder == holder))).all()
    now = _now()
    return {row.connection_id for row in rows if _is_live(row, ttl_s=ttl_s, now=now)}
