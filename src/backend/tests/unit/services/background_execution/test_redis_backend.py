"""RedisBackgroundQueue: enqueue routes to claim queue; events replay DB then tail Stream."""

from __future__ import annotations

import fakeredis.aioredis as fakeredis_aio
import pytest
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue


class _FakeJobService:
    """Minimal real-behavior stand-in for the durable event store.

    Not a mock of our code: it stores appended events in a list and read_events
    filters by seq, exactly like the DB-backed JobService.read_events contract.
    """

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
async def test_enqueue_pushes_to_claim_queue():
    client = fakeredis_aio.FakeRedis()
    jobs = _FakeJobService()
    backend = RedisBackgroundQueue(client=client, job_service=jobs)
    await backend.enqueue("job-1")
    pending = await client.lrange(backend.claim_queue.pending_key, 0, -1)
    assert b"job-1" in pending


@pytest.mark.asyncio
async def test_events_replays_durable_then_tails_stream():
    client = fakeredis_aio.FakeRedis()
    jobs = _FakeJobService()
    # Two durable milestones already persisted (e.g. run_started, vertex_end).
    await jobs.append_event("job-2", "run_started", {"flow_id": "f"})
    await jobs.append_event("job-2", "vertex_end", {"v": 1})

    # Short startup grace so the empty stream ends the tail quickly.
    backend = RedisBackgroundQueue(client=client, job_service=jobs, startup_grace_s=0.2)
    collected = []
    async for frame in backend.events("job-2", last_event_id=0):
        collected.append(frame)
        if len(collected) == 2:
            break
    # Replayed in seq order before any live tail.
    assert collected[0].seq == 1
    assert collected[1].seq == 2


@pytest.mark.asyncio
async def test_events_replay_respects_last_event_id():
    client = fakeredis_aio.FakeRedis()
    jobs = _FakeJobService()
    await jobs.append_event("job-3", "a", {})
    await jobs.append_event("job-3", "b", {})
    await jobs.append_event("job-3", "c", {})

    backend = RedisBackgroundQueue(client=client, job_service=jobs, startup_grace_s=0.2)
    collected = []
    async for frame in backend.events("job-3", last_event_id=2):
        collected.append(frame)
        if len(collected) == 1:
            break
    # Only seq>2 replayed (the Last-Event-ID cursor).
    assert collected[0].seq == 3
