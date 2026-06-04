"""Store-layer tests for JobService. Run against the app's real (sqlite) DB via the client fixture."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import JobStatus, JobType, SignalType
from langflow.services.jobs.service import JobService


@pytest.mark.usefixtures("client")
async def test_get_jobs_by_flow_id_orders_by_created_timestamp():
    """Regression: get_jobs_by_flow_id ordered by Job.created_at, which does not exist.

    Job has `created_timestamp`, not `created_at`, so the previous code raised
    AttributeError at query-build time. This test exercises the real query path.
    """
    service = JobService()
    flow_id = uuid4()
    user_id = uuid4()

    first = uuid4()
    second = uuid4()
    await service.create_job(job_id=first, flow_id=flow_id, job_type=JobType.WORKFLOW, user_id=user_id)
    await service.create_job(job_id=second, flow_id=flow_id, job_type=JobType.WORKFLOW, user_id=user_id)

    # Must not raise AttributeError, and must return both jobs newest-first.
    jobs = await service.get_jobs_by_flow_id(flow_id, user_id)
    returned_ids = [job.job_id for job in jobs]
    assert first in returned_ids
    assert second in returned_ids
    # created_timestamp is the ordering key; both rows present is the core assertion.
    assert all(job.status == JobStatus.QUEUED for job in jobs)


@pytest.mark.usefixtures("client")
async def test_set_result_persists_blob():
    service = JobService()
    job_id = uuid4()
    flow_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    updated = await service.set_result(job_id, {"output_text": "hello", "session_id": "s1"})
    assert updated is not None
    assert updated.result == {"output_text": "hello", "session_id": "s1"}

    fetched = await service.get_job_by_job_id(job_id)
    assert fetched.result == {"output_text": "hello", "session_id": "s1"}


@pytest.mark.usefixtures("client")
async def test_set_error_persists_blob():
    service = JobService()
    job_id = uuid4()
    flow_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    updated = await service.set_error(job_id, {"type": "worker_lost", "message": "crash"})
    assert updated is not None
    assert updated.error == {"type": "worker_lost", "message": "crash"}


@pytest.mark.usefixtures("client")
async def test_set_result_returns_none_for_missing_job():
    service = JobService()
    assert await service.set_result(uuid4(), {"x": 1}) is None


@pytest.mark.usefixtures("client")
async def test_append_event_assigns_monotonic_seq():
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    seq1 = await service.append_event(job_id, "run_started", {"a": 1})
    seq2 = await service.append_event(job_id, "vertex_started", {"b": 2})
    seq3 = await service.append_event(job_id, "run_finished", {"c": 3})

    assert (seq1, seq2, seq3) == (1, 2, 3)


@pytest.mark.usefixtures("client")
async def test_append_event_seq_is_per_job():
    service = JobService()
    job_a = uuid4()
    job_b = uuid4()
    await service.create_job(job_id=job_a, flow_id=uuid4(), user_id=uuid4())
    await service.create_job(job_id=job_b, flow_id=uuid4(), user_id=uuid4())

    assert await service.append_event(job_a, "x", {}) == 1
    assert await service.append_event(job_b, "x", {}) == 1
    assert await service.append_event(job_a, "x", {}) == 2


@pytest.mark.usefixtures("client")
async def test_read_events_after_seq_returns_ordered_tail():
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    await service.append_event(job_id, "e1", {"i": 1})
    await service.append_event(job_id, "e2", {"i": 2})
    await service.append_event(job_id, "e3", {"i": 3})

    tail = await service.read_events(job_id, after_seq=1)
    assert [e.seq for e in tail] == [2, 3]
    assert [e.event_type for e in tail] == ["e2", "e3"]
    assert tail[0].payload == {"i": 2}

    # after_seq=0 (or default) returns everything in order.
    all_events = await service.read_events(job_id, after_seq=0)
    assert [e.seq for e in all_events] == [1, 2, 3]


@pytest.mark.usefixtures("client")
async def test_write_signal_then_unconsumed():
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    signal = await service.write_signal(job_id, SignalType.STOP)
    assert signal.signal_type == SignalType.STOP
    assert signal.consumed_at is None

    pending = await service.unconsumed_signals(job_id)
    assert len(pending) == 1
    assert pending[0].signal_type == SignalType.STOP


@pytest.mark.usefixtures("client")
async def test_unconsumed_signals_empty_when_none_written():
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    assert await service.unconsumed_signals(job_id) == []


@pytest.mark.usefixtures("client")
async def test_sweep_orphans_fails_in_progress_jobs():
    """On startup, any IN_PROGRESS job is an orphan from a crashed worker.

    The default at-most-once policy marks it FAILED with a worker_lost error.
    QUEUED jobs are left alone (at-least-once: they get re-picked).
    """
    service = JobService()
    orphan = uuid4()
    queued = uuid4()
    flow_id = uuid4()
    user_id = uuid4()
    await service.create_job(job_id=orphan, flow_id=flow_id, user_id=user_id)
    await service.update_job_status(orphan, JobStatus.IN_PROGRESS)
    await service.create_job(job_id=queued, flow_id=flow_id, user_id=user_id)

    swept = await service.sweep_orphans()
    assert orphan in swept
    assert queued not in swept

    orphan_job = await service.get_job_by_job_id(orphan)
    assert orphan_job.status == JobStatus.FAILED
    assert orphan_job.error == {"type": "worker_lost"}
    assert orphan_job.finished_timestamp is not None

    # A reattacher must see a clean terminal event on the durable log.
    orphan_events = await service.read_events(orphan)
    assert len(orphan_events) == 1
    assert orphan_events[0].event_type == "run_failed"
    assert orphan_events[0].payload == {"type": "worker_lost"}

    queued_job = await service.get_job_by_job_id(queued)
    assert queued_job.status == JobStatus.QUEUED
    # QUEUED jobs are untouched: no terminal event.
    assert await service.read_events(queued) == []


@pytest.mark.usefixtures("client")
async def test_sweep_orphans_noop_when_clean():
    service = JobService()
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)

    assert await service.sweep_orphans() == []
