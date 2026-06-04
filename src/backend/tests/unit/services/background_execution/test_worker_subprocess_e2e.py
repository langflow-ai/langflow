"""REAL-PROCESS hard proof: a separate ``langflow worker`` OS process runs a job.

Closes the Phase 4 caveat that the worker ran in-process. Here an ACTUAL
``subprocess.Popen(["uv", "run", "langflow", "worker"])`` claims a job off real
redis, builds a REAL ChatInput->ChatOutput graph from the shared Postgres, runs
it to COMPLETED, and the API-side facade reattaches and replays the durable
milestones the worker persisted. Then a second job is killed with ``kill -9``
mid-flight and the lease watchdog reconciles the stranded job.

Requires both LANGFLOW_TEST_DATABASE_URI (real Postgres) and
LANGFLOW_TEST_REDIS_URL (real Redis). Skips otherwise. Every wait is bounded.
"""

from __future__ import annotations

import asyncio
import os
import signal

import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_settings_service

from ._subprocess_harness import setup_worker_harness


class _StubUser:
    def __init__(self, user_id):
        self.id = user_id


def _require_real_instances():
    pg = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    redis = os.environ.get("LANGFLOW_TEST_REDIS_URL")
    if not pg:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI not set; real-process proof requires real Postgres")
    if not redis:
        pytest.skip("LANGFLOW_TEST_REDIS_URL not set; real-process proof requires real Redis")
    return pg, redis


@pytest.mark.hard_proof
async def test_real_worker_subprocess_runs_job_and_facade_reattaches():
    """A REAL worker process claims + builds + completes a real graph; facade reattaches."""
    pg, redis = _require_real_instances()
    harness = await setup_worker_harness(pg, redis, redis_db=14)
    try:
        from redis.asyncio import StrictRedis

        user_id, flow_id = await harness.seed_real_flow(input_value="hello-subproc")
        job_id = await harness.submit_job(flow_id=flow_id, user_id=user_id, input_value="hello-subproc")

        # Sanity: the API process did NOT run it — it sits QUEUED on the claim queue.
        queued = await harness.job_service.get_job_by_job_id(job_id)
        assert queued.status == JobStatus.QUEUED

        # Launch the REAL separate worker OS process.
        proc = harness.spawn_worker(idle_block_ms=200)
        assert proc.poll() is None, "worker subprocess failed to start"

        # The SEPARATE process claims + builds + completes the real graph.
        job = await harness.wait_for_status(job_id, {JobStatus.COMPLETED}, timeout=90.0)
        assert job.status == JobStatus.COMPLETED
        assert job.result is not None

        # Durable milestones the worker persisted are replayable by ANY API replica.
        events = await harness.job_service.read_events(job_id, after_seq=0)
        types = [e.event_type for e in events]
        assert types, "worker persisted no durable milestones"
        assert "end" in types, f"no terminal milestone; types={types}"
        # Token deltas stay ephemeral (not durable).
        assert "token" not in types, "token deltas must not be persisted"

        # API-side facade (scaled backend on a SEPARATE redis connection) reattaches
        # and replays the durable milestones the worker wrote — cross-process.
        client_b = StrictRedis.from_url(harness.redis_url)
        backend_b = RedisBackgroundQueue(
            client=client_b, job_service=harness.job_service, stream_ttl=60, startup_grace_s=5.0
        )
        get_settings_service().settings.job_queue_type = "redis"
        facade_b = BackgroundExecutionService(settings_service=get_settings_service(), backend=backend_b)
        try:

            async def _collect():
                return [c async for c in facade_b.events(job_id, last_event_id=None, user=_StubUser(user_id))]

            replayed = await asyncio.wait_for(_collect(), timeout=15.0)
        finally:
            await client_b.aclose()
        body = b"".join(replayed)
        assert b"add_message" in body or b"end_vertex" in body, "facade replayed no durable worker frames"

        print(  # noqa: T201
            f"PROOF[subprocess/e2e]: REAL `langflow worker` (pid={proc.pid}) claimed + built + "
            f"completed a real graph; facade reattach replayed {len(replayed)} durable frames; "
            f"durable types={types}"
        )
    finally:
        await harness.teardown()


@pytest.mark.hard_proof
async def test_real_worker_kill9_midjob_reconciled_by_watchdog():
    """Kill -9 a REAL worker mid-job; the lease watchdog fails the stranded job worker_lost."""
    pg, redis = _require_real_instances()
    harness = await setup_worker_harness(pg, redis, redis_db=13)
    try:
        # A real multi-vertex flow so the worker is reliably mid-build when we
        # SIGKILL it. Default (not retry-safe) => at-most-once: worker_lost.
        user_id, flow_id = await harness.seed_slow_flow()
        job_id = await harness.submit_job(flow_id=flow_id, user_id=user_id, input_value="kill9")

        proc = harness.spawn_worker(idle_block_ms=200)

        # Wait until the worker has CLAIMED + started the job (IN_PROGRESS), then
        # kill -9 it so it cannot finalize the row (true worker death mid-flight).
        await harness.wait_for_status(job_id, {JobStatus.IN_PROGRESS, JobStatus.COMPLETED}, timeout=90.0)
        job = await harness.job_service.get_job_by_job_id(job_id)
        if job.status == JobStatus.COMPLETED:
            pytest.skip("graph completed before we could kill the worker mid-flight (too fast on this host)")

        # kill -9 the WHOLE worker group: ``uv run`` spawns a child python that
        # survives a SIGKILL aimed only at ``uv``, so we signal the process group.
        harness.signal_group(proc, signal.SIGKILL)
        proc.wait(timeout=10)
        assert proc.returncode is not None, "worker did not die on SIGKILL"
        # The durable row is now a stranded IN_PROGRESS orphan with a live lease on
        # the redis processing list (the dead worker never released it).

        # A fresh backend instance acts as a second replica / restarted worker and
        # runs the lease watchdog reconcile. Default (not retry-safe) => worker_lost.
        from redis.asyncio import StrictRedis

        client = StrictRedis.from_url(harness.redis_url)
        backend = RedisBackgroundQueue(client=client, job_service=harness.job_service, startup_grace_s=5.0)
        try:
            stranded = await backend.claim_queue.processing_ids()
            assert str(job_id) in stranded, f"job not on the processing list after kill: {stranded}"
            # Lease still fresh (the worker heartbeated just before dying): a
            # reconcile with a generous TTL must NOT touch it — this is the
            # at-most-once guard that stops a live job being failed.
            await backend.requeue_lost(lease_ttl_s=3600.0)
            still = await harness.job_service.get_job_by_job_id(job_id)
            assert still.status == JobStatus.IN_PROGRESS, f"fresh-lease job wrongly reconciled: {still.status}"
            # Once the lease is treated as expired (the dead worker stopped
            # heartbeating), the watchdog reconciles it worker_lost.
            await backend.requeue_lost(lease_ttl_s=0.0)
        finally:
            await client.aclose()

        job = await harness.job_service.get_job_by_job_id(job_id)
        assert job.status == JobStatus.FAILED, f"stranded job not failed: {job.status}"
        assert (job.error or {}).get("type") == "worker_lost", f"error={job.error}"
        print(  # noqa: T201
            f"PROOF[subprocess/kill9]: kill -9 the REAL worker (pid={proc.pid}) mid-job -> "
            f"lease watchdog reconciled stranded job to FAILED(worker_lost)"
        )
    finally:
        await harness.teardown()
