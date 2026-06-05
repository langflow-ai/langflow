"""DB-derived metric queries for background execution observability.

Pure, read-only aggregates over the durable job model. Each function takes a
session and (where time matters) an injected ``now`` so the math is
deterministic in tests and the loop owns the clock. No side effects, no gauge
writes — Task 7 wires these into the OTel gauges.

``now`` is timezone-aware UTC. ``created_timestamp`` is stored as a
timezone-aware column, but SQLite hands it back naive; we normalize to aware
UTC before subtracting so the math is valid on both SQLite and Postgres.

The "alive" worker definition reuses ``JobService.is_lease_stale`` semantics so
it matches the watchdog exactly: a heartbeat is FRESH while its age is within
the lease window (``age <= lease_window``), stale once older.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone

from lfx.log.logger import logger
from sqlmodel import col, func, select

from langflow.services.background_execution.metrics import current_backend
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.deps import get_telemetry_service, session_scope

# Non-terminal statuses: a job in one of these is still occupying the system.
# QUEUED/IN_PROGRESS are the only non-terminal states; COMPLETED / FAILED /
# TIMED_OUT / CANCELLED are terminal.
NONTERMINAL_STATUSES = (JobStatus.QUEUED, JobStatus.IN_PROGRESS)


async def count_nonterminal_jobs(session) -> dict[str, int]:
    """Return counts of non-terminal jobs keyed by status string.

    ``{"queued": 3, "in_progress": 1}`` via a ``GROUP BY status`` aggregate
    filtered to the non-terminal set. Statuses with zero rows are omitted (the
    collector loop fills in the canonical set with 0 when it sets gauges).
    """
    stmt = select(Job.status, func.count()).where(col(Job.status).in_(NONTERMINAL_STATUSES)).group_by(Job.status)
    result = await session.exec(stmt)
    counts: dict[str, int] = {}
    for status, count in result.all():
        # ``status`` is a JobStatus enum; ``.value`` is the wire string.
        key = status.value if isinstance(status, JobStatus) else str(status)
        counts[key] = int(count)
    return counts


async def oldest_queued_seconds(session, now: datetime) -> float:
    """Age in seconds of the oldest QUEUED job: ``now - min(created_timestamp)``.

    Returns ``0.0`` when nothing is queued. ``now`` is injected (aware UTC) for
    determinism.
    """
    stmt = select(func.min(Job.created_timestamp)).where(Job.status == JobStatus.QUEUED)
    result = await session.exec(stmt)
    oldest = result.first()
    if oldest is None:
        return 0.0
    # SQLite returns a naive datetime for a timezone-aware column; treat it as
    # UTC (matching how is_lease_stale normalizes naive heartbeats).
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    age = (now - oldest).total_seconds()
    # A clock skew where now precedes the row should never report a negative age.
    return max(age, 0.0)


async def alive_worker_count(session, now: datetime, lease_window: float) -> int:
    """Count distinct heartbeat owners whose lease is still fresh.

    Fresh means ``heartbeat_at >= now - lease_window`` — the exact inverse of
    ``JobService.is_lease_stale`` (stale once ``age > lease_window``), so a
    worker counted "alive" here is one the watchdog would NOT reconcile. The
    heartbeat lease lives in ``job_metadata`` (``owner`` + ``heartbeat_at`` ISO
    string), stamped only on IN_PROGRESS rows by ``JobService.heartbeat``.

    Parsing the ISO ``heartbeat_at`` in Python (rather than a cross-dialect
    JSON-string SQL comparison) keeps the boundary identical to is_lease_stale
    on both SQLite and Postgres.
    """
    stmt = select(Job.job_metadata).where(Job.status == JobStatus.IN_PROGRESS)
    result = await session.exec(stmt)
    alive_owners: set[str] = set()
    for row in result.all():
        meta = row or {}
        owner = meta.get("owner")
        raw = meta.get("heartbeat_at")
        if not owner or not raw:
            continue
        try:
            hb = datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            continue
        if hb.tzinfo is None:
            hb = hb.replace(tzinfo=timezone.utc)
        age = (now - hb).total_seconds()
        if age <= lease_window:
            alive_owners.add(owner)
    return len(alive_owners)


class BackgroundMetricsCollector:
    """Periodically pushes DB-derived bg-execution gauges to the OTel registry.

    The collector owns the clock: each tick computes one aware-UTC ``now``,
    runs the three query functions against a short-lived session, and writes the
    gauges via ``get_telemetry_service().ot.update_gauge``. It is the only writer
    of these gauges; an ObservableGauge reports the last value set per label-set,
    so each tick zero-fills the canonical non-terminal status set to make a status
    dropping to 0 overwrite a stale prior value.

    Best-effort: a failing tick logs a warning and returns without raising so the
    loop keeps running — observability must never crash the service.

    ``lease_window`` defaults to ``45.0`` to match the runtime
    ``background_lease_ttl_s`` setting that ``sweep_orphans`` / ``requeue_lost``
    are actually called with, so "alive workers" agrees with what the watchdog
    reconciles. Task 8 passes ``settings.background_lease_ttl_s`` explicitly.
    """

    def __init__(self, *, interval: float, lease_window: float = 45.0):
        self.interval = interval
        self.lease_window = lease_window
        self._stopped = False
        self._task: asyncio.Task | None = None

    async def collect_once(self, session) -> None:
        """Run the three queries and push the gauges. Never raises."""
        try:
            now = datetime.now(timezone.utc)
            counts = await count_nonterminal_jobs(session)
            oldest = await oldest_queued_seconds(session, now)
            alive = await alive_worker_count(session, now, self.lease_window)

            backend = current_backend()
            ot = get_telemetry_service().ot

            # Zero-fill the canonical non-terminal set so a status that drops to 0
            # overwrites the gauge's stale prior value (last-value-wins semantics).
            for status in (JobStatus.QUEUED, JobStatus.IN_PROGRESS):
                ot.update_gauge(
                    "langflow_bg_jobs",
                    counts.get(status.value, 0),
                    {"status": status.value, "backend": backend},
                )
            ot.update_gauge("langflow_bg_oldest_queued_seconds", oldest, {"backend": backend})
            ot.update_gauge("langflow_bg_alive_workers", alive, {"backend": backend})
        except Exception as exc:  # noqa: BLE001 - observability must never crash the loop
            logger.warning(f"bg metrics collection tick skipped: {exc}")

    async def run(self) -> None:
        """Loop: open a short-lived session per tick, collect, sleep the interval."""
        while not self._stopped:
            async with session_scope() as session:
                await self.collect_once(session)
            await asyncio.sleep(self.interval)

    def start(self) -> None:
        """Spawn the collector loop task."""
        self._stopped = False
        self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        """Signal stop and cancel/await the loop task."""
        self._stopped = True
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
