"""DB-derived metric collector queries over the real durable job model.

These are pure read-only aggregates the collector loop pushes to OTel gauges.
They run against the REAL test DB (the ``client`` fixture; SQLite locally,
Postgres in CI) with NO mocking. ``now`` is injected so the time math is
deterministic and never races the wall clock.

The "alive" definition MUST match the watchdog's lease-staleness boundary
(``JobService.is_lease_stale``): a heartbeat is FRESH while its age is within
the lease window, so ``alive_worker_count`` counts owners with
``heartbeat_at >= now - lease_window``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.background_execution.metrics import current_backend
from langflow.services.background_execution.metrics_collector import (
    BackgroundMetricsCollector,
    alive_worker_count,
    count_nonterminal_jobs,
    duration_percentiles,
    oldest_queued_seconds,
    terminal_counts,
)
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_telemetry_service, session_scope
from langflow.services.jobs.service import JobService

pytestmark = pytest.mark.usefixtures("client")


async def test_count_nonterminal_jobs_excludes_terminal():
    """Only non-terminal statuses are counted, keyed by status string."""
    service = JobService()

    queued_a = uuid4()
    queued_b = uuid4()
    in_progress = uuid4()
    completed = uuid4()

    await service.create_job(job_id=queued_a, flow_id=uuid4(), user_id=uuid4())
    await service.create_job(job_id=queued_b, flow_id=uuid4(), user_id=uuid4())

    await service.create_job(job_id=in_progress, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(in_progress, JobStatus.IN_PROGRESS)

    # Terminal: must be excluded from the non-terminal aggregate.
    await service.create_job(job_id=completed, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(completed, JobStatus.COMPLETED, finished_timestamp=True)

    async with session_scope() as session:
        counts = await count_nonterminal_jobs(session)

    assert counts == {"queued": 2, "in_progress": 1}


async def test_oldest_queued_seconds_uses_injected_now():
    """Age of the oldest QUEUED job == now - min(created_timestamp)."""
    service = JobService()

    older = uuid4()
    newer = uuid4()
    await service.create_job(job_id=older, flow_id=uuid4(), user_id=uuid4())
    await service.create_job(job_id=newer, flow_id=uuid4(), user_id=uuid4())

    # Read back the actual stored created_timestamp of the oldest QUEUED job so
    # the expected age is exact regardless of insert latency.
    older_job = await service.get_job_by_job_id(older)
    created = older_job.created_timestamp
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    now = created + timedelta(seconds=42)

    async with session_scope() as session:
        age = await oldest_queued_seconds(session, now)

    assert age == pytest.approx(42.0, abs=1.0)


async def test_oldest_queued_seconds_zero_when_none_queued():
    """No QUEUED jobs -> 0.0 (a COMPLETED job must not count)."""
    service = JobService()

    done = uuid4()
    await service.create_job(job_id=done, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(done, JobStatus.COMPLETED, finished_timestamp=True)

    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        age = await oldest_queued_seconds(session, now)

    assert age == 0.0


async def test_alive_worker_count_excludes_stale_heartbeats():
    """Distinct owners with a FRESH heartbeat (within the lease window) are alive.

    Two owners heartbeat fresh; one owner's heartbeat is older than the window.
    The stale owner is excluded, matching ``is_lease_stale``.
    """
    service = JobService()
    lease_window = 30.0

    fresh_a = uuid4()
    fresh_b = uuid4()
    stale = uuid4()

    await service.create_job(job_id=fresh_a, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(fresh_a, JobStatus.IN_PROGRESS)
    await service.heartbeat(fresh_a, owner="worker-A")

    await service.create_job(job_id=fresh_b, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(fresh_b, JobStatus.IN_PROGRESS)
    await service.heartbeat(fresh_b, owner="worker-B")

    await service.create_job(job_id=stale, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(stale, JobStatus.IN_PROGRESS)
    old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await service.update_job_metadata(stale, {"owner": "worker-dead", "heartbeat_at": old})

    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        alive = await alive_worker_count(session, now, lease_window)

    assert alive == 2


async def test_alive_worker_count_distinct_owner():
    """Multiple fresh heartbeats from the SAME owner count once."""
    service = JobService()
    lease_window = 30.0

    job_one = uuid4()
    job_two = uuid4()
    await service.create_job(job_id=job_one, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(job_one, JobStatus.IN_PROGRESS)
    await service.heartbeat(job_one, owner="worker-A")

    await service.create_job(job_id=job_two, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(job_two, JobStatus.IN_PROGRESS)
    await service.heartbeat(job_two, owner="worker-A")

    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        alive = await alive_worker_count(session, now, lease_window)

    assert alive == 1


def _gauge_value(metric_name: str, labels: dict[str, str]) -> float:
    """Read a gauge value straight off the real OTel ObservableGaugeWrapper.

    The wrapper stores values keyed by ``tuple(sorted(labels.items()))`` — assert
    the SPECIFIC label-set we set this tick so a prior test's other label-sets in
    the process-wide singleton cannot interfere.
    """
    gauge = get_telemetry_service().ot._metrics[metric_name]
    return gauge._values[tuple(sorted(labels.items()))]


async def test_collect_once_sets_gauges():
    """One tick over a seeded mix sets each gauge to the DB-derived value."""
    service = JobService()
    backend = current_backend()

    queued_a = uuid4()
    queued_b = uuid4()
    in_progress = uuid4()
    completed = uuid4()

    await service.create_job(job_id=queued_a, flow_id=uuid4(), user_id=uuid4())
    await service.create_job(job_id=queued_b, flow_id=uuid4(), user_id=uuid4())

    await service.create_job(job_id=in_progress, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(in_progress, JobStatus.IN_PROGRESS)
    await service.heartbeat(in_progress, owner="worker-A")

    await service.create_job(job_id=completed, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(completed, JobStatus.COMPLETED, finished_timestamp=True)

    collector = BackgroundMetricsCollector(interval=15.0)
    async with session_scope() as session:
        await collector.collect_once(session)

    assert _gauge_value("langflow_bg_jobs", {"status": "queued", "backend": backend}) == 2
    assert _gauge_value("langflow_bg_jobs", {"status": "in_progress", "backend": backend}) == 1
    assert _gauge_value("langflow_bg_oldest_queued_seconds", {"backend": backend}) > 0
    assert _gauge_value("langflow_bg_alive_workers", {"backend": backend}) == 1


async def test_collect_once_zero_fills_dropped_status():
    """A status dropping to 0 overwrites the stale prior value (zero-fill)."""
    service = JobService()
    backend = current_backend()

    queued_a = uuid4()
    queued_b = uuid4()
    await service.create_job(job_id=queued_a, flow_id=uuid4(), user_id=uuid4())
    await service.create_job(job_id=queued_b, flow_id=uuid4(), user_id=uuid4())

    collector = BackgroundMetricsCollector(interval=15.0)
    async with session_scope() as session:
        await collector.collect_once(session)

    assert _gauge_value("langflow_bg_jobs", {"status": "queued", "backend": backend}) == 2

    # Drain the queue: both queued jobs go terminal, so queued must fall to 0.
    await service.update_job_status(queued_a, JobStatus.COMPLETED, finished_timestamp=True)
    await service.update_job_status(queued_b, JobStatus.COMPLETED, finished_timestamp=True)

    async with session_scope() as session:
        await collector.collect_once(session)

    assert _gauge_value("langflow_bg_jobs", {"status": "queued", "backend": backend}) == 0


async def test_run_stop_lifecycle():
    """start() spawns the loop, a tick runs against the real DB, stop() cancels cleanly.

    The process-wide OTel singleton already holds the ``queued`` label-set from
    prior tests, so we cannot key the wait on the key merely existing. Instead we
    flip the value to a sentinel, let a real tick overwrite it with this DB's
    count (>= the one queued job we seeded), then assert stop() ends the loop.
    """
    import asyncio

    service = JobService()
    backend = current_backend()

    queued = uuid4()
    await service.create_job(job_id=queued, flow_id=uuid4(), user_id=uuid4())

    sentinel = -1.0
    gauge = get_telemetry_service().ot._metrics["langflow_bg_jobs"]
    key = tuple(sorted({"status": "queued", "backend": backend}.items()))
    gauge._values[key] = sentinel

    collector = BackgroundMetricsCollector(interval=0.01)
    collector.start()
    for _ in range(200):
        if gauge._values.get(key, sentinel) != sentinel:
            break
        await asyncio.sleep(0.01)

    await collector.stop()
    assert collector._task is None
    assert _gauge_value("langflow_bg_jobs", {"status": "queued", "backend": backend}) >= 1


async def _seed_failed(service: JobService, *, error: dict):
    """Create a job, flip it FAILED, and stamp the given error blob."""
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
    await service.set_error(job_id, error)
    return job_id


async def _seed_terminal(service: JobService, status: JobStatus):
    """Create a job and flip it to the given terminal status."""
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(job_id, status, finished_timestamp=True)
    return job_id


async def test_terminal_counts_splits_outcomes():
    """terminal_counts returns the per-outcome split; started excludes only QUEUED."""
    from langflow.services.database.models.jobs.model import Job

    service = JobService()

    # 1 QUEUED (excluded from started), 1 IN_PROGRESS (counts toward started).
    await service.create_job(job_id=uuid4(), flow_id=uuid4(), user_id=uuid4())
    in_progress = uuid4()
    await service.create_job(job_id=in_progress, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(in_progress, JobStatus.IN_PROGRESS)

    # 2 COMPLETED.
    await _seed_terminal(service, JobStatus.COMPLETED)
    await _seed_terminal(service, JobStatus.COMPLETED)

    # FAILED split: 1 plain error, 2 worker_lost.
    await _seed_failed(service, error={"type": "error"})
    await _seed_failed(service, error={"type": "worker_lost"})
    await _seed_failed(service, error={"type": "worker_lost"})

    # 1 TIMED_OUT, 1 CANCELLED.
    await _seed_terminal(service, JobStatus.TIMED_OUT)
    await _seed_terminal(service, JobStatus.CANCELLED)

    async with session_scope() as session:
        tc = await terminal_counts(session)
        # Absolute totals in a shared test DB are not isolated across tests, so
        # assert against the actual current rows by status to keep this robust.
        from sqlmodel import col, func, select

        async def _count(*statuses):
            stmt = select(func.count()).select_from(Job).where(col(Job.status).in_(statuses))
            return int((await session.exec(stmt)).one())

        total = await _count(*list(JobStatus))
        queued = await _count(JobStatus.QUEUED)
        completed = await _count(JobStatus.COMPLETED)
        timed_out = await _count(JobStatus.TIMED_OUT)
        cancelled = await _count(JobStatus.CANCELLED)
        failed = await _count(JobStatus.FAILED)

    assert tc["started"] == total - queued
    assert tc["completed"] == completed
    assert tc["timed_out"] == timed_out
    assert tc["cancelled"] == cancelled
    # The split must partition all FAILED rows.
    assert tc["failed_worker_lost"] + tc["failed_error"] == failed
    # We seeded exactly two worker_lost rows; any pre-existing FAILED rows from
    # other tests carry a different/absent type and land in failed_error.
    assert tc["failed_worker_lost"] >= 2


async def test_duration_percentiles_deterministic():
    """p50/p95 over jobs finished within the window match known durations."""
    from langflow.services.database.models.jobs.model import Job

    service = JobService()
    now = datetime.now(timezone.utc)

    # Seed five COMPLETED jobs with known durations 10..50s, all finished now.
    durations = [10, 20, 30, 40, 50]
    job_ids = []
    for _ in durations:
        jid = uuid4()
        await service.create_job(job_id=jid, flow_id=uuid4(), user_id=uuid4())
        await service.update_job_status(jid, JobStatus.COMPLETED, finished_timestamp=True)
        job_ids.append(jid)

    # Stamp deterministic created/finished timestamps directly.
    async with session_scope() as session:
        for jid, dur in zip(job_ids, durations, strict=True):
            job = await session.get(Job, jid)
            job.finished_timestamp = now
            job.created_timestamp = now - timedelta(seconds=dur)
            session.add(job)
        await session.flush()

    # A tiny window isolates OUR five just-finished rows from any earlier
    # finished jobs other tests left in the shared DB. Nearest-rank over the
    # durations [10,20,30,40,50]: p50 -> rank ceil(0.5*5)=3 -> 30; p95 -> rank
    # ceil(0.95*5)=5 -> 50.
    async with session_scope() as session:
        p50, p95 = await duration_percentiles(session, now, window_seconds=1.0)
    assert p50 == pytest.approx(30.0, abs=1.0)
    assert p95 == pytest.approx(50.0, abs=1.0)


async def test_duration_percentiles_excludes_jobs_outside_window():
    """A job finished before the SQL cutoff is excluded; only the recent one counts.

    Anchors a synthetic ``now`` far in the future so no other test's rows fall in
    the window, then seeds two jobs: one finished an hour before that ``now``
    (duration 999s, OUTSIDE a 60s window) and one finished AT that ``now``
    (duration 7s, INSIDE). The SQL cutoff must drop the old row, so only the 7s
    duration contributes — proving the window is applied in the query, not just
    in Python.
    """
    from langflow.services.database.models.jobs.model import Job

    service = JobService()
    base = datetime.now(timezone.utc) + timedelta(days=365)

    old = uuid4()
    recent = uuid4()
    for jid in (old, recent):
        await service.create_job(job_id=jid, flow_id=uuid4(), user_id=uuid4())
        await service.update_job_status(jid, JobStatus.COMPLETED, finished_timestamp=True)

    async with session_scope() as session:
        old_job = await session.get(Job, old)
        old_job.finished_timestamp = base - timedelta(hours=1)
        old_job.created_timestamp = base - timedelta(hours=1) - timedelta(seconds=999)
        session.add(old_job)
        recent_job = await session.get(Job, recent)
        recent_job.finished_timestamp = base
        recent_job.created_timestamp = base - timedelta(seconds=7)
        session.add(recent_job)
        await session.flush()

    # 60s window back from ``base``: the recent job (finished AT base) is in; the
    # old job (finished an hour earlier) is out. Only the 7s sample remains, so
    # p50 == p95 == 7 and the 999s duration never leaks in.
    async with session_scope() as session:
        p50, p95 = await duration_percentiles(session, base, window_seconds=60.0)

    assert p50 == pytest.approx(7.0, abs=1.0)
    assert p95 == pytest.approx(7.0, abs=1.0)
    assert p95 < 100.0


async def test_duration_percentiles_zero_when_none_in_window():
    """No job finished in the window -> (0.0, 0.0)."""
    service = JobService()

    jid = uuid4()
    await service.create_job(job_id=jid, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(jid, JobStatus.COMPLETED, finished_timestamp=True)

    # Anchor ``now`` far in the FUTURE with a tiny window so the cutoff
    # (now - 1s) sits well after every real-time finish; nothing qualifies.
    future = datetime.now(timezone.utc) + timedelta(days=365)
    async with session_scope() as session:
        p50, p95 = await duration_percentiles(session, future, window_seconds=1.0)

    assert (p50, p95) == (0.0, 0.0)


def _counter_value(metric_name: str, labels: dict[str, str]) -> float:
    """Read an observable-counter value straight off the real OTel wrapper."""
    counter = get_telemetry_service().ot._metrics[metric_name]
    return counter._values[tuple(sorted(labels.items()))]


async def test_collect_once_sets_counters_and_duration_gauges():
    """A tick sets the observable counters (per reason) + p50/p95 duration gauges."""
    from langflow.services.database.models.jobs.model import Job

    service = JobService()
    backend = current_backend()
    now = datetime.now(timezone.utc)

    other_terminal = [
        await _seed_terminal(service, JobStatus.COMPLETED),
        await _seed_failed(service, error={"type": "error"}),
        await _seed_failed(service, error={"type": "worker_lost"}),
        await _seed_terminal(service, JobStatus.TIMED_OUT),
        await _seed_terminal(service, JobStatus.CANCELLED),
    ]

    # A COMPLETED job with a known 12s duration finished now so the duration
    # gauges are non-zero with a tight window.
    dur_job = uuid4()
    await service.create_job(job_id=dur_job, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(dur_job, JobStatus.COMPLETED, finished_timestamp=True)
    async with session_scope() as session:
        # Push every other seeded job's finish well outside the duration window
        # so only ``dur_job`` qualifies and its 12s duration is the lone sample.
        for jid in other_terminal:
            job = await session.get(Job, jid)
            job.finished_timestamp = now - timedelta(hours=1)
            session.add(job)
        job = await session.get(Job, dur_job)
        job.finished_timestamp = now
        job.created_timestamp = now - timedelta(seconds=12)
        session.add(job)
        await session.flush()

    collector = BackgroundMetricsCollector(interval=15.0, duration_window_seconds=30.0)
    async with session_scope() as session:
        # Read the expected DB-derived counts under the same session the tick uses.
        expected = await terminal_counts(session)
        await collector.collect_once(session)

    assert _counter_value("langflow_bg_jobs_started_total", {"backend": backend}) == expected["started"]
    assert _counter_value("langflow_bg_jobs_completed_total", {"backend": backend}) == expected["completed"]
    assert (
        _counter_value("langflow_bg_jobs_failed_total", {"reason": "error", "backend": backend})
        == expected["failed_error"]
    )
    assert (
        _counter_value("langflow_bg_jobs_failed_total", {"reason": "worker_lost", "backend": backend})
        == expected["failed_worker_lost"]
    )
    assert (
        _counter_value("langflow_bg_jobs_failed_total", {"reason": "timeout", "backend": backend})
        == expected["timed_out"]
    )
    assert (
        _counter_value("langflow_bg_jobs_failed_total", {"reason": "cancelled", "backend": backend})
        == expected["cancelled"]
    )
    assert (
        _counter_value("langflow_bg_orphans_reconciled_total", {"backend": backend}) == expected["failed_worker_lost"]
    )
    # dur_job finished AT now with a 12s run, so it qualifies for the window and
    # drives the duration gauges non-zero (exact percentile math is asserted in
    # test_duration_percentiles_deterministic; here we only prove collect_once
    # wires p50/p95 from a real finished-job sample).
    assert _gauge_value("langflow_bg_job_duration_p50_seconds", {"backend": backend}) > 0.0
    assert _gauge_value("langflow_bg_job_duration_p95_seconds", {"backend": backend}) > 0.0
