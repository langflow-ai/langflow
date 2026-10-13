"""Collect cached background-job metrics from read-only database aggregates.

Gauges refresh every tick; all-time outcome counters refresh every five minutes
because their aggregate still scans retained job history. Purged outcomes are
archived transactionally and included in the same database snapshot. Prometheus
callbacks read only the cached values. Background submissions are identified by the persisted request
marker, excluding stored sync results and events that orphan reconciliation can
also append to other jobs.

Query functions accept an injected aware-UTC ``now`` for deterministic age and
submission-to-finish duration calculations. SQLite returns naive datetimes, which
are normalized to UTC before subtraction.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from sqlmodel import col, func, select

from langflow.services.background_execution.metrics import current_backend
from langflow.services.database.models.jobs.metrics import is_background_job, terminal_counts
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.deps import get_telemetry_service, session_scope

if TYPE_CHECKING:
    from fastapi import FastAPI

# Non-terminal statuses: a job in one of these is still occupying the system.
# SUSPENDED belongs here: a run waiting on human input has not finished, and leaving it
# out made those jobs vanish from a gauge documented as a count by status. COMPLETED /
# FAILED / TIMED_OUT / CANCELLED are terminal.
NONTERMINAL_STATUSES = (JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.SUSPENDED)
TERMINAL_COUNTS_INTERVAL_SECONDS = 300.0


async def count_nonterminal_jobs(session) -> dict[str, int]:
    """Count queued, running, and suspended background submissions by status.

    Sync workflow rows briefly start as QUEUED too; the persisted request marker
    excludes them at every stage. Missing statuses are zero-filled by the collector.
    """
    stmt = (
        select(Job.status, func.count())
        .where(col(Job.status).in_(NONTERMINAL_STATUSES))
        .where(is_background_job())
        .group_by(Job.status)
    )
    rows = (await session.exec(stmt)).all()
    return {status.value if hasattr(status, "value") else str(status): int(count) for status, count in rows if count}


async def oldest_queued_seconds(session, now: datetime) -> float:
    """Age in seconds of the oldest queued background submission: ``now - min(created_timestamp)``.

    Returns ``0.0`` when nothing is queued. ``now`` is injected (aware UTC) for
    determinism.
    """
    stmt = select(func.min(Job.created_timestamp)).where(Job.status == JobStatus.QUEUED).where(is_background_job())
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


async def duration_percentiles(session, now: datetime, window_seconds: float) -> tuple[float, float]:
    """p50/p95 submission-to-finish time (seconds) over jobs finished within the window.

    Considers rows with ``finished_timestamp`` not null AND
    ``finished_timestamp >= now - window_seconds``; duration is
    ``finished_timestamp - created_timestamp``. The window is SQL-bounded so the
    fetch scales with the window, not the all-time finished-job count, then the
    durations and percentiles are computed in Python (nearest-rank). Returns
    ``(0.0, 0.0)`` when no job finished in the window.

    The cutoff is bound per-dialect (reusing ``session.get_bind().dialect.name``)
    because Postgres stores ``finished_timestamp`` tz-aware (an aware cutoff
    compares correctly) while SQLite stores it as a naive ISO string (comparing
    against an aware ``+00:00`` cutoff is a lexicographic mismatch that can drop
    boundary rows), so SQLite gets a naive-UTC cutoff that matches the stored
    format. Naive SQLite datetimes are still normalized to aware UTC before
    subtracting, the same way ``oldest_queued_seconds`` does.

    Only marked background submissions are considered. Durations include queue
    wait and time suspended on human input, since resume preserves the same row.
    """
    cutoff = now - timedelta(seconds=window_seconds)
    # Bind the cutoff in the form the stored column uses: aware for postgres,
    # naive-UTC for sqlite (text datetimes), so the comparison is apples-to-apples.
    dialect = session.get_bind().dialect.name
    sql_cutoff = cutoff if dialect == "postgresql" else cutoff.replace(tzinfo=None)
    stmt = (
        select(Job.created_timestamp, Job.finished_timestamp)
        .where(col(Job.finished_timestamp).is_not(None))
        .where(col(Job.finished_timestamp) >= sql_cutoff)
        .where(is_background_job())
    )
    result = await session.exec(stmt)
    durations: list[float] = []
    for created, finished in result.all():
        if finished is None:
            continue
        # SQLite hands back naive datetimes for tz-aware columns; normalize.
        finished_utc = finished if finished.tzinfo is not None else finished.replace(tzinfo=timezone.utc)
        created_utc = created if created.tzinfo is not None else created.replace(tzinfo=timezone.utc)
        durations.append(max((finished_utc - created_utc).total_seconds(), 0.0))
    if not durations:
        return 0.0, 0.0
    durations.sort()
    return _nearest_rank(durations, 50), _nearest_rank(durations, 95)


def _nearest_rank(sorted_values: list[float], percentile: float) -> float:
    """Nearest-rank percentile over a pre-sorted list (1-indexed rank, clamped)."""
    n = len(sorted_values)
    rank = max(1, min(n, math.ceil(percentile / 100 * n)))
    return sorted_values[rank - 1]


class BackgroundMetricsCollector:
    """Periodically pushes DB-derived bg-execution gauges to the OTel registry.

    Each tick computes one aware-UTC ``now``, queries the current gauges in a
    short-lived session, and writes them to the telemetry registry. All-time
    counters refresh on the first tick and at most once every five minutes. It is
    the only writer of these gauges; an ObservableGauge reports the last value set per label-set,
    so each tick zero-fills the canonical non-terminal status set to make a status
    dropping to 0 overwrite a stale prior value.

    Best-effort: a failing tick logs a warning and returns without raising so the
    loop keeps running — observability must never crash the service.

    Every metric carries a ``backend`` label, so the same series distinguish the
    in-process default backend from a scaled one if that lands later.
    """

    def __init__(
        self,
        *,
        interval: float,
        duration_window_seconds: float = 300.0,
    ):
        self.interval = interval
        self.duration_window_seconds = duration_window_seconds
        self._stopped = False
        self._task: asyncio.Task | None = None
        self._last_totals_refresh: float | None = None

    async def collect_once(self, session, *, now: datetime | None = None) -> None:
        """Run the queries and push the gauges. Never raises.

        ``now`` defaults to the wall clock so the loop owns the tick's clock; tests
        inject an explicit ``now`` for deterministic freshness/retention math.
        """
        try:
            if now is None:
                now = datetime.now(timezone.utc)
            counts = await count_nonterminal_jobs(session)
            oldest = await oldest_queued_seconds(session, now)
            backend = current_backend()
            ot = get_telemetry_service().ot

            # Zero-fill the canonical non-terminal set so a status that drops to 0
            # overwrites the gauge's stale prior value (last-value-wins semantics).
            for status in NONTERMINAL_STATUSES:
                ot.update_gauge(
                    "langflow_bg_jobs",
                    counts.get(status.value, 0),
                    {"status": status.value, "backend": backend},
                )
            ot.update_gauge("langflow_bg_oldest_queued_seconds", oldest, {"backend": backend})

            p50, p95 = await duration_percentiles(session, now, self.duration_window_seconds)
            ot.update_gauge("langflow_bg_job_duration_p50_seconds", p50, {"backend": backend})
            ot.update_gauge("langflow_bg_job_duration_p95_seconds", p95, {"backend": backend})

            # Full-history aggregates are more expensive than the indexed gauges.
            # Keep their last exported values between refreshes; a monotonic clock
            # prevents wall-clock adjustments from changing the polling cadence.
            if (
                self._last_totals_refresh is not None
                and monotonic() - self._last_totals_refresh < TERMINAL_COUNTS_INTERVAL_SECONDS
            ):
                return
            tc = await terminal_counts(session)
            ot.set_observable_counter("langflow_bg_jobs_started_total", tc["started"], {"backend": backend})
            ot.set_observable_counter("langflow_bg_jobs_completed_total", tc["completed"], {"backend": backend})
            # Zero-fill every reason on refresh so a reason whose count stops
            # growing still reports its cumulative value (and a never-seen reason
            # reports 0 rather than vanishing).
            for reason, count in (
                ("error", tc["failed_error"]),
                ("worker_lost", tc["failed_worker_lost"]),
                ("input_timeout", tc["failed_input_timeout"]),
                ("timeout", tc["timed_out"]),
                ("cancelled", tc["cancelled"]),
            ):
                ot.set_observable_counter(
                    "langflow_bg_jobs_failed_total", count, {"reason": reason, "backend": backend}
                )
            # Only a successful refresh advances the clock; failures retry next tick.
            self._last_totals_refresh = monotonic()
        except Exception as exc:  # noqa: BLE001 - observability must never crash the loop
            logger.warning(f"bg metrics collection tick skipped: {exc}")

    async def run(self) -> None:
        """Loop: open a short-lived session per tick, collect, sleep the interval.

        The whole body is guarded, not just the collection. ``collect_once`` swallows its
        own errors, but ``session_scope()`` is outside it, so a database that is briefly
        unavailable would raise here, end the task, and stop every later tick for the life
        of the process. Nothing awaits this task, so that would surface only as a stray
        "Task exception was never retrieved" and the metrics would go quietly flat.

        ``CancelledError`` inherits from ``BaseException``, so ``stop()`` still cancels the
        loop rather than being caught and retried here.
        """
        while not self._stopped:
            try:
                async with session_scope() as session:
                    await self.collect_once(session)
            except Exception as exc:  # noqa: BLE001 - a bad tick must not end the loop
                logger.warning(f"bg metrics tick failed, retrying next interval: {exc}")
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


async def maybe_start_metrics_collector(app: FastAPI, settings: Any, *, prometheus_started: bool) -> None:
    """Start the collector and stash it on ``app.state`` when this process owns metrics.

    Gated on ``prometheus_started`` so only the process that actually bound the
    Prometheus exposition port runs the collector. With ``gunicorn -w N`` only one
    worker wins the port (EADDRINUSE for the rest), so only that worker queries the
    DB and writes the gauges that get scraped. ``prometheus_enabled`` is the feature
    switch; without it nothing is exposed so there is nothing to collect for.

    Best-effort: never block or crash startup on observability — a failure logs a
    warning and leaves ``app.state.background_metrics_collector`` as ``None``.
    """
    if not hasattr(app, "state"):  # pragma: no cover - defensive, a real app always has it
        return
    app.state.background_metrics_collector = None
    if not (prometheus_started and getattr(settings, "prometheus_enabled", False)):
        return
    try:
        collector = BackgroundMetricsCollector(
            interval=settings.background_metrics_interval,
        )
        collector.start()
        app.state.background_metrics_collector = collector
        await logger.adebug("Started background-execution metrics collector")
    except Exception as exc:  # noqa: BLE001 - never block startup on observability
        await logger.awarning(f"Background metrics collector not started: {exc}")


async def stop_metrics_collector(app: FastAPI) -> None:
    """Stop the collector if one was started. Defensive: never breaks shutdown.

    The attribute may be unset if startup failed before it ran, so we read it
    with ``getattr`` and swallow any stop error — shutdown must finish regardless.
    """
    # getattr through ``state`` as well as through it. This runs in the lifespan's finally
    # block, which is also reached when startup failed early enough that ``state`` was never
    # populated, and an AttributeError raised here would replace the original startup error
    # with a misleading one. Shutdown cleanup must not be able to mask why startup failed.
    collector = getattr(getattr(app, "state", None), "background_metrics_collector", None)
    if collector is not None:
        with contextlib.suppress(Exception):
            await collector.stop()
