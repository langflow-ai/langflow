"""Hard-proof store tests: JobService methods against REAL SQLite and REAL Postgres.

These bind ``session_scope()`` to a real, migrated database (via the
``hard_proof_job_service`` fixture) so every store method is exercised on both
engines, not just the temp-file SQLite the ``client`` fixture provides. Running
the real Alembic migrations against both engines here also re-proves the schema
applies on Postgres (JSONB columns, the execution_signal_type_enum, the
uq_job_events_job_id_seq unique constraint).
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import JobStatus, SignalType


@pytest.mark.hard_proof
@pytest.mark.no_blockbuster
async def test_set_result_and_error_persist(hard_proof_job_service) -> None:
    service = hard_proof_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    await service.set_result(job_id, {"output_text": "hi", "session_id": "s1"})
    await service.set_error(job_id, {"type": "boom", "message": "x"})

    fetched = await service.get_job_by_job_id(job_id)
    assert fetched.result == {"output_text": "hi", "session_id": "s1"}
    assert fetched.error == {"type": "boom", "message": "x"}


@pytest.mark.hard_proof
@pytest.mark.no_blockbuster
async def test_append_and_read_events_ordered(hard_proof_job_service) -> None:
    service = hard_proof_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    assert await service.append_event(job_id, "e1", {"i": 1}) == 1
    assert await service.append_event(job_id, "e2", {"i": 2}) == 2
    assert await service.append_event(job_id, "e3", {"i": 3}) == 3

    tail = await service.read_events(job_id, after_seq=1)
    assert [e.seq for e in tail] == [2, 3]
    assert tail[0].payload == {"i": 2}


@pytest.mark.hard_proof
@pytest.mark.no_blockbuster
async def test_append_event_seq_is_per_job(hard_proof_job_service) -> None:
    service = hard_proof_job_service
    job_a = uuid4()
    job_b = uuid4()
    await service.create_job(job_id=job_a, flow_id=uuid4(), user_id=uuid4())
    await service.create_job(job_id=job_b, flow_id=uuid4(), user_id=uuid4())

    assert await service.append_event(job_a, "x", {}) == 1
    assert await service.append_event(job_b, "x", {}) == 1
    assert await service.append_event(job_a, "x", {}) == 2


@pytest.mark.hard_proof
@pytest.mark.no_blockbuster
async def test_append_event_concurrent_appends_all_land_gap_free(hard_proof_job_service) -> None:
    """Concurrent appends to one job must ALL land, gap-free (retry on UNIQUE collision).

    Regression for the seq race: SELECT max(seq)+1 then INSERT collides under
    contention; without retry the losers' events were silently dropped.
    """
    service = hard_proof_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    n = 12
    seqs = await asyncio.gather(*(service.append_event(job_id, f"e{i}", {"i": i}) for i in range(n)))

    # Every append returned a distinct seq and the set is exactly 1..n (no loss, no gaps).
    assert sorted(seqs) == list(range(1, n + 1)), f"returned seqs not gap-free: {sorted(seqs)}"
    events = await service.read_events(job_id)
    assert [e.seq for e in events] == list(range(1, n + 1)), "persisted events not gap-free"
    assert len(events) == n


@pytest.mark.hard_proof
@pytest.mark.no_blockbuster
async def test_write_and_read_signals(hard_proof_job_service) -> None:
    service = hard_proof_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    assert await service.unconsumed_signals(job_id) == []
    signal = await service.write_signal(job_id, SignalType.STOP)
    assert signal.signal_type == SignalType.STOP
    assert signal.consumed_at is None

    pending = await service.unconsumed_signals(job_id)
    assert len(pending) == 1
    assert pending[0].signal_type == SignalType.STOP


@pytest.mark.hard_proof
@pytest.mark.no_blockbuster
async def test_sweep_orphans_reconciles_in_progress(hard_proof_job_service) -> None:
    service = hard_proof_job_service
    orphan = uuid4()
    queued = uuid4()
    await service.create_job(job_id=orphan, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(orphan, JobStatus.IN_PROGRESS)
    await service.create_job(job_id=queued, flow_id=uuid4(), user_id=uuid4())

    swept = await service.sweep_orphans()
    assert orphan in swept
    assert queued not in swept

    orphan_job = await service.get_job_by_job_id(orphan)
    assert orphan_job.status == JobStatus.FAILED
    assert orphan_job.error == {"type": "worker_lost"}
    assert orphan_job.finished_timestamp is not None

    events = await service.read_events(orphan)
    assert [e.event_type for e in events] == ["run_failed"]
    assert events[0].payload == {"type": "worker_lost"}

    queued_job = await service.get_job_by_job_id(queued)
    assert queued_job.status == JobStatus.QUEUED


@pytest.mark.hard_proof
@pytest.mark.no_blockbuster
async def test_get_jobs_by_flow_id_orders_by_created_timestamp(hard_proof_job_service) -> None:
    """Regression on real engines: ordering by created_timestamp must not raise."""
    service = hard_proof_job_service
    flow_id = uuid4()
    user_id = uuid4()
    first = uuid4()
    second = uuid4()
    await service.create_job(job_id=first, flow_id=flow_id, user_id=user_id)
    await service.create_job(job_id=second, flow_id=flow_id, user_id=user_id)

    jobs = await service.get_jobs_by_flow_id(flow_id, user_id)
    returned = {job.job_id for job in jobs}
    assert {first, second} <= returned
