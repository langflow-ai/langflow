"""DB-backend end-to-end: facade submit (scaled) -> worker runs -> COMPLETED -> reattach.

The integration capstone, now brokerless. A scaled-mode facade submits a job
(which only persists the QUEUED row — no in-process execution), a worker loop
lease-claims it off the shared database and runs the real JobRunner via
WorkerJobRunner with a scripted frame source (no LLM), and the durable job row
reaches COMPLETED with a replayable event log. A SECOND facade instance (a
different API replica) then reattaches and replays the durable milestones —
cross-replica, no gap. The only injected piece is the scripted frame source
standing in for a live graph build (same pattern as test_service.py).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING

import pytest
from langflow.services.background_execution.db_backend import DBBackgroundQueue
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.background_execution.worker import WorkerJobRunner, run_worker_loop
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.usefixtures("client")


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode("utf-8"), event_type)


async def _scripted_source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
    yield _frame("build_start", {})
    yield _frame("end_vertex", {"id": "n1"})
    yield _frame("end", {})


async def test_submit_then_worker_runs_to_completion(active_user):
    jobs = get_job_service()
    settings = get_settings_service().settings

    # API replica A: scaled facade over the DB backend.
    backend_a = DBBackgroundQueue(job_service=jobs, owner="api:a", poll_interval_s=0.05)
    facade_a = BackgroundExecutionService(settings_service=get_settings_service(), backend=backend_a)

    flow_id = uuid.uuid4()
    job_id = await facade_a.submit(flow_id=flow_id, request={"stream_protocol": "langflow"}, user=active_user)

    # In scaled mode the API process must NOT execute — the QUEUED row IS the
    # queue entry, waiting for a worker.
    queued = await jobs.get_job_by_job_id(job_id)
    assert queued.status == JobStatus.QUEUED

    # Worker (separate loop): lease-claim + run the real JobRunner with a
    # scripted source. Durable milestones land in job_events.
    worker_backend = DBBackgroundQueue(job_service=jobs, owner="worker:w1", poll_interval_s=0.05)
    worker_runner = WorkerJobRunner(
        settings=settings,
        live_bus=InMemoryLiveBus(),
        frame_source_factory=lambda **_kw: _scripted_source,
        owner="worker:w1",
    )
    stop_event = asyncio.Event()

    async def stop_when_done():
        for _ in range(200):
            refreshed = await jobs.get_job_by_job_id(job_id)
            if refreshed.status == JobStatus.COMPLETED:
                stop_event.set()
                return
            await asyncio.sleep(0.05)
        stop_event.set()

    driver = asyncio.create_task(stop_when_done())
    await run_worker_loop(
        worker_backend,
        worker_runner,
        stop_event=stop_event,
        idle_block_ms=50,
        job_service=jobs,
        owner="worker:w1",
    )
    await driver

    refreshed = await jobs.get_job_by_job_id(job_id)
    assert refreshed.status == JobStatus.COMPLETED
    assert refreshed.result is not None

    # API replica B: a fresh facade + backend that never ran the job reattaches
    # and replays the durable milestones off the shared database.
    backend_b = DBBackgroundQueue(job_service=jobs, owner="api:b", poll_interval_s=0.05)
    facade_b = BackgroundExecutionService(settings_service=get_settings_service(), backend=backend_b)
    seen = [chunk async for chunk in facade_b.events(job_id, last_event_id=None, user=active_user)]

    assert any(b"build_start" in c for c in seen)
    assert any(b"end_vertex" in c for c in seen)


async def test_booting_watchdog_leaves_a_live_workers_job_alone(active_user):
    """A second worker's startup reconcile must not reap a job mid-run on worker A."""
    jobs = get_job_service()
    settings = get_settings_service().settings

    backend = DBBackgroundQueue(job_service=jobs, owner="api:a", poll_interval_s=0.05)
    facade = BackgroundExecutionService(settings_service=get_settings_service(), backend=backend)
    job_id = await facade.submit(flow_id=uuid.uuid4(), request={"stream_protocol": "langflow"}, user=active_user)

    in_flight = asyncio.Event()
    release = asyncio.Event()

    def _holding_source_factory(**_kw):
        async def _source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
            yield _frame("build_start", {})
            in_flight.set()
            await release.wait()
            yield _frame("end", {})

        return _source

    worker_backend = DBBackgroundQueue(job_service=jobs, owner="worker:a", poll_interval_s=0.05)
    worker_runner = WorkerJobRunner(
        settings=settings,
        live_bus=InMemoryLiveBus(),
        frame_source_factory=_holding_source_factory,
        owner="worker:a",
    )
    stop_event = asyncio.Event()
    loop_task = asyncio.create_task(
        run_worker_loop(
            worker_backend,
            worker_runner,
            stop_event=stop_event,
            idle_block_ms=50,
            job_service=jobs,
            owner="worker:a",
        )
    )

    await asyncio.wait_for(in_flight.wait(), timeout=10.0)
    # Worker B boots mid-run: its startup reconcile sees a FRESH lease (worker
    # A heartbeats while running) and must leave the job alone.
    booting = DBBackgroundQueue(job_service=jobs, owner="worker:b")
    await booting.requeue_lost(lease_ttl_s=45.0)
    live = await jobs.get_job_by_job_id(job_id)
    assert live.status == JobStatus.IN_PROGRESS

    release.set()
    for _ in range(200):
        refreshed = await jobs.get_job_by_job_id(job_id)
        if refreshed.status == JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.05)
    stop_event.set()
    await asyncio.wait_for(loop_task, timeout=10.0)

    assert (await jobs.get_job_by_job_id(job_id)).status == JobStatus.COMPLETED
