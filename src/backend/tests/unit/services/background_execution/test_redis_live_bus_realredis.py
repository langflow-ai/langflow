"""Real-redis: RedisStreamLiveBus XADDs frames that RedisQueueWrapper consumes."""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.background_execution.live_bus import LiveFrame
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.background_execution.redis_live_bus import RedisStreamLiveBus
from langflow.services.job_queue.service import _STREAM_PREFIX


class _FakeJobService:
    def __init__(self):
        self._events: dict[str, list] = {}

    async def read_events(self, job_id, after_seq=0):
        return [
            type("E", (), {"seq": s, "event_type": et, "payload": p})()
            for (s, et, p) in self._events.get(str(job_id), [])
            if s > after_seq
        ]


@pytest.mark.asyncio
async def test_published_frames_reach_a_reattaching_consumer(real_redis, real_redis_url):
    from redis.asyncio import StrictRedis

    job_id = "livebus-job"
    stream_key = f"{_STREAM_PREFIX}{job_id}"

    # Worker side: publish two live frames then close (sentinel).
    bus = RedisStreamLiveBus(real_redis, ttl=60)

    # Consumer side: a separate connection, replays empty DB then tails the Stream.
    client_b = StrictRedis.from_url(real_redis_url)
    backend_b = RedisBackgroundQueue(
        client=client_b, job_service=_FakeJobService(), stream_ttl=60, startup_grace_s=10.0
    )

    collected = []

    async def consume():
        async for frame in backend_b.events(job_id, last_event_id=0):
            collected.append(frame)  # noqa: PERF401 - explicit loop reads clearer than a comprehension here

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.2)  # let the tail register

    await bus.publish(job_id, LiveFrame(seq=1, data=b"frame-one"))
    await bus.publish(job_id, LiveFrame(seq=2, data=b"frame-two"))
    await bus.close(job_id)

    try:
        await asyncio.wait_for(consumer, timeout=5.0)
    finally:
        if not consumer.done():
            consumer.cancel()
        await client_b.aclose()
        await real_redis.delete(stream_key)

    # Both live frames arrived in order; the sentinel ended the stream cleanly.
    payloads = [f.payload for f in collected]
    assert payloads == [b"frame-one", b"frame-two"]
