"""DB-derived metric collector queries over the real durable job model.

These are pure read-only aggregates the collector loop pushes to OTel gauges.
They run against the REAL test DB (the ``client`` fixture; SQLite locally,
Postgres in CI) with NO mocking. ``now`` is injected so the time math is
deterministic and never races the wall clock.

Background submissions carry the persisted request marker. Tests also exercise
orphan cleanup, human-input expiry, retries, and status corrections through the
real JobService to keep their metric semantics pinned.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.background_execution.metrics import current_backend
from langflow.services.background_execution.metrics_collector import (
    BackgroundMetricsCollector,
    count_nonterminal_jobs,
    duration_percentiles,
    oldest_queued_seconds,
    terminal_counts,
)
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.deps import get_telemetry_service, session_scope
from langflow.services.jobs.service import JobService

pytestmark = pytest.mark.usefixtures("client")


async def _create_background_job(service: JobService, **kwargs):
    """Persist the same submission marker as BackgroundExecutionService.submit."""
    return await service.create_job(initial_metadata={"request": {}}, **kwargs)


async def test_count_nonterminal_jobs_excludes_terminal():
    """Only non-terminal background statuses are counted, keyed by status string."""
    service = JobService()

    queued_a = uuid4()
    queued_b = uuid4()
    in_progress = uuid4()
    completed = uuid4()
    run_in_progress = uuid4()

    await _create_background_job(service, job_id=queued_a, flow_id=uuid4(), user_id=uuid4())
    await _create_background_job(service, job_id=queued_b, flow_id=uuid4(), user_id=uuid4())

    await _create_background_job(service, job_id=in_progress, flow_id=uuid4(), user_id=uuid4())
    await service.append_event(in_progress, "run_started", {})
    await service.update_job_status(in_progress, JobStatus.IN_PROGRESS)

    # A RUN job briefly IN_PROGRESS with NO job_events — must be excluded.
    await service.create_job(job_id=run_in_progress, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(run_in_progress, JobStatus.IN_PROGRESS)

    # Terminal: must be excluded from the non-terminal aggregate.
    await _create_background_job(service, job_id=completed, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(completed, JobStatus.COMPLETED, finished_timestamp=True)

    async with session_scope() as session:
        counts = await count_nonterminal_jobs(session)

    assert counts == {"queued": 2, "in_progress": 1}


async def test_queued_metrics_exclude_non_workflow_jobs():
    """Ingestion jobs do not affect workflow counts or oldest queue age."""
    service = JobService()
    workflow_queued = uuid4()
    workflow_running = uuid4()
    ingestion_queued = uuid4()
    ingestion_running = uuid4()

    await _create_background_job(service, job_id=workflow_queued, flow_id=uuid4())
    await _create_background_job(service, job_id=workflow_running, flow_id=uuid4())
    await service.append_event(workflow_running, "run_started", {})
    await service.update_job_status(workflow_running, JobStatus.IN_PROGRESS)

    await _create_background_job(service, job_id=ingestion_queued, flow_id=uuid4(), job_type=JobType.INGESTION)
    await _create_background_job(service, job_id=ingestion_running, flow_id=uuid4(), job_type=JobType.INGESTION)
    await service.append_event(ingestion_running, "run_started", {})
    await service.update_job_status(ingestion_running, JobStatus.IN_PROGRESS)

    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        workflow = await session.get(Job, workflow_queued)
        ingestion = await session.get(Job, ingestion_queued)
        workflow.created_timestamp = now - timedelta(seconds=42)
        ingestion.created_timestamp = now - timedelta(hours=1)
        session.add(workflow)
        session.add(ingestion)
        await session.flush()

    async with session_scope() as session:
        counts = await count_nonterminal_jobs(session)
        age = await oldest_queued_seconds(session, now)

    assert counts == {"queued": 1, "in_progress": 1}
    assert age == pytest.approx(42.0)


async def test_oldest_queued_seconds_uses_injected_now():
    """Age of the oldest QUEUED job == now - min(created_timestamp)."""
    service = JobService()

    older = uuid4()
    newer = uuid4()
    await _create_background_job(service, job_id=older, flow_id=uuid4(), user_id=uuid4())
    await _create_background_job(service, job_id=newer, flow_id=uuid4(), user_id=uuid4())

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
    await _create_background_job(service, job_id=done, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(done, JobStatus.COMPLETED, finished_timestamp=True)

    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        age = await oldest_queued_seconds(session, now)

    assert age == 0.0


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

    await _create_background_job(service, job_id=queued_a, flow_id=uuid4(), user_id=uuid4())
    await _create_background_job(service, job_id=queued_b, flow_id=uuid4(), user_id=uuid4())

    await _create_background_job(service, job_id=in_progress, flow_id=uuid4(), user_id=uuid4())
    await service.append_event(in_progress, "run_started", {})
    await service.update_job_status(in_progress, JobStatus.IN_PROGRESS)

    await _create_background_job(service, job_id=completed, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(completed, JobStatus.COMPLETED, finished_timestamp=True)

    collector = BackgroundMetricsCollector(interval=15.0)
    async with session_scope() as session:
        await collector.collect_once(session)

    assert _gauge_value("langflow_bg_jobs", {"status": "queued", "backend": backend}) == 2
    assert _gauge_value("langflow_bg_jobs", {"status": "in_progress", "backend": backend}) == 1
    assert _gauge_value("langflow_bg_oldest_queued_seconds", {"backend": backend}) > 0


async def test_collect_once_zero_fills_dropped_status():
    """A status dropping to 0 overwrites the stale prior value (zero-fill)."""
    service = JobService()
    backend = current_backend()

    queued_a = uuid4()
    queued_b = uuid4()
    await _create_background_job(service, job_id=queued_a, flow_id=uuid4(), user_id=uuid4())
    await _create_background_job(service, job_id=queued_b, flow_id=uuid4(), user_id=uuid4())

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
    await _create_background_job(service, job_id=queued, flow_id=uuid4(), user_id=uuid4())

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
    """Create a BACKGROUND job (with a job_events row), flip FAILED, stamp error."""
    job_id = uuid4()
    await _create_background_job(service, job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.append_event(job_id, "run_started", {})
    await service.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
    await service.set_error(job_id, error)
    return job_id


async def _seed_terminal(service: JobService, status: JobStatus):
    """Create a BACKGROUND job (with a job_events row) and flip it terminal."""
    job_id = uuid4()
    await _create_background_job(service, job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.append_event(job_id, "run_started", {})
    await service.update_job_status(job_id, status, finished_timestamp=True)
    return job_id


async def _seed_run_job(service: JobService, status: JobStatus = JobStatus.COMPLETED):
    """Create a Memory-Base RUN job: created directly, terminal, NO job_events.

    Mimics build.py's second workflow row, which lacks the submission request marker.
    """
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(job_id, status, finished_timestamp=True)
    return job_id


async def test_terminal_counts_splits_outcomes():
    """terminal_counts returns the per-outcome split; started excludes only QUEUED."""
    from langflow.services.database.models.jobs.model import Job, JobEvent

    service = JobService()

    # 1 QUEUED (excluded from started), 1 IN_PROGRESS (counts toward started).
    await _create_background_job(service, job_id=uuid4(), flow_id=uuid4(), user_id=uuid4())
    in_progress = uuid4()
    await _create_background_job(service, job_id=in_progress, flow_id=uuid4(), user_id=uuid4())
    await service.append_event(in_progress, "run_started", {})
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

    # RUN jobs (no job_events) in several terminal states — must be excluded.
    await _seed_run_job(service, JobStatus.COMPLETED)
    await _seed_run_job(service, JobStatus.FAILED)

    async with session_scope() as session:
        tc = await terminal_counts(session)
        # Absolute totals in a shared test DB are not isolated across tests, so
        # assert against the actual current BACKGROUND rows (EXISTS(job_events))
        # by status to keep this robust and to exclude run jobs.
        from sqlmodel import col, func, select

        has_events = select(JobEvent.id).where(col(JobEvent.job_id) == Job.job_id).exists()

        async def _count(*statuses):
            stmt = select(func.count()).select_from(Job).where(col(Job.status).in_(statuses)).where(has_events)
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
    # The split must partition all FAILED background rows.
    assert tc["failed_worker_lost"] + tc["failed_error"] == failed
    # We seeded exactly two worker_lost rows; any pre-existing FAILED rows from
    # other tests carry a different/absent type and land in failed_error.
    assert tc["failed_worker_lost"] >= 2


async def test_terminal_counts_excludes_run_jobs():
    """A COMPLETED run job (no job_events) must NOT count toward completed.

    This is the 2x-inflation guard: build.py writes a second workflow row per
    flow build that goes straight to COMPLETED with no job_events. The collector
    must count only the marked background submission.
    """
    service = JobService()

    async with session_scope() as session:
        before = (await terminal_counts(session))["completed"]

    # One real background completion (+1) and three run-job completions (+0).
    await _seed_terminal(service, JobStatus.COMPLETED)
    await _seed_run_job(service, JobStatus.COMPLETED)
    await _seed_run_job(service, JobStatus.COMPLETED)
    await _seed_run_job(service, JobStatus.COMPLETED)

    async with session_scope() as session:
        after = (await terminal_counts(session))["completed"]

    # Only the single background job moved the needle; the three run jobs did not.
    assert after - before == 1


async def test_duration_percentiles_deterministic():
    """p50/p95 over jobs finished within the window match known durations."""
    from langflow.services.database.models.jobs.model import Job

    service = JobService()
    now = datetime.now(timezone.utc)

    # Seed five COMPLETED BACKGROUND jobs (with job_events) with known durations
    # 10..50s, all finished now.
    durations = [10, 20, 30, 40, 50]
    job_ids = []
    for _ in durations:
        jid = uuid4()
        await _create_background_job(service, job_id=jid, flow_id=uuid4(), user_id=uuid4())
        await service.append_event(jid, "run_started", {})
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
        await _create_background_job(service, job_id=jid, flow_id=uuid4(), user_id=uuid4())
        await service.append_event(jid, "run_started", {})
        await service.update_job_status(jid, JobStatus.COMPLETED, finished_timestamp=True)

    # A RUN job (no job_events) finished AT base with a 5000s duration — inside
    # the window but lacks the request marker, so it never skews p95.
    run_job = await _seed_run_job(service, JobStatus.COMPLETED)

    async with session_scope() as session:
        old_job = await session.get(Job, old)
        old_job.finished_timestamp = base - timedelta(hours=1)
        old_job.created_timestamp = base - timedelta(hours=1) - timedelta(seconds=999)
        session.add(old_job)
        recent_job = await session.get(Job, recent)
        recent_job.finished_timestamp = base
        recent_job.created_timestamp = base - timedelta(seconds=7)
        session.add(recent_job)
        run_row = await session.get(Job, run_job)
        run_row.finished_timestamp = base
        run_row.created_timestamp = base - timedelta(seconds=5000)
        session.add(run_row)
        await session.flush()

    # 60s window back from ``base``: the recent job (finished AT base) is in; the
    # old job (finished an hour earlier) is out by the SQL cutoff; the run job is
    # out by its missing request marker. Only the 7s sample remains, so p50 == p95 == 7
    # and neither the 999s nor the 5000s duration leaks in.
    async with session_scope() as session:
        p50, p95 = await duration_percentiles(session, base, window_seconds=60.0)

    assert p50 == pytest.approx(7.0, abs=1.0)
    assert p95 == pytest.approx(7.0, abs=1.0)
    assert p95 < 100.0


async def test_duration_percentiles_zero_when_none_in_window():
    """No job finished in the window -> (0.0, 0.0)."""
    service = JobService()

    jid = uuid4()
    await _create_background_job(service, job_id=jid, flow_id=uuid4(), user_id=uuid4())
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

    # A COMPLETED BACKGROUND job (with a job_events row) with a known 12s
    # duration finished now so the duration gauges are non-zero with a tight window.
    dur_job = uuid4()
    await _create_background_job(service, job_id=dur_job, flow_id=uuid4(), user_id=uuid4())
    await service.append_event(dur_job, "run_started", {})
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
    # dur_job finished AT now with a 12s run, so it qualifies for the window and
    # drives the duration gauges non-zero (exact percentile math is asserted in
    # test_duration_percentiles_deterministic; here we only prove collect_once
    # wires p50/p95 from a real finished-job sample).
    assert _gauge_value("langflow_bg_job_duration_p50_seconds", {"backend": backend}) > 0.0
    assert _gauge_value("langflow_bg_job_duration_p95_seconds", {"backend": backend}) > 0.0


async def test_a_failing_tick_does_not_end_the_collector_loop(client):  # noqa: ARG001
    """A brief database outage must cost one tick, not every future one.

    ``collect_once`` guards itself, but the session is opened outside it. Without the guard
    in ``run``, a raising ``session_scope()`` ends the task, no later tick runs for the life
    of the process, and because nothing awaits the task it surfaces only as a stray
    "Task exception was never retrieved" while the metrics quietly go flat.

    Drives the real loop and makes the first session fail, rather than asserting on the
    presence of a try block.
    """
    import langflow.services.background_execution.metrics_collector as mc

    calls = {"n": 0}
    real_session_scope = mc.session_scope

    def flaky_session_scope():
        calls["n"] += 1
        if calls["n"] == 1:
            msg = "database is briefly unavailable"
            raise RuntimeError(msg)
        return real_session_scope()

    collector = BackgroundMetricsCollector(interval=0.01)
    mc.session_scope = flaky_session_scope
    try:
        collector.start()
        # Long enough for the failing tick plus several successful ones.
        for _ in range(100):
            await asyncio.sleep(0.01)
            if calls["n"] >= 3:
                break
        await collector.stop()
    finally:
        mc.session_scope = real_session_scope

    assert calls["n"] >= 3, f"the loop stopped after the failing tick (only {calls['n']} attempts)"


async def test_orphan_sweep_does_not_turn_other_jobs_into_background_jobs():
    """Swept sync and ingestion rows have events but no background request marker."""
    service = JobService()
    background = await _seed_terminal(service, JobStatus.COMPLETED)
    others = []
    for job_type, metadata in (
        (JobType.WORKFLOW, None),
        (JobType.WORKFLOW, {"request": None}),
        (JobType.INGESTION, {"request": {}}),
    ):
        job_id = uuid4()
        await service.create_job(job_id=job_id, flow_id=uuid4(), job_type=job_type, initial_metadata=metadata)
        await service.update_job_status(job_id, JobStatus.IN_PROGRESS)
        others.append(job_id)

    assert set(await service.sweep_orphans()) == set(others)
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        for job_id in [background, *others]:
            job = await session.get(Job, job_id)
            job.finished_timestamp = now
            job.created_timestamp = now - timedelta(seconds=10 if job_id == background else 3600)
            session.add(job)
        await session.flush()
        counts = await terminal_counts(session)
        durations = await duration_percentiles(session, now, window_seconds=300)
    assert counts["started"] == counts["completed"] == 1
    assert counts["failed_worker_lost"] == 0
    assert durations == (10.0, 10.0)


@pytest.mark.parametrize("background_request", [{}, {"mode": None}, {"mode": "background"}])
async def test_stored_sync_results_do_not_count_as_background_jobs(background_request):
    """Persisting a sync result must not change background totals or durations."""
    from langflow.api.v2.workflow_execution import _persist_sync_result
    from lfx.schema.workflow import WorkflowExecutionResponse

    service = JobService()
    background = await _seed_terminal(service, JobStatus.COMPLETED)
    await service.update_job_metadata(background, {"request": background_request})
    sync_job = await _seed_run_job(service)
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        for job_id, duration in ((background, 10), (sync_job, 3600)):
            row = await session.get(Job, job_id)
            row.created_timestamp = now - timedelta(seconds=duration)
            row.finished_timestamp = now
            session.add(row)
        await session.flush()
        before = await terminal_counts(session)
        assert before["started"] == before["completed"] == 1
        assert await duration_percentiles(session, now, window_seconds=300) == (10.0, 10.0)

    sync_row = await service.get_job_by_job_id(sync_job)
    request = {"mode": "sync", "flow_id": str(sync_row.flow_id), "session_id": "sync-session"}
    response = WorkflowExecutionResponse(flow_id=str(sync_row.flow_id), status="completed")
    await _persist_sync_result(service, sync_job, response, request, sync_row.flow_id)

    async with session_scope() as session:
        stored = await session.get(Job, sync_job)
        assert stored.job_metadata["request"] == request
        assert stored.result == {"status": "completed", "outputs": []}
        assert await terminal_counts(session) == before
        assert await duration_percentiles(session, now, window_seconds=300) == (10.0, 10.0)


@pytest.mark.parametrize("sync_metadata", [None, {"request": {"mode": "sync"}}])
async def test_background_marker_identifies_queued_and_suspended_jobs_without_events(sync_metadata):
    """Only submissions contribute even before an event is appended."""
    service = JobService()
    now = datetime.now(timezone.utc)
    await _create_background_job(service, job_id=uuid4(), flow_id=uuid4())
    suspended = uuid4()
    await _create_background_job(service, job_id=suspended, flow_id=uuid4())
    await service.update_job_status(suspended, JobStatus.SUSPENDED)
    for status in (JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.SUSPENDED):
        sync_job = uuid4()
        await service.create_job(job_id=sync_job, flow_id=uuid4(), initial_metadata=sync_metadata)
        await service.update_job_status(sync_job, status)
        async with session_scope() as session:
            row = await session.get(Job, sync_job)
            row.created_timestamp = now - timedelta(hours=1)
            session.add(row)
    async with session_scope() as session:
        assert await count_nonterminal_jobs(session) == {"queued": 1, "suspended": 1}
        assert await oldest_queued_seconds(session, now) < 60
        await BackgroundMetricsCollector(interval=15).collect_once(session, now=now)
    assert _gauge_value("langflow_bg_jobs", {"status": "suspended", "backend": current_backend()}) == 1


async def test_started_count_survives_retry_requeue():
    """Requeueing a started submission must not reduce started_total."""
    service = JobService()
    job_id = uuid4()
    await _create_background_job(service, job_id=job_id, flow_id=uuid4())
    await service.update_job_metadata(job_id, {"attempt": 0})
    await service.update_job_status(job_id, JobStatus.IN_PROGRESS)
    await service.append_event(job_id, "run_started", {})
    assert await service.retry_requeue_claim(job_id, expected_attempt=0)
    async with session_scope() as session:
        assert (await terminal_counts(session))["started"] == 1


async def test_input_deadline_expiry_has_its_own_failure_reason():
    """A missed approval deadline is distinct from execution errors and timeouts."""
    service = JobService()
    job_id = uuid4()
    await _create_background_job(service, job_id=job_id, flow_id=uuid4())
    await service.update_job_status(job_id, JobStatus.SUSPENDED)
    await service.update_job_metadata(
        job_id, {"input_deadline_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
    )
    assert await service.sweep_input_deadlines() == [job_id]
    async with session_scope() as session:
        counts = await terminal_counts(session)
        await BackgroundMetricsCollector(interval=15).collect_once(session)
    assert counts["failed_input_timeout"] == 1
    assert counts["failed_error"] == counts["timed_out"] == 0
    assert (
        _counter_value("langflow_bg_jobs_failed_total", {"reason": "input_timeout", "backend": current_backend()}) == 1
    )


async def test_totals_refresh_less_often_than_gauges(monkeypatch):
    """Fast ticks update gauges without re-querying all historical outcomes."""
    import langflow.services.background_execution.metrics_collector as mc

    clock = [0.0]
    monkeypatch.setattr(mc, "monotonic", lambda: clock[0])
    calls = 0
    real_counts = mc.terminal_counts

    async def tracked_counts(session):
        nonlocal calls
        calls += 1
        return await real_counts(session)

    monkeypatch.setattr(mc, "terminal_counts", tracked_counts)
    service = JobService()
    job_id = uuid4()
    await _create_background_job(service, job_id=job_id, flow_id=uuid4())
    collector = BackgroundMetricsCollector(interval=15)
    backend = current_backend()
    async with session_scope() as session:
        await collector.collect_once(session)
    await service.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)
    for instant in (15, 150, 299):
        clock[0] = instant
        async with session_scope() as session:
            await collector.collect_once(session)
    assert calls == 1
    assert _gauge_value("langflow_bg_jobs", {"status": "queued", "backend": backend}) == 0
    assert _counter_value("langflow_bg_jobs_completed_total", {"backend": backend}) == 0
    clock[0] = 300
    async with session_scope() as session:
        await collector.collect_once(session)
    assert calls == 2
    assert _counter_value("langflow_bg_jobs_completed_total", {"backend": backend}) == 1


async def test_totals_query_failure_retries_next_tick(monkeypatch):
    """A failed full scan must not delay the retry for another five minutes."""
    import langflow.services.background_execution.metrics_collector as mc

    monkeypatch.setattr(mc, "monotonic", lambda: 0.0)
    calls = 0
    real_counts = mc.terminal_counts

    async def flaky_counts(session):
        nonlocal calls
        calls += 1
        if calls == 1:
            msg = "temporary query failure"
            raise RuntimeError(msg)
        return await real_counts(session)

    monkeypatch.setattr(mc, "terminal_counts", flaky_counts)
    collector = BackgroundMetricsCollector(interval=15)
    async with session_scope() as session:
        await collector.collect_once(session)
        await collector.collect_once(session)
    assert calls == 2


async def test_status_corrections_do_not_lower_exported_counters(monkeypatch):
    """Late cancellation and worker-loss correction cannot look like counter resets."""
    import langflow.services.background_execution.metrics_collector as mc

    clock = [0.0]
    monkeypatch.setattr(mc, "monotonic", lambda: clock[0])
    service = JobService()
    completed = await _seed_terminal(service, JobStatus.COMPLETED)
    lost = await _seed_failed(service, error={"type": "worker_lost"})
    collector = BackgroundMetricsCollector(interval=15)
    labels = {"backend": current_backend()}
    async with session_scope() as session:
        await collector.collect_once(session)
    assert _counter_value("langflow_bg_jobs_completed_total", labels) == 1
    assert _counter_value("langflow_bg_jobs_failed_total", {**labels, "reason": "worker_lost"}) == 1
    await service.update_job_status(completed, JobStatus.CANCELLED)
    clock[0] = 300
    async with session_scope() as session:
        assert (await terminal_counts(session))["completed"] == 0
        await collector.collect_once(session)
    assert _counter_value("langflow_bg_jobs_completed_total", labels) == 1
    await service.update_job_status(lost, JobStatus.COMPLETED)
    clock[0] = 600
    async with session_scope() as session:
        assert (await terminal_counts(session))["failed_worker_lost"] == 0
        await collector.collect_once(session)
    assert _counter_value("langflow_bg_jobs_failed_total", {**labels, "reason": "worker_lost"}) == 1
    assert _counter_value("langflow_bg_jobs_failed_total", {**labels, "reason": "cancelled"}) == 1


_TERMINAL_OUTCOMES = (
    ("completed", JobStatus.COMPLETED, None),
    ("failed_error", JobStatus.FAILED, "error"),
    ("failed_worker_lost", JobStatus.FAILED, "worker_lost"),
    ("failed_input_timeout", JobStatus.FAILED, "input_timed_out"),
    ("timed_out", JobStatus.TIMED_OUT, None),
    ("cancelled", JobStatus.CANCELLED, None),
)


async def _age_terminal_jobs(job_ids):
    """Put seeded terminal rows outside the retention window without waiting."""
    stamp = datetime.now(timezone.utc) - timedelta(days=40)
    async with session_scope() as session:
        for job_id in job_ids:
            job = await session.get(Job, job_id)
            job.created_timestamp = stamp - timedelta(seconds=10)
            job.finished_timestamp = stamp
            session.add(job)


def _exported_terminal_counts() -> dict[str, float]:
    labels = {"backend": current_backend()}
    return {
        "started": _counter_value("langflow_bg_jobs_started_total", labels),
        "completed": _counter_value("langflow_bg_jobs_completed_total", labels),
        **{
            key: _counter_value("langflow_bg_jobs_failed_total", {**labels, "reason": reason})
            for key, reason in (
                ("failed_error", "error"),
                ("failed_worker_lost", "worker_lost"),
                ("failed_input_timeout", "input_timeout"),
                ("timed_out", "timeout"),
                ("cancelled", "cancelled"),
            )
        },
    }


@pytest.fixture
def fresh_background_counters(monkeypatch, client):  # noqa: ARG001
    """Install real empty wrappers so a process-local high-water mark cannot hide a reset."""
    from langflow.services.telemetry.opentelemetry import ObservableCounterWrapper
    from opentelemetry.metrics import NoOpMeterProvider

    meter = NoOpMeterProvider().get_meter("background-retention-test")

    def reset():
        for name in (
            "langflow_bg_jobs_started_total",
            "langflow_bg_jobs_completed_total",
            "langflow_bg_jobs_failed_total",
        ):
            monkeypatch.setitem(
                get_telemetry_service().ot._metrics,
                name,
                ObservableCounterWrapper(name=name, description="", unit="", meter=meter),
            )

    reset()
    return reset


@pytest.mark.parametrize("collect_before_purge", [True, False])
async def test_retention_preserves_counters_and_counts_new_jobs_after_restart(
    monkeypatch, fresh_background_counters, collect_before_purge
):
    """Purged history remains cumulative even if no collector ever observed the rows."""
    import langflow.services.background_execution.metrics_collector as mc

    clock = [0.0]
    monkeypatch.setattr(mc, "monotonic", lambda: clock[0])
    service = JobService()
    old_jobs = []
    for _ in range(2):
        for _, status, error_type in _TERMINAL_OUTCOMES:
            job_id = await _seed_terminal(service, status)
            if error_type is not None:
                await service.set_error(job_id, {"type": error_type})
            old_jobs.append(job_id)
    await _age_terminal_jobs(old_jobs)
    expected = {"started": len(old_jobs), **{key: 2 for key, _, _ in _TERMINAL_OUTCOMES}}
    collector = BackgroundMetricsCollector(interval=15)
    if collect_before_purge:
        async with session_scope() as session:
            await collector.collect_once(session)
        assert _exported_terminal_counts() == expected

    assert await service.purge_terminal_jobs(older_than_days=30) == len(old_jobs)
    assert all([await service.get_job_by_job_id(job_id) is None for job_id in old_jobs])
    clock[0] = 300
    async with session_scope() as session:
        assert await terminal_counts(session) == expected
        await collector.collect_once(session)
    assert _exported_terminal_counts() == expected

    # Each live outcome count is now only one, below its pre-purge value of two.
    # A max(previous, live_count) clamp would conceal all these new executions.
    for key, status, error_type in _TERMINAL_OUTCOMES:
        job_id = await _seed_terminal(service, status)
        if error_type is not None:
            await service.set_error(job_id, {"type": error_type})
        expected[key] += 1
        expected["started"] += 1
    clock[0] = 600
    async with session_scope() as session:
        assert await terminal_counts(session) == expected
        await collector.collect_once(session)
    assert _exported_terminal_counts() == expected

    # Discard both layers of process-local state, as a replacement API worker does.
    fresh_background_counters()
    restarted_collector = BackgroundMetricsCollector(interval=15)
    async with session_scope() as session:
        await restarted_collector.collect_once(session)
    assert _exported_terminal_counts() == expected
    assert await service.purge_terminal_jobs(older_than_days=30) == 0
    async with session_scope() as session:
        assert await terminal_counts(session) == expected


async def test_retention_excludes_sync_unmarked_and_ingestion_jobs():
    """Archiving must use the same background predicate as the live aggregate."""
    service = JobService()
    background = await _seed_terminal(service, JobStatus.COMPLETED)
    job_ids = [background]
    for job_type, metadata in (
        (JobType.WORKFLOW, None),
        (JobType.WORKFLOW, {"request": None}),
        (JobType.WORKFLOW, {"request": {"mode": "sync"}}),
        (JobType.INGESTION, {"request": {}}),
    ):
        job_id = uuid4()
        await service.create_job(job_id=job_id, flow_id=uuid4(), job_type=job_type, initial_metadata=metadata)
        # Cleanup and stored sync rows can have events. Events alone do not mark a submission.
        await service.append_event(job_id, "run_started", {})
        await service.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)
        job_ids.append(job_id)
    await _age_terminal_jobs(job_ids)
    async with session_scope() as session:
        expected = await terminal_counts(session)
    assert expected["started"] == expected["completed"] == 1
    assert await service.purge_terminal_jobs(older_than_days=30) == len(job_ids)
    async with session_scope() as session:
        assert await terminal_counts(session) == expected


async def test_retention_batches_preserve_totals_without_double_counting():
    """Each committed batch transfers exactly its rows, and an empty retry adds nothing."""
    service = JobService()
    job_ids = [await _seed_terminal(service, JobStatus.COMPLETED) for _ in range(5)]
    await _age_terminal_jobs(job_ids)
    async with session_scope() as session:
        expected = await terminal_counts(session)
    for deleted in (2, 2, 1, 0):
        assert await service.purge_terminal_jobs(older_than_days=30, limit=2) == deleted
        async with session_scope() as session:
            assert await terminal_counts(session) == expected


async def test_retention_rolls_back_totals_when_delete_fails():
    """An aborted purge preserves the source rows and cannot count their history twice."""
    from sqlalchemy import event

    service = JobService()
    job_id = await _seed_terminal(service, JobStatus.COMPLETED)
    await _age_terminal_jobs([job_id])
    async with session_scope() as session:
        expected = await terminal_counts(session)
        engine = session.get_bind()

    def fail_job_delete(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("DELETE FROM job "):
            msg = "injected job deletion failure"
            raise RuntimeError(msg)

    event.listen(engine, "before_cursor_execute", fail_job_delete)
    try:
        with pytest.raises(RuntimeError, match="injected job deletion failure"):
            await service.purge_terminal_jobs(older_than_days=30)
    finally:
        event.remove(engine, "before_cursor_execute", fail_job_delete)

    assert await service.get_job_by_job_id(job_id) is not None
    assert len(await service.read_events(job_id)) == 1
    async with session_scope() as session:
        assert await terminal_counts(session) == expected
    assert await service.purge_terminal_jobs(older_than_days=30) == 1
    async with session_scope() as session:
        assert await terminal_counts(session) == expected


async def test_concurrent_retention_sweeps_preserve_totals_once():
    """API workers purging concurrently must not archive the same job twice."""
    service = JobService()
    job_ids = [await _seed_terminal(service, JobStatus.COMPLETED) for _ in range(6)]
    await _age_terminal_jobs(job_ids)
    async with session_scope() as session:
        expected = await terminal_counts(session)
    deleted = await asyncio.gather(*(JobService().purge_terminal_jobs(older_than_days=30, limit=2) for _ in range(3)))
    assert sum(deleted) == len(job_ids)
    assert await service.purge_terminal_jobs(older_than_days=30) == 0
    async with session_scope() as session:
        assert await terminal_counts(session) == expected
