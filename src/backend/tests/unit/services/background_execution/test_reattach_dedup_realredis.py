"""Real-redis: cross-replica reattach delivers each durable milestone EXACTLY once.

The scaled worker publishes EVERY durable milestone to BOTH the DB (append_event)
and the redis Stream (RedisStreamLiveBus.XADD). A reattacher's ``events()``
replays the durable rows from the DB, then tails the Stream. If the Stream tail
starts at ``0-0`` with no seq filtering, every milestone already replayed from the
DB is delivered a SECOND time off the Stream. This test puts the same milestones
in BOTH places and asserts a fresh reattach yields each milestone exactly once,
mirroring the in-memory bus dedup-at-the-seam contract.
"""

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


def _frame_bytes(seq: int, event_type: str) -> bytes:
    import json

    from fastapi.sse import format_sse_event

    return format_sse_event(data_str=json.dumps({"event": event_type, "data": {}}), id=str(seq))


@pytest.mark.asyncio
async def test_reattach_no_double_delivery_realredis(real_redis, real_redis_url):
    from redis.asyncio import StrictRedis

    job_id = "dedup-job"
    jobs = _FakeJobService()
    live_bus = RedisStreamLiveBus(real_redis, ttl=60)

    # The worker writes each milestone to BOTH the DB and the Stream, with the
    # durable seq stamped on the Stream frame (event_id == seq) — exactly what
    # the runner does in scaled mode after the Last-Event-ID namespace fix.
    for event_type in ("run_started", "vertices_sorted", "end_vertex"):
        seq = await jobs.append_event(job_id, event_type, {})
        await live_bus.publish(job_id, LiveFrame(seq=seq, data=_frame_bytes(seq, event_type)))
    # Sentinel so the tail terminates cleanly.
    await live_bus.close(job_id)

    # A fresh replica reattaches from the start (last_event_id=0).
    client_b = StrictRedis.from_url(real_redis_url)
    backend_b = RedisBackgroundQueue(client=client_b, job_service=jobs, stream_ttl=60, startup_grace_s=10.0)

    seqs: list[int] = []
    stream_key = f"{_STREAM_PREFIX}{job_id}"

    async def consume() -> None:
        async for item in backend_b.events(job_id, last_event_id=0):
            seq = item.seq if item.seq is not None else _parse_event_id(item)
            if seq is not None:
                seqs.append(seq)

    try:
        await asyncio.wait_for(consume(), timeout=8.0)
    finally:
        await client_b.aclose()
        await real_redis.delete(stream_key)

    # Each durable seq must appear EXACTLY once across DB-replay + Stream-tail.
    assert seqs == [1, 2, 3], f"double-delivery on reattach: {seqs}"


@pytest.mark.asyncio
async def test_reattach_mid_run_last_event_id_realredis(real_redis, real_redis_url):
    """A mid-run Last-Event-ID resumes exactly after that durable seq on the Stream.

    The worker has written milestones 1,2,3 to BOTH the DB and the Stream. A
    client that disconnected after seeing seq 2 reconnects with Last-Event-ID=2.
    The reattach must yield ONLY seq 3 (the next milestone) — no seq <= 2 from the
    DB replay (filtered by after_seq) and none re-delivered off the Stream tail.
    """
    from redis.asyncio import StrictRedis

    job_id = "midrun-job"
    jobs = _FakeJobService()
    live_bus = RedisStreamLiveBus(real_redis, ttl=60)
    for event_type in ("run_started", "vertices_sorted", "end_vertex"):
        seq = await jobs.append_event(job_id, event_type, {})
        await live_bus.publish(job_id, LiveFrame(seq=seq, data=_frame_bytes(seq, event_type)))
    await live_bus.close(job_id)

    client_b = StrictRedis.from_url(real_redis_url)
    backend_b = RedisBackgroundQueue(client=client_b, job_service=jobs, stream_ttl=60, startup_grace_s=10.0)

    seqs: list[int] = []
    stream_key = f"{_STREAM_PREFIX}{job_id}"

    async def consume() -> None:
        async for item in backend_b.events(job_id, last_event_id=2):
            seq = item.seq if item.seq is not None else _parse_event_id(item)
            if seq is not None:
                seqs.append(seq)

    try:
        await asyncio.wait_for(consume(), timeout=8.0)
    finally:
        await client_b.aclose()
        await real_redis.delete(stream_key)

    assert seqs == [3], f"reattach from seq 2 must yield only seq 3, got: {seqs}"


def _parse_event_id(item) -> int | None:
    """A live _StreamFrame carries the worker-stamped durable seq in event_type."""
    raw = getattr(item, "event_type", None)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
