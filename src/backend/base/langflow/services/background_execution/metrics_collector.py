"""DB-derived metric queries for background execution observability.

Pure, read-only aggregates over the durable job model. Each function takes a
session and (where time matters) an injected ``now`` so the math is
deterministic in tests and the loop owns the clock. No side effects, no gauge
writes — Task 7 wires these into the OTel gauges.

``now`` is timezone-aware UTC. ``created_timestamp`` is stored as a
timezone-aware column, but SQLite hands it back naive; we normalize to aware
UTC before subtracting so the math is valid on both SQLite and Postgres.

The worker online/busy/idle gauges are derived from the durable
``worker_registry`` table (``WorkerRegistryService.count_by_state``): a row is
online while ``last_heartbeat >= now - online_window`` (online_window = 3x the
worker's registry interval). The collector also prunes rows past retention.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from sqlmodel import col, func, select

from langflow.services.background_execution.metrics import current_backend
from langflow.services.background_execution.worker_registry import WorkerRegistryService
from langflow.services.database.models.jobs.model import Job, JobEvent, JobStatus
from langflow.services.deps import get_telemetry_service, session_scope

if TYPE_CHECKING:
    from fastapi import FastAPI

# Non-terminal statuses: a job in one of these is still occupying the system.
# QUEUED/IN_PROGRESS are the only non-terminal states; COMPLETED / FAILED /
# TIMED_OUT / CANCELLED are terminal.
NONTERMINAL_STATUSES = (JobStatus.QUEUED, JobStatus.IN_PROGRESS)


def _has_job_events():
    """EXISTS subquery: the job has at least one ``job_events`` row.

    Distinguishes a TRUE background job from a Memory-Base "run job". Every flow
    build writes a second ``job`` row keyed by the graph run_id (``build.py``,
    predates the bg work); it is ``type=workflow`` too, so a naive status query
    double-counts it. The background runner uniquely appends ``job_events`` rows,
    while run jobs never have any (they go straight IN_PROGRESS->terminal via
    ``execute_with_status`` and never QUEUED). So a background job is
    ``status == QUEUED`` OR EXISTS(job_events). ``job_id`` is indexed
    (UNIQUE(job_id, seq)), so the EXISTS is cheap and dialect-agnostic.
    """
    return select(JobEvent.id).where(col(JobEvent.job_id) == Job.job_id).exists()


async def count_nonterminal_jobs(session) -> dict[str, int]:
    """Return counts of non-terminal background jobs keyed by status string.

    ``{"queued": 3, "in_progress": 1}``. QUEUED is bg-only (run jobs are never
    queued), so it counts as-is. IN_PROGRESS adds the EXISTS(job_events) filter
    because a run job is briefly IN_PROGRESS with no events — without the filter
    it would inflate the in_progress count. A status with zero rows is omitted
    (the collector loop fills in the canonical set with 0 when it sets gauges).
    """
    queued = (await session.exec(select(func.count()).select_from(Job).where(Job.status == JobStatus.QUEUED))).one()
    in_progress = (
        await session.exec(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.IN_PROGRESS).where(_has_job_events())
        )
    ).one()
    counts: dict[str, int] = {}
    if int(queued):
        counts[JobStatus.QUEUED.value] = int(queued)
    if int(in_progress):
        counts[JobStatus.IN_PROGRESS.value] = int(in_progress)
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


async def worker_state_counts(session, now: datetime, online_window: timedelta) -> dict[str, int]:
    """Aggregate online/busy/idle worker counts from the durable ``worker_registry``.

    Thin wrapper over ``WorkerRegistryService.count_by_state`` so the collector
    derives its fleet gauges from the same source of truth the worker loop writes.
    A row is online when ``last_heartbeat >= now - online_window``; busy/idle split
    online rows by state. ``now`` is injected for deterministic freshness math.
    """
    return await WorkerRegistryService().count_by_state(session, now=now, online_window=online_window)


def _error_type_expr(session):
    """Dialect-aware SQL expression for ``error->>'type'`` as text.

    Postgres uses the raw ``->>`` operator (``error ->> 'type'``) via
    ``col(Job.error).op("->>")("type")`` — robust regardless of whether the
    column maps as JSON or JSONB, unlike ``.astext`` which raises on this
    column's type mapping. SQLite uses ``json_extract(error, '$.type')``. Both
    return the string value of the ``type`` key (or NULL when ``error`` is NULL
    or has no ``type``), so the FAILED worker_lost split is computed in SQL
    rather than reading every FAILED row into Python (unbounded over all time).

    The test DB is sqlite (json_extract branch); the postgres ``->>`` branch is
    verified live against a real Postgres instance.
    """
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return col(Job.error).op("->>")("type")
    # sqlite (and other JSON-text dialects): json_extract walks the path.
    return func.json_extract(col(Job.error), "$.type")


async def terminal_counts(session) -> dict[str, int]:
    """Cumulative all-time outcome counts derived from the durable job table.

    Returns ``{"started", "completed", "failed_error", "failed_worker_lost",
    "timed_out", "cancelled"}``:

    * ``started`` — every background job that has begun: ``status != QUEUED``
      AND EXISTS(job_events) (IN_PROGRESS plus every terminal state).
    * ``completed`` — ``status == COMPLETED``.
    * FAILED jobs split by ``error->>'type'``: ``failed_worker_lost`` is FAILED
      AND ``type == 'worker_lost'``; ``failed_error`` is every other FAILED row.
    * ``timed_out`` / ``cancelled`` — the matching terminal statuses.

    Every non-queued count adds the EXISTS(job_events) filter so a Memory-Base
    "run job" (build.py's second workflow row, which never appends job_events)
    is excluded — without it the counts double (see ``_has_job_events``). The
    worker_lost split uses a dialect-aware JSON extract (see ``_error_type_expr``)
    so it stays a single bounded SQL aggregate on both SQLite and Postgres.
    """
    has_events = _has_job_events()
    started_stmt = select(func.count()).select_from(Job).where(Job.status != JobStatus.QUEUED).where(has_events)
    completed_stmt = select(func.count()).select_from(Job).where(Job.status == JobStatus.COMPLETED).where(has_events)
    timed_out_stmt = select(func.count()).select_from(Job).where(Job.status == JobStatus.TIMED_OUT).where(has_events)
    cancelled_stmt = select(func.count()).select_from(Job).where(Job.status == JobStatus.CANCELLED).where(has_events)

    error_type = _error_type_expr(session)
    worker_lost_stmt = (
        select(func.count())
        .select_from(Job)
        .where(Job.status == JobStatus.FAILED)
        .where(has_events)
        .where(error_type == "worker_lost")
    )

    started = (await session.exec(started_stmt)).one()
    completed = (await session.exec(completed_stmt)).one()
    timed_out = (await session.exec(timed_out_stmt)).one()
    cancelled = (await session.exec(cancelled_stmt)).one()
    failed_worker_lost = (await session.exec(worker_lost_stmt)).one()
    # ``error_type != 'worker_lost'`` is NULL (and thus excluded) for FAILED rows
    # with a NULL error or no ``type`` key, so count FAILED-not-worker_lost as the
    # complement of worker_lost to capture those rows too.
    failed_total = (
        await session.exec(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.FAILED).where(has_events)
        )
    ).one()

    return {
        "started": int(started),
        "completed": int(completed),
        "failed_error": int(failed_total) - int(failed_worker_lost),
        "failed_worker_lost": int(failed_worker_lost),
        "timed_out": int(timed_out),
        "cancelled": int(cancelled),
    }


async def duration_percentiles(session, now: datetime, window_seconds: float) -> tuple[float, float]:
    """p50/p95 run duration (seconds) over jobs finished within the window.

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

    Only TRUE background jobs are considered (EXISTS(job_events)) so a run job's
    near-instant duration does not skew p50/p95 — see ``_has_job_events``.
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
        .where(_has_job_events())
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

    The collector owns the clock: each tick computes one aware-UTC ``now``,
    runs the three query functions against a short-lived session, and writes the
    gauges via ``get_telemetry_service().ot.update_gauge``. It is the only writer
    of these gauges; an ObservableGauge reports the last value set per label-set,
    so each tick zero-fills the canonical non-terminal status set to make a status
    dropping to 0 overwrite a stale prior value.

    Best-effort: a failing tick logs a warning and returns without raising so the
    loop keeps running — observability must never crash the service.

    ``registry_interval`` is the worker's ``background_worker_registry_interval_s``;
    the online window is ``3 * registry_interval`` (a worker is online while it has
    beat within three of its own intervals). ``registry_retention_s`` is how long a
    stale row is kept before the per-tick prune removes it. Both default from the
    settings at the construction site (``maybe_start_metrics_collector``).
    """

    def __init__(
        self,
        *,
        interval: float,
        registry_interval: float = 10.0,
        registry_retention_s: float = 3600.0,
        duration_window_seconds: float = 300.0,
    ):
        self.interval = interval
        self.registry_interval = registry_interval
        self.registry_retention_s = registry_retention_s
        self.duration_window_seconds = duration_window_seconds
        self._stopped = False
        self._task: asyncio.Task | None = None

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
            online_window = timedelta(seconds=3 * self.registry_interval)
            worker_counts = await worker_state_counts(session, now, online_window)

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
            ot.update_gauge("langflow_bg_workers_online", worker_counts["online"], {"backend": backend})
            ot.update_gauge("langflow_bg_workers_busy", worker_counts["busy"], {"backend": backend})
            ot.update_gauge("langflow_bg_workers_idle", worker_counts["idle"], {"backend": backend})

            # Cumulative all-time throughput/outcome counts, set as observable
            # counters (last-absolute-value-wins per label-set). The worker runs
            # in separate processes that never expose :9090, so the API-side
            # collector is the single writer of these from the durable table.
            tc = await terminal_counts(session)
            ot.set_observable_counter("langflow_bg_jobs_started_total", tc["started"], {"backend": backend})
            ot.set_observable_counter("langflow_bg_jobs_completed_total", tc["completed"], {"backend": backend})
            # Zero-fill every reason each tick so a reason whose count stops
            # growing still reports its cumulative value (and a never-seen reason
            # reports 0 rather than vanishing).
            for reason, count in (
                ("error", tc["failed_error"]),
                ("worker_lost", tc["failed_worker_lost"]),
                ("timeout", tc["timed_out"]),
                ("cancelled", tc["cancelled"]),
            ):
                ot.set_observable_counter(
                    "langflow_bg_jobs_failed_total", count, {"reason": reason, "backend": backend}
                )
            ot.set_observable_counter(
                "langflow_bg_orphans_reconciled_total", tc["failed_worker_lost"], {"backend": backend}
            )

            p50, p95 = await duration_percentiles(session, now, self.duration_window_seconds)
            ot.update_gauge("langflow_bg_job_duration_p50_seconds", p50, {"backend": backend})
            ot.update_gauge("langflow_bg_job_duration_p95_seconds", p95, {"backend": backend})

            # Best-effort prune of crashed-worker rows past retention. Guarded on its
            # own so a prune failure (e.g. a write contention) does not drop the gauges
            # already set this tick — the next tick retries.
            try:
                await WorkerRegistryService().prune_stale(session, now=now, retention_s=self.registry_retention_s)
            except Exception as exc:  # noqa: BLE001 - prune is best-effort, never breaks the tick
                logger.warning(f"bg worker_registry prune skipped: {exc}")
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
    app.state.background_metrics_collector = None
    if not (prometheus_started and getattr(settings, "prometheus_enabled", False)):
        return
    try:
        collector = BackgroundMetricsCollector(
            interval=settings.background_metrics_interval,
            registry_interval=settings.background_worker_registry_interval_s,
            registry_retention_s=settings.background_worker_registry_retention_s,
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
    collector = getattr(app.state, "background_metrics_collector", None)
    if collector is not None:
        with contextlib.suppress(Exception):
            await collector.stop()
