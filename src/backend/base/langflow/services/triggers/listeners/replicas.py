"""Which listener replicas are alive, so a loaded one can hand connections back.

``connection_leases`` elects one holder per connection, and that alone is enough
to *spread* connections that are armed while several replicas are already
running. It is not enough to *rebalance*: a lease is only observable while it is
held, so a replica that has just started holds nothing and is invisible to the
replica already holding everything. Nothing in the loaded replica's view changes
when a peer appears, so it hands nothing back - and "add a replica when one
process cannot keep up" quietly does nothing at all.

A presence row is the missing signal. Each process takes a ``trigger_lease`` row
named after its own holder token and renews it on every reconcile pass, so an
idle replica is still countable. A pass that sees ``n`` live rows knows its fair
share of the armed connections is ``ceil(total / n)`` and releases whatever it
holds above that; the peers pick the freed connections up through the ordinary
lease race on their next pass. No assignment protocol, no leader, and no new
table: the rebalance is one number computed the same way in every replica.

The row is a lease of a name only this process ever uses, so it is never
contended, and ``trigger_lease`` already carries the expiry semantics presence
needs. A replica that exits cleanly deletes its row; one that is hard-killed
leaves a row that stops counting as live after one TTL and is reaped later.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlmodel import col, delete, select

from langflow.services.database.models.trigger.model import TriggerLease
from langflow.services.triggers import leases

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

#: Presence rows share a prefix so they can be counted and reaped as a group
#: without colliding with the named singleton leases (``dispatcher``, ``purge``)
#: that live in the same table.
PRESENCE_PREFIX = "listener-replica:"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def presence_name(holder: str) -> str:
    """The ``trigger_lease`` row name this holder announces itself under.

    ``trigger_lease.name`` is ``String(64)``; a holder token is ``listener:<pid>:<8 hex>``,
    so the prefixed name fits with room to spare. It is truncated rather than
    allowed to raise, because a presence row is a scaling optimization and must
    never be the reason a listener fails to start.
    """
    return f"{PRESENCE_PREFIX}{holder}"[:64]


async def announce(session: AsyncSession, *, holder: str, ttl_s: float) -> None:
    """Take or renew this replica's presence row."""
    await leases.acquire(session, name=presence_name(holder), owner=holder, ttl_s=ttl_s)


async def live_replicas(session: AsyncSession, *, reap_after_s: float | None = None) -> int:
    """How many listener replicas are announcing themselves right now.

    Expiry is judged in Python rather than in the ``WHERE`` clause: SQLite reads
    datetimes back naive, and comparing a naive column against an aware bind
    parameter is the kind of silently-wrong that would make every replica think
    it is alone. The row count is bounded by the replica count, so reading them
    is cheap.

    Passing ``reap_after_s`` also deletes rows that have been expired for longer
    than that, which is what keeps a hard-killed replica from leaving a row
    behind forever.
    """
    rows = (await session.exec(select(TriggerLease).where(col(TriggerLease.name).like(f"{PRESENCE_PREFIX}%")))).all()
    now = _now()
    live = 0
    stale: list[str] = []
    for row in rows:
        expires_at = _as_aware(row.expires_at)
        if expires_at is not None and expires_at > now:
            live += 1
        elif reap_after_s is not None and expires_at is not None and expires_at < now - timedelta(seconds=reap_after_s):
            stale.append(row.name)
    if stale:
        await session.exec(  # type: ignore[call-overload]
            delete(TriggerLease).where(col(TriggerLease.name).in_(stale))
        )
        await session.flush()
    return live


async def withdraw(session: AsyncSession, *, holder: str) -> None:
    """Drop this replica's presence row on a clean shutdown.

    Deleted rather than expired: the name is unique to one process, so nothing
    will ever renew it again and leaving it would accumulate one dead row per
    restart. Guarded on the owner for symmetry with every other lease write.
    """
    await session.exec(  # type: ignore[call-overload]
        delete(TriggerLease).where(
            col(TriggerLease.name) == presence_name(holder),
            col(TriggerLease.owner) == holder,
        )
    )
    await session.flush()


def fair_share(*, total: int, replicas: int) -> int:
    """How many connections one replica may hold when ``replicas`` are alive.

    Rounded up, so ``n`` replicas' shares always cover the whole set: three
    replicas and thirty-one connections give eleven each, not ten and a
    connection nobody is allowed to hold. A replica that cannot see any peer -
    including itself, if its own announcement failed - keeps everything, because
    handing a connection back to nobody is strictly worse than holding it.
    """
    if replicas <= 1 or total <= 0:
        return max(total, 0)
    return max(1, math.ceil(total / replicas))
