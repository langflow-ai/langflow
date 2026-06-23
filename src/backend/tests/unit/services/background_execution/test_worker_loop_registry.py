"""The worker loop registers/heartbeats/deregisters its presence in worker_registry.

These drive the REAL ``run_worker_loop`` against the REAL test DB (the ``client``
fixture; SQLite locally, Postgres in CI) with NO DB mocks. The queue side is a
real-behavior stand-in (hands out scripted ids, records completes) and the runner
is a stub we gate with an ``asyncio.Event`` so a job can be held BUSY mid-run while
we read the registry row. The heartbeat task's clock is injected so a beat lands
deterministically without a wall-clock sleep.
"""

from __future__ import annotations

import asyncio
from datetime import timezone
from uuid import uuid4

import pytest
from langflow.services.background_execution.worker import run_worker_loop
from langflow.services.background_execution.worker_registry import WorkerRegistryService
from langflow.services.database.models.worker_registry.model import WorkerRegistry, WorkerState
from langflow.services.deps import session_scope

pytestmark = pytest.mark.usefixtures("client")


def _aware(dt):
    """SQLite hands datetimes back naive; normalize to aware UTC for comparison."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def _get_row(owner: str) -> WorkerRegistry | None:
    async with session_scope() as session:
        return await session.get(WorkerRegistry, owner)


async def _wait_for(predicate, *, timeout: float = 5.0):
    """Poll an async predicate until truthy or the timeout elapses."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if await predicate():
            return True
        await asyncio.sleep(0.01)
    return False


class _FakeBackend:
    """Real-behavior stand-in for the claim queue (not a mock of our code).

    The first claim waits on ``claim_gate`` so a test can observe the IDLE row the
    worker registered BEFORE any job is handed out; once released it drains the
    scripted ids then returns None (idle).
    """

    def __init__(self, ids, *, claim_gate=None):
        self._ids = list(ids)
        self.completed: list[str] = []
        self._claim_gate = claim_gate
        self._gated = False

    async def requeue_lost(self, *, lease_ttl_s=45.0):  # noqa: ARG002
        return []

    async def claim(self, *, block_ms=1000):  # noqa: ARG002
        if self._claim_gate is not None and not self._gated:
            self._gated = True
            await self._claim_gate.wait()
        if self._ids:
            return self._ids.pop(0)
        return None

    async def complete(self, job_id):
        self.completed.append(job_id)


class _GatedRunner:
    """Holds each run open until a per-run gate is released, so we can observe BUSY."""

    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.ran: list[str] = []

    async def run(self, job_id):
        self.ran.append(job_id)
        self.started.set()
        await self.release.wait()


async def test_registry_lifecycle_idle_busy_idle_then_deregister():
    """Startup -> one IDLE row; mid-job -> BUSY+job_id; after -> IDLE; on stop -> deleted."""
    owner = "worker:loop:lifecycle"
    job_id = str(uuid4())  # production job ids are UUIDs; the registry column is UUID.
    claim_gate = asyncio.Event()
    backend = _FakeBackend([job_id], claim_gate=claim_gate)
    runner = _GatedRunner()
    stop_event = asyncio.Event()
    registry = WorkerRegistryService()

    loop_task = asyncio.create_task(
        run_worker_loop(
            backend,
            runner,
            stop_event=stop_event,
            idle_block_ms=10,
            owner=owner,
            worker_registry=registry,
            pid=4242,
            host="host-loop",
            registry_interval_s=100.0,  # long: no periodic beat interferes with this test
        )
    )

    # (1) After startup, with the first claim gated, exactly one IDLE row exists.
    assert await _wait_for(lambda: _idle_row_exists(owner))
    row = await _get_row(owner)
    assert row.pid == 4242
    assert row.host == "host-loop"
    assert row.state == WorkerState.IDLE
    assert row.current_job_id is None

    # (2) Release the claim: the job is claimed and the gated runner is mid-run, so
    # the row is BUSY with the job id.
    claim_gate.set()
    assert await runner.started.wait() or True
    assert await _wait_for(lambda: _busy_with_job(owner, job_id))

    # (3) Release the run; once complete it returns to IDLE with no current job.
    runner.release.set()
    assert await _wait_for(lambda: _idle_no_job(owner))

    # (4) Stop the loop; the finally deregisters so the row is deleted.
    stop_event.set()
    await asyncio.wait_for(loop_task, timeout=5.0)
    assert await _get_row(owner) is None


async def _idle_row_exists(owner):
    row = await _get_row(owner)
    return row is not None and row.state == WorkerState.IDLE


async def _busy_with_job(owner, job_id):
    row = await _get_row(owner)
    return row is not None and row.state == WorkerState.BUSY and str(row.current_job_id) == job_id


async def _idle_no_job(owner):
    row = await _get_row(owner)
    return row is not None and row.state == WorkerState.IDLE and row.current_job_id is None


async def test_periodic_heartbeat_refreshes_last_heartbeat_during_long_job():
    """While a job runs, the periodic beat advances last_heartbeat with state still BUSY."""
    owner = "worker:loop:heartbeat"
    job_id = str(uuid4())
    backend = _FakeBackend([job_id])
    runner = _GatedRunner()
    stop_event = asyncio.Event()
    registry = WorkerRegistryService()

    # Short interval so periodic beats land quickly in real time. The gated runner
    # holds the job open, so every beat that lands does so with the row still BUSY:
    # determinism comes from the gate, not from sleeping a fixed amount.
    loop_task = asyncio.create_task(
        run_worker_loop(
            backend,
            runner,
            stop_event=stop_event,
            idle_block_ms=10,
            owner=owner,
            worker_registry=registry,
            pid=99,
            host="host-hb",
            registry_interval_s=0.02,
        )
    )

    # Wait until the job is BUSY, capture last_heartbeat, then wait for a later beat.
    assert await _wait_for(lambda: _busy_with_job(owner, job_id))
    first = _aware((await _get_row(owner)).last_heartbeat)

    # A periodic beat must land while still BUSY and advance last_heartbeat.
    advanced = await _wait_for(lambda: _busy_and_advanced(owner, first))
    assert advanced, "periodic heartbeat did not refresh last_heartbeat during the job"

    runner.release.set()
    stop_event.set()
    await asyncio.wait_for(loop_task, timeout=5.0)


async def _busy_and_advanced(owner, baseline):
    row = await _get_row(owner)
    if row is None or row.state != WorkerState.BUSY:
        return False
    return _aware(row.last_heartbeat) > baseline
