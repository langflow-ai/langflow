"""Named singleton leases for the trigger loops.

One row in ``trigger_lease`` per loop name. A holder renews ``heartbeat_at`` and
``expires_at``; any process may take the lease once ``expires_at`` has passed.
Every mutation is a single conditional UPDATE guarded on the exact value the
caller read, so two replicas racing the same expired lease see exactly one
``rowcount == 1`` — the same primitive ``JobService.claim_queued_lease`` uses,
and portable across SQLite and Postgres.

This is what makes "exactly once per tick on three replicas" true without a
message broker: every API process may run the loops, but only the lease holder
produces ticks, and a hard kill costs at most one TTL of latency.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlmodel import select, update

from langflow.services.database.models.trigger.model import TriggerLease

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


def new_owner_token(prefix: str = "trg") -> str:
    """A process-unique owner token, stable for the life of one loop."""
    return f"{prefix}:{os.getpid()}:{uuid4().hex[:8]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def acquire(session: AsyncSession, *, name: str, owner: str, ttl_s: float) -> bool:
    """Take or renew the named lease. Returns True when this owner holds it.

    Three cases, all single-statement:

    * no row — INSERT inside a SAVEPOINT; a loser's unique-key violation is not
      an error, it means somebody else won the race this tick.
    * we already hold it — renew, guarded on ``owner``.
    * somebody else held it and it expired — steal, guarded on the exact
      ``expires_at`` we read so only one stealer wins.
    """
    now = _now()
    expires_at = now + timedelta(seconds=ttl_s)
    row = (await session.exec(select(TriggerLease).where(TriggerLease.name == name))).first()

    if row is None:
        try:
            async with session.begin_nested():
                session.add(
                    TriggerLease(name=name, owner=owner, acquired_at=now, heartbeat_at=now, expires_at=expires_at)
                )
                await session.flush()
        except IntegrityError:
            return False
        return True

    current_expiry = _as_aware(row.expires_at)
    if row.owner == owner:
        statement = (
            update(TriggerLease)
            .where(TriggerLease.name == name, TriggerLease.owner == owner)
            .values(heartbeat_at=now, expires_at=expires_at)
        )
    elif current_expiry is not None and current_expiry > now:
        # Live holder that is not us.
        return False
    else:
        statement = (
            update(TriggerLease)
            .where(TriggerLease.name == name, TriggerLease.expires_at == row.expires_at)
            .values(owner=owner, acquired_at=now, heartbeat_at=now, expires_at=expires_at)
        )
    result = await session.exec(statement)  # type: ignore[call-overload]
    await session.flush()
    return bool(result.rowcount == 1)


async def release(session: AsyncSession, *, name: str, owner: str) -> bool:
    """Give up the lease so another replica can take it immediately.

    Guarded on ``owner``: a process that already lost the lease must not expire
    the new holder's claim on its way out.
    """
    statement = (
        update(TriggerLease)
        .where(TriggerLease.name == name, TriggerLease.owner == owner)
        .values(expires_at=_now() - timedelta(seconds=1))
    )
    result = await session.exec(statement)  # type: ignore[call-overload]
    await session.flush()
    return bool(result.rowcount == 1)


async def holder(session: AsyncSession, *, name: str) -> str | None:
    """The current live holder, or None when the lease is free or expired."""
    row = (await session.exec(select(TriggerLease).where(TriggerLease.name == name))).first()
    if row is None:
        return None
    expires_at = _as_aware(row.expires_at)
    if expires_at is not None and expires_at <= _now():
        return None
    return row.owner
