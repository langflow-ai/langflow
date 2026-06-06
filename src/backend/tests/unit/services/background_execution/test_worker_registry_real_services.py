"""Real-process proof of the worker_registry lifecycle on real Postgres + Redis.

A separate ``langflow worker`` OS process registers, flips busy/idle around a real
job, and deregisters on a graceful stop.

The unit tests drive the registry wiring with a stub runner (``test_worker_loop_registry``),
so they prove the loop calls register/heartbeat/deregister but not that a REAL
``langflow worker`` subprocess actually writes the rows the fleet dashboard and
the collector's ``workers_online/busy/idle`` gauges read. This closes that gap
end to end against real Postgres + Redis:

* register -> exactly one IDLE row with a real pid/host
* claim a real (slow, no-LLM) job -> the row flips to BUSY with ``current_job_id``
* the collector's ``count_by_state`` derivation sees online/busy/idle correctly
* the job completes -> the row returns to IDLE
* a graceful SIGTERM -> the row is deleted (deregistered)

Requires LANGFLOW_TEST_DATABASE_URI (real Postgres) and LANGFLOW_TEST_REDIS_URL
(real Redis). Skips otherwise. Every wait is bounded so a regression fails loudly.
"""

from __future__ import annotations

import asyncio
import os
import signal
import time
from datetime import datetime, timedelta, timezone

import pytest
from langflow.services.background_execution.worker_registry import WorkerRegistryService
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.worker_registry.model import WorkerRegistry, WorkerState
from langflow.services.deps import session_scope
from sqlmodel import col, select

from ._subprocess_harness import setup_worker_harness

# Match the collector's window: online == heartbeat within 3x the default interval.
_ONLINE_WINDOW = timedelta(seconds=30)


def _require_real_instances():
    pg = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    redis = os.environ.get("LANGFLOW_TEST_REDIS_URL")
    if not pg:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI not set; real-process registry proof requires real Postgres")
    if not redis:
        pytest.skip("LANGFLOW_TEST_REDIS_URL not set; real-process registry proof requires real Redis")
    return pg, redis


async def _registry_rows() -> list[WorkerRegistry]:
    async with session_scope() as session:
        return list((await session.exec(select(WorkerRegistry))).all())


async def _clear_registry() -> None:
    async with session_scope() as session:
        for row in (await session.exec(select(WorkerRegistry))).all():
            await session.delete(row)
        await session.commit()


async def _counts() -> dict:
    async with session_scope() as session:
        return await WorkerRegistryService().count_by_state(
            session, now=datetime.now(timezone.utc), online_window=_ONLINE_WINDOW
        )


async def _wait_until(predicate, *, timeout: float = 60.0, interval: float = 0.5):
    """Poll ``predicate`` until it returns a non-None value or the deadline passes."""
    deadline = time.monotonic() + timeout
    result = None
    while time.monotonic() < deadline:
        result = await predicate()
        if result is not None:
            return result
        await asyncio.sleep(interval)
    return None


@pytest.mark.real_services
async def test_real_worker_registers_runs_and_deregisters():
    pg, redis = _require_real_instances()
    harness = await setup_worker_harness(pg, redis, redis_db=13)
    try:
        # Isolate from any rows a previous run's crashed worker may have left.
        await _clear_registry()
        user_id, flow_id = await harness.seed_slow_flow()

        # 1. REGISTER: a real worker process writes exactly one IDLE row.
        proc = harness.spawn_worker(idle_block_ms=200)
        assert proc.poll() is None, "worker subprocess failed to start"

        async def _one_idle_row():
            rows = await _registry_rows()
            return rows[0] if len(rows) == 1 and rows[0].state == WorkerState.IDLE else None

        row = await _wait_until(_one_idle_row, timeout=90.0)
        assert row is not None, f"worker did not register an IDLE row; output:\n{harness.drain_worker_output()}"
        assert row.owner.startswith("worker:"), f"unexpected owner {row.owner}"
        assert row.pid > 0
        assert row.host
        assert row.current_job_id is None
        assert await _counts() == {"online": 1, "busy": 0, "idle": 1}

        # 2. BUSY: submit a small backlog of real slow jobs so the worker is busy
        # long enough to observe (a single sub-second job's BUSY window can slip
        # between polls; a backlog keeps it busy for several seconds). The row
        # flips to BUSY with a current_job_id drawn from what we submitted.
        job_ids = {await harness.submit_job(flow_id=flow_id, user_id=user_id) for _ in range(6)}

        async def _busy_with_submitted_job():
            rows = await _registry_rows()
            if len(rows) != 1 or rows[0].state != WorkerState.BUSY:
                return None
            return rows[0] if rows[0].current_job_id in job_ids else None

        busy = await _wait_until(_busy_with_submitted_job, timeout=60.0, interval=0.2)
        assert busy is not None, f"worker did not flip to BUSY with a submitted job; rows={await _registry_rows()}"
        busy_counts = await _counts()
        assert busy_counts == {"online": 1, "busy": 1, "idle": 0}, busy_counts

        # 3. IDLE: once the whole backlog drains, the worker returns to IDLE.
        async def _all_done():
            async with session_scope() as session:
                done = (
                    await session.exec(
                        select(Job.job_id).where(col(Job.job_id).in_(job_ids)).where(Job.status == JobStatus.COMPLETED)
                    )
                ).all()
            return True if len(done) == len(job_ids) else None

        assert await _wait_until(_all_done, timeout=180.0) is not None, "the submitted backlog did not all complete"

        async def _idle_again():
            rows = await _registry_rows()
            return (
                rows[0]
                if len(rows) == 1 and rows[0].state == WorkerState.IDLE and rows[0].current_job_id is None
                else None
            )

        assert await _wait_until(_idle_again, timeout=60.0) is not None, "worker did not return to IDLE after draining"

        # 4. DEREGISTER: a graceful SIGTERM deletes the row (not just marks it stale).
        harness.signal_group(proc, signal.SIGTERM)

        async def _no_rows():
            return [] if len(await _registry_rows()) == 0 else None

        gone = await _wait_until(_no_rows, timeout=60.0)
        assert gone is not None, f"worker did not deregister on graceful stop; rows={await _registry_rows()}"
        assert await _counts() == {"online": 0, "busy": 0, "idle": 0}
    finally:
        await harness.teardown()
