"""Real-redis: stop() PUBLISH reaches an owning RedisJobQueueService dispatcher."""

from __future__ import annotations

import asyncio
import contextlib

import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.job_queue.service import RedisJobQueueService


class _NoopJobService:
    async def write_signal(self, _job_id, _signal_type):  # durable write is exercised elsewhere
        return None


@pytest.mark.asyncio
async def test_stop_publish_cancels_owned_build(real_redis_url):
    if real_redis_url is None:
        pytest.skip("LANGFLOW_TEST_REDIS_URL not set")

    job_id = "fastpath-job"

    # Owning worker: real RedisJobQueueService with its cancel dispatcher running.
    owner = RedisJobQueueService(url=real_redis_url, cancel_channel_enabled=True)
    owner.start()
    # Give the PSUBSCRIBE a beat to land before publishing.
    await asyncio.sleep(0.3)

    cancelled = asyncio.Event()

    async def fake_build():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    owner.create_queue(job_id)
    owner.start_job(job_id, fake_build())

    from redis.asyncio import StrictRedis

    publisher = StrictRedis.from_url(real_redis_url)
    backend = RedisBackgroundQueue(client=publisher, job_service=_NoopJobService())
    try:
        await backend.stop(job_id)
        # The dispatcher should receive the pmessage and cancel the local task.
        await asyncio.wait_for(cancelled.wait(), timeout=5.0)
        assert cancelled.is_set()
    finally:
        await publisher.aclose()
        # owner.stop() routes through cleanup_job, which re-raises the
        # user-initiated CancelledError (a BaseException, so suppress(Exception)
        # would miss it). Suppress both so teardown stays clean.
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await owner.stop()
