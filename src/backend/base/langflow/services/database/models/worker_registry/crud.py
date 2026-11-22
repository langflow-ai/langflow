"""Durable worker-presence CRUD + aggregates over the ``worker_registry`` table.

The registry is the source of truth for the worker fleet: each ``langflow worker``
registers on startup, heartbeats (idle or busy) while it lives, records its current
job, and deregisters on graceful stop. The API-side metrics collector derives the
three aggregate gauges (online/busy/idle) from this table and prunes stale rows.

These take an ``AsyncSession`` directly and never open their own scope, the same
way the sibling job aggregates in ``jobs/metrics.py`` do: the collector already
owns a short-lived ``session_scope()`` per tick, and the worker loop opens one per
beat, so both pass the session they hold. Where time matters, ``now`` is injected so the math is
deterministic and the caller owns the clock.

``last_heartbeat`` is a timezone-aware column, but SQLite hands it back naive. The
freshness/staleness cutoff is bound per-dialect (aware on Postgres, naive-UTC on
SQLite), the same pattern ``duration_percentiles`` uses, so boundary rows are not
dropped by a lexicographic mismatch on SQLite.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlmodel import col, func, select

from langflow.services.database.models.worker_registry.model import WorkerRegistry, WorkerState

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


def _heartbeat_cutoff(session: AsyncSession, cutoff: datetime) -> datetime:
    """Bind a ``last_heartbeat`` cutoff in the form the stored column uses.

    Postgres stores ``last_heartbeat`` tz-aware (an aware cutoff compares
    correctly); SQLite stores it as a naive ISO string (comparing against an
    aware ``+00:00`` cutoff is a lexicographic mismatch that can drop boundary
    rows), so SQLite gets a naive-UTC cutoff that matches the stored format.
    """
    dialect = session.get_bind().dialect.name
    return cutoff if dialect == "postgresql" else cutoff.replace(tzinfo=None)


async def register_worker(session: AsyncSession, *, owner: str, pid: int, host: str) -> None:
    """Upsert a fresh IDLE row for ``owner``.

    Idempotent for an existing owner: re-registering (e.g. after a restart that
    reused the owner, or a recovered row) updates pid/host/started_at/last_heartbeat
    and resets state to IDLE with no current job, rather than raising on the PK.
    ``state`` is always set explicitly because the model has no default.
    """
    now = datetime.now(timezone.utc)
    row = await session.get(WorkerRegistry, owner)
    if row is None:
        row = WorkerRegistry(
            owner=owner,
            pid=pid,
            host=host,
            started_at=now,
            last_heartbeat=now,
            state=WorkerState.IDLE,
            current_job_id=None,
        )
    else:
        row.pid = pid
        row.host = host
        row.started_at = now
        row.last_heartbeat = now
        row.state = WorkerState.IDLE
        row.current_job_id = None
    session.add(row)
    await session.flush()


async def heartbeat_worker(
    session: AsyncSession,
    *,
    owner: str,
    state: WorkerState,
    current_job_id: UUID | None,
    pid: int,
    host: str,
) -> None:
    """Refresh ``last_heartbeat`` and set ``state`` + ``current_job_id`` for ``owner``.

    If the row is missing (e.g. pruned out from under a still-live worker), it is
    recreated, because a heartbeat is a liveness signal and must not silently no-op, so a
    worker whose row was pruned reappears on its next beat. ``started_at`` is set to
    now for the recreated row since the original start time is no longer known.

    ``pid`` / ``host`` are only used for that recreate, and they are required
    rather than defaulted so a row naming a process that does not exist cannot
    be constructed at all. They are ignored when the row is already there,
    since the row the worker registered already carries the real values.
    """
    now = datetime.now(timezone.utc)
    row = await session.get(WorkerRegistry, owner)
    if row is None:
        row = WorkerRegistry(
            owner=owner,
            pid=pid,
            host=host,
            started_at=now,
            last_heartbeat=now,
            state=state,
            current_job_id=current_job_id,
        )
    else:
        row.last_heartbeat = now
        row.state = state
        row.current_job_id = current_job_id
    session.add(row)
    await session.flush()


async def deregister_worker(session: AsyncSession, *, owner: str) -> None:
    """Delete the row for ``owner``. No-op when it is already gone (graceful stop)."""
    row = await session.get(WorkerRegistry, owner)
    if row is None:
        return
    await session.delete(row)
    await session.flush()


async def count_workers_by_state(session: AsyncSession, *, now: datetime, online_window: timedelta) -> dict[str, int]:
    """Aggregate fresh-worker counts: ``{"online", "busy", "idle"}``.

    A row is fresh (online) when ``last_heartbeat >= now - online_window``.
    Counted with one GROUP BY, the shape ``count_nonterminal_jobs`` already
    uses, and zero-filled over the canonical states so one that empties
    reports 0 rather than vanishing. A stale row counts toward none of them.

    ``online`` is the sum of those states rather than its own query:
    ``state`` is NOT NULL with exactly two members, so the states partition
    the fresh rows. A separate COUNT could only ever agree with them, and a
    later edit to one statement would let the two drift apart silently.
    """
    sql_cutoff = _heartbeat_cutoff(session, now - online_window)
    stmt = (
        select(WorkerRegistry.state, func.count())
        .where(col(WorkerRegistry.last_heartbeat) >= sql_cutoff)
        .group_by(col(WorkerRegistry.state))
    )
    counts = {state.value: 0 for state in WorkerState}
    for state, count in (await session.exec(stmt)).all():
        # SQLite hands back the raw string where Postgres hands back the enum.
        counts[state.value if isinstance(state, WorkerState) else str(state)] = int(count)
    return {"online": sum(counts.values()), **counts}


async def prune_stale_workers(session: AsyncSession, *, now: datetime, retention_s: float) -> int:
    """Delete rows whose ``last_heartbeat`` is older than ``retention_s``; return the count.

    A crashed worker leaves a stale row behind; once it is older than the retention
    window it is removed so the roster does not accumulate dead owners across
    restarts. Uses the same dialect-aware cutoff as ``count_by_state``.
    """
    sql_cutoff = _heartbeat_cutoff(session, now - timedelta(seconds=retention_s))
    stale = col(WorkerRegistry.last_heartbeat) < sql_cutoff
    result = await session.exec(select(WorkerRegistry).where(stale))
    rows = list(result.all())
    for row in rows:
        await session.delete(row)
    await session.flush()
    return len(rows)
