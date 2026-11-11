"""The production database queue and workers honor the shared maintenance switch."""

import asyncio
import json
from uuid import uuid4

import pytest
from langflow.services.background_execution.db_backend import DBBackgroundQueue
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.worker import WorkerJobRunner, _roster_beat, run_worker_loop
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.worker_registry.crud import register_worker
from langflow.services.database.models.worker_registry.model import WorkerRegistry, WorkerState
from langflow.services.deps import get_job_service, get_settings_service, session_scope
from langflow.services.maintenance.state import set_maintenance

pytestmark = pytest.mark.usefixtures("client")


async def _pause(*, enabled):
    async with session_scope() as session:
        await set_maintenance(session, enabled=enabled)


async def _queued_job(user_id):
    job_id = uuid4()
    await get_job_service().create_job(
        job_id=job_id, flow_id=uuid4(), user_id=user_id, initial_metadata={"request": {"stream_protocol": "langflow"}}
    )
    return job_id


async def _frames(**_kwargs):
    yield json.dumps({"event": "end", "data": {}}).encode(), "end"


async def test_database_queue_defers_claims_and_orphan_recovery_until_unfreeze(active_user):
    jobs = get_job_service()
    queued = await _queued_job(active_user.id)
    orphan = await _queued_job(active_user.id)
    await jobs.update_job_status(orphan, JobStatus.IN_PROGRESS)
    backend = DBBackgroundQueue(job_service=jobs, owner="worker:maintenance")
    before = {job_id: (await jobs.get_job_by_job_id(job_id)).model_dump() for job_id in (queued, orphan)}

    try:
        await _pause(enabled=True)
        assert await backend.claim(block_ms=0) is None
        assert await backend.requeue_lost() == []
        assert {job_id: (await jobs.get_job_by_job_id(job_id)).model_dump() for job_id in before} == before
        await _pause(enabled=False)
        assert await backend.claim(block_ms=0) == str(queued)
        await backend.requeue_lost()
        assert (await jobs.get_job_by_job_id(orphan)).status == JobStatus.FAILED
    finally:
        await _pause(enabled=False)


async def test_worker_rechecks_maintenance_after_a_job_was_claimed(active_user):
    jobs = get_job_service()
    job_id = await _queued_job(active_user.id)
    owner = "worker:claimed-before-maintenance"
    backend = DBBackgroundQueue(job_service=jobs, owner=owner)
    assert await backend.claim(block_ms=0) == str(job_id)
    runner = WorkerJobRunner(
        settings=get_settings_service().settings,
        live_bus=InMemoryLiveBus(),
        owner=owner,
        frame_source_factory=lambda **_kw: _frames,
    )

    try:
        await _pause(enabled=True)
        await runner.run(str(job_id))
        assert (await jobs.get_job_by_job_id(job_id)).status == JobStatus.QUEUED
        assert await jobs.read_events(job_id) == []
        await _pause(enabled=False)
        await runner.run(str(job_id))
        assert (await jobs.get_job_by_job_id(job_id)).status == JobStatus.COMPLETED
    finally:
        await _pause(enabled=False)


async def test_worker_polls_during_maintenance_then_runs_without_restarting(active_user, monkeypatch):
    jobs = get_job_service()
    job_id = await _queued_job(active_user.id)
    owner = "worker:maintenance-loop"
    backend = DBBackgroundQueue(job_service=jobs, owner=owner)
    polled, stop = asyncio.Event(), asyncio.Event()
    claim = backend.claim

    async def observe_claim(**kwargs):
        result = await claim(**kwargs)
        polled.set()
        return result

    async def frames(**kwargs):
        async for frame in _frames(**kwargs):
            yield frame
        stop.set()

    monkeypatch.setattr(backend, "claim", observe_claim)
    runner = WorkerJobRunner(
        settings=get_settings_service().settings,
        live_bus=InMemoryLiveBus(),
        owner=owner,
        frame_source_factory=lambda **_kw: frames,
    )
    await _pause(enabled=True)
    task = asyncio.create_task(
        run_worker_loop(backend, runner, stop_event=stop, idle_block_ms=10, owner=owner, roster_enabled=True)
    )
    try:
        await asyncio.wait_for(polled.wait(), timeout=4)
        assert (await jobs.get_job_by_job_id(job_id)).status == JobStatus.QUEUED
        async with session_scope() as session:
            assert await session.get(WorkerRegistry, owner) is None
        await _pause(enabled=False)
        await asyncio.wait_for(task, timeout=4)
        assert (await jobs.get_job_by_job_id(job_id)).status == JobStatus.COMPLETED
    finally:
        await _pause(enabled=False)
        stop.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_worker_roster_is_unchanged_while_maintenance_is_enabled():
    owner = "worker:frozen-roster"
    async with session_scope() as session:
        await register_worker(session, owner=owner, pid=1, host="fixture")
        before = (await session.get(WorkerRegistry, owner)).model_dump()
    try:
        await _pause(enabled=True)
        await _roster_beat(owner=owner, state=WorkerState.BUSY, current_job_id=uuid4())
        async with session_scope() as session:
            assert (await session.get(WorkerRegistry, owner)).model_dump() == before
    finally:
        await _pause(enabled=False)


async def test_maintenance_after_claim_defers_the_worker_heartbeat(active_user, monkeypatch):
    jobs = get_job_service()
    job_id = await _queued_job(active_user.id)
    owner = "worker:maintenance-before-heartbeat"
    backend = DBBackgroundQueue(job_service=jobs, owner=owner)
    stop = asyncio.Event()
    claim = backend.claim
    claimed_row = None

    async def claim_then_pause(**kwargs):
        nonlocal claimed_row
        result = await claim(**kwargs)
        claimed_row = (await jobs.get_job_by_job_id(job_id)).model_dump()
        await _pause(enabled=True)
        stop.set()
        return result

    monkeypatch.setattr(backend, "claim", claim_then_pause)
    runner = WorkerJobRunner(
        settings=get_settings_service().settings,
        live_bus=InMemoryLiveBus(),
        owner=owner,
        frame_source_factory=lambda **_kw: _frames,
    )
    try:
        await run_worker_loop(backend, runner, stop_event=stop, idle_block_ms=0, job_service=jobs, owner=owner)
        assert (await jobs.get_job_by_job_id(job_id)).model_dump() == claimed_row
    finally:
        await _pause(enabled=False)
