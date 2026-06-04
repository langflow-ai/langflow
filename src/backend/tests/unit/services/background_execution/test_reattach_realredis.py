"""Real-redis: a replica that never ran the job replays DB then tails the live Stream."""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.job_queue.service import _STREAM_PREFIX


class _FakeJobService:
    def __init__(self):
        self._events: dict[str, list] = {}

    async def append_event(self, job_id, event_type, payload):
        seq = len(self._events.setdefault(str(job_id), [])) + 1
        self._events[str(job_id)].append((seq, event_type, payload))
        return seq

    async def read_events(self, job_id, after_seq=0):
        return [
            type("E", (), {"seq": s, "event_type": et, "payload": p})()
            for (s, et, p) in self._events.get(str(job_id), [])
            if s > after_seq
        ]


@pytest.mark.asyncio
async def test_replica_b_reattaches_and_sees_live_frame(real_redis, real_redis_url):
    from redis.asyncio import StrictRedis

    job_id = "reattach-job"
    jobs = _FakeJobService()
    # Durable milestone persisted by the worker before replica B attaches.
    await jobs.append_event(job_id, "run_started", {"flow_id": "f"})

    # Replica B uses a separate connection and never started the job.
    client_b = StrictRedis.from_url(real_redis_url)
    backend_b = RedisBackgroundQueue(client=client_b, job_service=jobs, stream_ttl=60, startup_grace_s=10.0)

    stream_key = f"{_STREAM_PREFIX}{job_id}"
    collected = []

    async def consume():
        async for frame in backend_b.events(job_id, last_event_id=0):
            collected.append(frame)
            if len(collected) == 2:  # durable replay + one live frame
                return

    consumer = asyncio.create_task(consume())
    # Let replica B replay the durable event and start tailing the Stream.
    await asyncio.sleep(0.2)

    # Worker (on the primary connection) publishes a live ephemeral frame, then
    # the end-of-stream sentinel.
    await real_redis.xadd(stream_key, {"event_id": "token", "data": b"hello", "ts": "0"})
    await real_redis.expire(stream_key, 60)

    try:
        await asyncio.wait_for(consumer, timeout=5.0)
    finally:
        if not consumer.done():
            consumer.cancel()
        await client_b.aclose()
        await real_redis.delete(stream_key)

    # First frame is the durable replay; second is the live Stream frame.
    assert collected[0].seq == 1
    assert collected[0].event_type == "run_started"
    assert collected[1].seq is None
    assert collected[1].payload == b"hello"
