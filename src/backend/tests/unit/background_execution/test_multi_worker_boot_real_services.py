"""Crown jewel: a booting worker's sweep must not touch a sibling's live job.

Reproduces the BLOCKER/HIGH where ``sweep_orphans`` marked EVERY IN_PROGRESS row
FAILED(worker_lost). Under ``gunicorn -w N`` a booting worker B would flip worker
A's just-claimed, actively-running, freshly-heartbeated job FAILED mid-run,
inject a phantom terminal event into A's live durable log, and race A's real
terminal write. With lease+heartbeat liveness the sweep only reconciles
GENUINELY orphaned rows (stale/absent heartbeat), so B leaves A's live job alone.

Real SQLite AND real Postgres via the real-service fixture.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.jobs.model import JobStatus

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.real_services


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode("utf-8"), event_type)


async def test_booting_worker_sweep_spares_live_heartbeated_job(real_services_job_service):
    job_service = real_services_job_service
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    # Gate that holds worker A "mid-run" while worker B boots and sweeps.
    release = asyncio.Event()
    side_effect_runs = 0

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        nonlocal side_effect_runs
        side_effect_runs += 1
        yield _frame("build_start", {})
        # Park here (job is IN_PROGRESS + heartbeating) until the test releases it.
        await release.wait()
        yield _frame("end", {})

    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    bus = InMemoryLiveBus()
    # Worker A: a fast heartbeat so the row is demonstrably fresh by the time B sweeps.
    runner_a = JobRunner(
        job_service=job_service,
        live_bus=bus,
        adapter=adapter,
        frame_source=source,
        owner="worker-A",
        heartbeat_interval_s=0.1,
    )
    run_a = asyncio.create_task(runner_a.run(job_id=job_id, source_kwargs={}))

    try:
        # Wait until A is IN_PROGRESS and has stamped at least one heartbeat.
        for _ in range(100):
            job = await job_service.get_job_by_job_id(job_id)
            meta = job.job_metadata or {}
            if job.status == JobStatus.IN_PROGRESS and meta.get("heartbeat_at"):
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("worker A never reached IN_PROGRESS with a heartbeat")

        # Worker B boots and runs the liveness-aware sweep. A's heartbeat is fresh
        # (well under the lease TTL), so B must NOT reconcile A's job.
        swept = await job_service.sweep_orphans(lease_ttl_s=30.0)
        assert job_id not in swept

        job = await job_service.get_job_by_job_id(job_id)
        assert job.status == JobStatus.IN_PROGRESS  # not flipped FAILED mid-run
        # No phantom terminal event injected into A's live durable log.
        events = await job_service.read_events(job_id)
        assert all(e.event_type != "run_failed" for e in events)
    finally:
        release.set()
        await asyncio.wait_for(run_a, timeout=10)

    # A finished cleanly; the flow ran exactly once (no second run from B).
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    assert side_effect_runs == 1
