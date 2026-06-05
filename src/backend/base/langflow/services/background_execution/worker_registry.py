"""Durable worker-presence CRUD + aggregates over the ``worker_registry`` table.

The registry is the source of truth for the worker fleet: each ``langflow worker``
registers on startup, heartbeats (idle or busy) while it lives, records its current
job, and deregisters on graceful stop. The API-side metrics collector derives the
three aggregate gauges (online/busy/idle) from this table and prunes stale rows.

These methods take an ``AsyncSession`` directly and never open their own scope —
they mirror the metrics-collector query functions so the collector (which already
owns a short-lived ``session_scope()`` per tick) and the worker loop both pass the
session they hold. Where time matters, ``now`` is injected so the math is
deterministic and the caller owns the clock.

``last_heartbeat`` is a timezone-aware column, but SQLite hands it back naive. The
freshness/staleness cutoff is bound per-dialect (aware on Postgres, naive-UTC on
SQLite) — the same pattern ``duration_percentiles`` uses — so boundary rows are not
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


class WorkerRegistryService:
    """CRUD + aggregate queries for the durable ``worker_registry`` roster."""

    name = "worker_registry_service"

    async def register(self, session: AsyncSession, *, owner: str, pid: int, host: str) -> None:
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

    async def heartbeat(
        self,
        session: AsyncSession,
        *,
        owner: str,
        state: WorkerState,
        current_job_id: UUID | None,
    ) -> None:
        """Refresh ``last_heartbeat`` and set ``state`` + ``current_job_id`` for ``owner``.

        If the row is missing (e.g. pruned out from under a still-live worker), it is
        recreated — a heartbeat is a liveness signal and must not silently no-op, so a
        worker whose row was pruned reappears on its next beat. ``started_at`` is set to
        now for the recreated row since the original start time is no longer known.
        """
        now = datetime.now(timezone.utc)
        row = await session.get(WorkerRegistry, owner)
        if row is None:
            row = WorkerRegistry(
                owner=owner,
                pid=0,
                host="",
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

    async def deregister(self, session: AsyncSession, *, owner: str) -> None:
        """Delete the row for ``owner``. No-op when it is already gone (graceful stop)."""
        row = await session.get(WorkerRegistry, owner)
        if row is None:
            return
        await session.delete(row)
        await session.flush()

    async def count_by_state(self, session: AsyncSession, *, now: datetime, online_window: timedelta) -> dict[str, int]:
        """Aggregate fresh-worker counts: ``{"online", "busy", "idle"}``.

        A row is fresh (online) when ``last_heartbeat >= now - online_window``; busy is
        fresh AND ``state == BUSY``, idle is fresh AND ``state == IDLE``. Counted in SQL
        with a dialect-aware cutoff (see ``_heartbeat_cutoff``). A stale row counts
        toward none of the three.
        """
        sql_cutoff = _heartbeat_cutoff(session, now - online_window)
        fresh = col(WorkerRegistry.last_heartbeat) >= sql_cutoff

        online = (await session.exec(select(func.count()).select_from(WorkerRegistry).where(fresh))).one()
        busy = (
            await session.exec(
                select(func.count())
                .select_from(WorkerRegistry)
                .where(fresh)
                .where(WorkerRegistry.state == WorkerState.BUSY)
            )
        ).one()
        idle = (
            await session.exec(
                select(func.count())
                .select_from(WorkerRegistry)
                .where(fresh)
                .where(WorkerRegistry.state == WorkerState.IDLE)
            )
        ).one()
        return {"online": int(online), "busy": int(busy), "idle": int(idle)}

    async def prune_stale(self, session: AsyncSession, *, now: datetime, retention_s: float) -> int:
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
