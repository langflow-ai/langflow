"""REAL-PROCESS real service: a durable STOP from the API reaches a separate worker.

Closes the Phase 4 caveat that stop was delivered in-process. Here an ACTUAL
``langflow worker`` OS subprocess runs a slowish multi-vertex real flow; the
API-side facade calls ``stop_job`` (the durable STOP signal, the single source of
truth); the SEPARATE worker process honors the stop at its next vertex boundary
and the job ends CANCELLED with the STOP signal consumed.

Requires real Postgres + real Redis. Skips otherwise. Every wait is bounded.
"""

from __future__ import annotations

import os

import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import JobStatus, SignalType
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


@pytest.mark.real_services
async def test_real_worker_subprocess_honors_pubsub_stop():
    """API-side stop_job CANCELs a job running in a SEPARATE worker OS process."""
    pg, redis = _require_real_instances()
    harness = await setup_worker_harness(pg, redis, redis_db=12)
    try:
        # A real multi-vertex no-LLM flow whose build crosses several vertex
        # boundaries — each a point where the runner polls the durable STOP.
        user_id, flow_id = await harness.seed_slow_flow()
        job_id = await harness.submit_job(flow_id=flow_id, user_id=user_id, input_value="stop-me")

        # API-side scaled facade (writes the durable STOP signal, the source of truth).
        from redis.asyncio import StrictRedis

        api_client = StrictRedis.from_url(harness.redis_url)
        backend = RedisBackgroundQueue(client=api_client, job_service=harness.job_service, startup_grace_s=5.0)
        get_settings_service().settings.job_queue_type = "redis"
        facade = BackgroundExecutionService(settings_service=get_settings_service(), backend=backend)

        proc = harness.spawn_worker(idle_block_ms=200)

        try:
            # Wait until the SEPARATE worker has started the job (IN_PROGRESS).
            await harness.wait_for_status(
                job_id, {JobStatus.IN_PROGRESS, JobStatus.COMPLETED, JobStatus.CANCELLED}, timeout=90.0
            )
            job = await harness.job_service.get_job_by_job_id(job_id)
            if job.status != JobStatus.IN_PROGRESS:
                pytest.skip(f"job reached {job.status} before stop could land (too fast on this host)")

            # API-side stop: the durable STOP signal the owning worker process
            # polls at its next vertex boundary.
            await facade.stop_job(job_id, _StubUser(user_id))

            # The SEPARATE worker honors the stop at a vertex boundary -> CANCELLED.
            final = await harness.wait_for_status(job_id, {JobStatus.CANCELLED}, timeout=60.0)
            assert final.status == JobStatus.CANCELLED, f"worker did not honor stop: {final.status}"

            # The STOP signal was consumed by the worker's terminal reconcile.
            leftover = [
                s for s in await harness.job_service.unconsumed_signals(job_id) if s.signal_type == SignalType.STOP
            ]
            assert leftover == [], "STOP signal was not consumed by the worker"
            print(  # noqa: T201
                f"PROOF[subprocess/stop]: API stop_job -> SEPARATE worker (pid={proc.pid}) honored "
                f"durable STOP -> job CANCELLED, signal consumed"
            )
        finally:
            await api_client.aclose()
    finally:
        await harness.teardown()
