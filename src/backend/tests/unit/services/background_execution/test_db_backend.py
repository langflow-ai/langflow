"""DBBackgroundQueue: the durable job table as the work queue.

Claim semantics (FIFO, single-flight, lease-aware) and the polling event tail.
Everything runs against the ordinary test DB — the whole point of the DB queue
is that there is no broker to fake.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from langflow.services.background_execution.db_backend import DBBackgroundQueue
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service

pytestmark = [pytest.mark.usefixtures("client"), pytest.mark.asyncio]


async def _make_queued_job(user_id, *, flow_id=None):
    jobs = get_job_service()
    job_id = uuid.uuid4()
    await jobs.create_job(job_id=job_id, flow_id=flow_id or uuid.uuid4(), user_id=user_id)
    return jobs, job_id


async def test_claim_is_fifo_and_leaves_the_row_queued(active_user):
    jobs, first = await _make_queued_job(active_user.id)
    _, second = await _make_queued_job(active_user.id)

    backend = DBBackgroundQueue(job_service=jobs, owner="worker:a")
    claimed = await backend.claim(block_ms=0)

    assert claimed == str(first), f"expected FIFO claim of {first}, got {claimed}"
    row = await jobs.get_job_by_job_id(first)
    # The claim stamps the lease but leaves the row QUEUED: the runner's
    # execute_with_status does the real QUEUED->IN_PROGRESS flip, so a worker
    # crash before start leaves the job re-claimable once the lease is stale.
    assert row.status == JobStatus.QUEUED
    meta = row.job_metadata or {}
    assert meta.get("owner") == "worker:a"
    assert meta.get("heartbeat_at") is not None
    # The second job is untouched and next in line.
    assert (await backend.claim(block_ms=0)) == str(second)


async def test_concurrent_claimers_get_distinct_jobs(active_user):
    jobs, first = await _make_queued_job(active_user.id)
    _, second = await _make_queued_job(active_user.id)

    backend_a = DBBackgroundQueue(job_service=jobs, owner="worker:a")
    backend_b = DBBackgroundQueue(job_service=jobs, owner="worker:b")
    claimed = await asyncio.gather(backend_a.claim(block_ms=0), backend_b.claim(block_ms=0))

    # Single-flight: the two workers must not claim the same job.
    assert set(claimed) == {str(first), str(second)}


async def test_fresh_lease_blocks_reclaim_until_stale(active_user):
    jobs, job_id = await _make_queued_job(active_user.id)

    backend_a = DBBackgroundQueue(job_service=jobs, owner="worker:a")
    assert await backend_a.claim(block_ms=0) == str(job_id)

    # Worker B polls while A's lease is fresh: nothing claimable.
    backend_b = DBBackgroundQueue(job_service=jobs, owner="worker:b")
    assert await backend_b.claim(block_ms=0) is None

    # Once A's lease goes stale (dead worker), the SAME QUEUED row is claimable
    # again — no strand-recovery pass needed, the row is the queue.
    backend_b_stale = DBBackgroundQueue(job_service=jobs, owner="worker:b", lease_ttl_s=0.0)
    assert await backend_b_stale.claim(block_ms=0) == str(job_id)


async def test_claim_returns_none_and_sleeps_out_block_window(active_user):  # noqa: ARG001
    backend = DBBackgroundQueue(job_service=get_job_service(), owner="worker:a")
    loop = asyncio.get_running_loop()
    start = loop.time()
    assert await backend.claim(block_ms=100) is None
    # The empty-queue path sleeps out the block window (the poll cadence), so
    # the worker loop does not hot-spin.
    assert loop.time() - start >= 0.09


async def test_enqueue_is_a_noop(active_user):
    jobs, job_id = await _make_queued_job(active_user.id)
    backend = DBBackgroundQueue(job_service=jobs, owner="worker:a")
    await backend.enqueue(str(job_id))
    # The QUEUED row submit persisted IS the enqueue; nothing else changes.
    assert (await jobs.get_job_by_job_id(job_id)).status == JobStatus.QUEUED


async def test_events_replays_then_polls_live_rows_until_terminal(active_user):
    jobs, job_id = await _make_queued_job(active_user.id)
    await jobs.append_event(job_id, "build_start", {"a": 1})

    backend = DBBackgroundQueue(job_service=jobs, poll_interval_s=0.05)

    async def _consume():
        return [e async for e in backend.events(str(job_id))]

    consumer = asyncio.create_task(_consume())
    # Let the tail replay the first event and enter its poll loop.
    await asyncio.sleep(0.15)
    # A live milestone lands while the tail is attached...
    await jobs.append_event(job_id, "end_vertex", {"id": "n1"})
    # ...then the run finishes: terminal event first, then the status flip
    # (the runner's ordering), so the final drain cannot miss the milestone.
    await jobs.append_event(job_id, "end", {})
    await jobs.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)

    events = await asyncio.wait_for(consumer, timeout=5)
    types = [e.event_type for e in events]
    assert types == ["build_start", "end_vertex", "end"]
    # Seqs are strictly increasing — the Last-Event-ID cursor contract.
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)


async def test_events_resumes_after_last_event_id_without_duplicates(active_user):
    jobs, job_id = await _make_queued_job(active_user.id)
    first_seq = await jobs.append_event(job_id, "build_start", {})
    await jobs.append_event(job_id, "end_vertex", {"id": "n1"})
    await jobs.append_event(job_id, "end", {})
    await jobs.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)

    backend = DBBackgroundQueue(job_service=jobs, poll_interval_s=0.05)
    events = [e async for e in backend.events(str(job_id), last_event_id=first_seq)]
    types = [e.event_type for e in events]
    # Resume strictly after the cursor: no replayed build_start, no gap.
    assert types == ["end_vertex", "end"]


async def test_events_grace_pass_catches_terminal_event_appended_after_status_flip(active_user):
    """CANCELLED/TIMED_OUT/worker_lost flip status BEFORE their terminal event lands.

    A tail that returned on the first terminal observation would end without the
    terminal milestone. The grace pass (drain, wait one poll interval, drain
    again) must deliver an event appended shortly after the status flip.
    """
    jobs, job_id = await _make_queued_job(active_user.id)
    await jobs.append_event(job_id, "build_start", {})
    # The status is already terminal, but the terminal event has NOT landed yet
    # (the runner's finally appends it moments later).
    await jobs.update_job_status(job_id, JobStatus.CANCELLED, finished_timestamp=True)

    backend = DBBackgroundQueue(job_service=jobs, poll_interval_s=0.2)

    async def _consume():
        return [e async for e in backend.events(str(job_id))]

    consumer = asyncio.create_task(_consume())
    # Land the terminal event inside the grace window.
    await asyncio.sleep(0.05)
    await jobs.append_event(job_id, "run_cancelled", {"type": "cancelled"})

    events = await asyncio.wait_for(consumer, timeout=5)
    types = [e.event_type for e in events]
    assert types == ["build_start", "run_cancelled"], f"terminal event missed by the tail: {types}"


async def test_events_on_terminal_job_ends_without_hanging(active_user):
    jobs, job_id = await _make_queued_job(active_user.id)
    await jobs.append_event(job_id, "end", {})
    await jobs.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)

    backend = DBBackgroundQueue(job_service=jobs, poll_interval_s=0.05)
    events = await asyncio.wait_for(
        _collect(backend.events(str(job_id))),
        timeout=5,
    )
    assert [e.event_type for e in events] == ["end"]


async def _collect(events_iter):
    return [item async for item in events_iter]
