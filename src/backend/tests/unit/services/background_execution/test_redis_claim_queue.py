"""RedisJobClaimQueue enqueue/claim/complete semantics (fakeredis, timing-independent)."""

from __future__ import annotations

import fakeredis.aioredis as fakeredis_aio
import pytest
from langflow.services.background_execution.redis_queue import RedisJobClaimQueue


@pytest.fixture
def client():
    return fakeredis_aio.FakeRedis()


@pytest.mark.asyncio
async def test_enqueue_then_claim_returns_job_id(client):
    q = RedisJobClaimQueue(client)
    await q.enqueue("job-1")
    claimed = await q.claim(block_ms=50)
    assert claimed == "job-1"


@pytest.mark.asyncio
async def test_claim_empty_returns_none(client):
    q = RedisJobClaimQueue(client)
    claimed = await q.claim(block_ms=50)
    assert claimed is None


@pytest.mark.asyncio
async def test_claimed_job_is_on_processing_list(client):
    q = RedisJobClaimQueue(client)
    await q.enqueue("job-2")
    await q.claim(block_ms=50)
    # Until complete(), the id sits on the processing list (crash-recoverable).
    processing = await client.lrange(q.processing_key, 0, -1)
    assert b"job-2" in processing


@pytest.mark.asyncio
async def test_complete_removes_from_processing_list(client):
    q = RedisJobClaimQueue(client)
    await q.enqueue("job-3")
    await q.claim(block_ms=50)
    await q.complete("job-3")
    processing = await client.lrange(q.processing_key, 0, -1)
    assert b"job-3" not in processing


@pytest.mark.asyncio
async def test_fifo_order(client):
    q = RedisJobClaimQueue(client)
    await q.enqueue("a")
    await q.enqueue("b")
    assert await q.claim(block_ms=50) == "a"
    assert await q.claim(block_ms=50) == "b"


@pytest.mark.asyncio
async def test_processing_ids_lists_claimed(client):
    q = RedisJobClaimQueue(client)
    await q.enqueue("p1")
    await q.enqueue("p2")
    await q.claim(block_ms=50)
    await q.claim(block_ms=50)
    ids = await q.processing_ids()
    assert sorted(ids) == ["p1", "p2"]
