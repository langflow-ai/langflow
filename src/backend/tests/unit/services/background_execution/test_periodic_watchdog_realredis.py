"""The worker loop's PERIODIC watchdog reconciles a dead worker's orphan.

Proves the watchdog runs on an interval inside the loop (not just at startup),
so a worker that died mid-run is reconciled under a STEADY fleet WITHOUT any new
worker process starting. Real redis + real DB.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.background_execution.worker import run_worker_loop
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service

pytestmark = pytest.mark.usefixtures("client")


def _scoped_backend(real_redis, jobs):
    prefix = real_redis._bgtest_prefix
    backend = RedisBackgroundQueue(client=real_redis, job_service=jobs, startup_grace_s=10.0)
    backend.claim_queue.pending_key = f"{prefix}pending"
    backend.claim_queue.processing_key = f"{prefix}processing"
    return backend


class _IdleRunner:
    """A runner the loop never actually drives (queue stays empty)."""

    async def run(self, job_id):  # noqa: ARG002 - matches the runner contract
        return


async def test_periodic_watchdog_reconciles_orphan_without_restart(real_redis, active_user):
    jobs = get_job_service()
    backend = _scoped_backend(real_redis, jobs)

    # A previously-dead worker left an IN_PROGRESS job on the processing list with
    # a stale lease. No new worker process starts — the SAME running loop's
    # periodic watchdog must reap it.
    orphan = uuid.uuid4()
    await jobs.create_job(job_id=orphan, flow_id=uuid.uuid4(), user_id=active_user.id)
    await jobs.update_job_status(orphan, JobStatus.IN_PROGRESS)
    old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await jobs.update_job_metadata(orphan, {"owner": "dead", "heartbeat_at": old})
    await real_redis.lpush(backend.claim_queue.processing_key, str(orphan))

    stop_event = asyncio.Event()

    async def _watch_then_stop():
        # Wait until the periodic watchdog has reaped the orphan, then stop.
        for _ in range(100):
            job = await jobs.get_job_by_job_id(orphan)
            if job.status == JobStatus.FAILED:
                break
            await asyncio.sleep(0.05)
        stop_event.set()

    driver = asyncio.create_task(_watch_then_stop())
    # Short watchdog interval so the test does not wait long.
    await asyncio.wait_for(
        run_worker_loop(
            backend,
            _IdleRunner(),
            stop_event=stop_event,
            idle_block_ms=50,
            job_service=jobs,
            lease_ttl_s=30.0,
            watchdog_interval_s=0.2,
        ),
        timeout=15,
    )
    await driver

    job = await jobs.get_job_by_job_id(orphan)
    assert job.status == JobStatus.FAILED
    assert (job.error or {}).get("type") == "worker_lost"
    assert str(orphan) not in await backend.claim_queue.processing_ids()
