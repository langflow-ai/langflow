"""Real-redis: BRPOPLPUSH blocks and wakes on a cross-client enqueue, exactly once."""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.background_execution.redis_queue import RedisJobClaimQueue


@pytest.mark.asyncio
async def test_blocking_claim_wakes_on_enqueue(real_redis):
    prefix = real_redis._bgtest_prefix
    q = RedisJobClaimQueue(
        real_redis,
        pending_key=f"{prefix}pending",
        processing_key=f"{prefix}processing",
    )

    claim_task = asyncio.create_task(q.claim(block_ms=3000))
    # Let the BRPOPLPUSH register its block before we enqueue.
    await asyncio.sleep(0.1)
    assert not claim_task.done()

    await q.enqueue("late-job")
    claimed = await asyncio.wait_for(claim_task, timeout=3.0)
    assert claimed == "late-job"


@pytest.mark.asyncio
async def test_two_workers_claim_disjoint_jobs(real_redis, real_redis_url):
    prefix = real_redis._bgtest_prefix
    from redis.asyncio import StrictRedis

    second = StrictRedis.from_url(real_redis_url)
    try:
        q1 = RedisJobClaimQueue(real_redis, pending_key=f"{prefix}pending", processing_key=f"{prefix}processing")
        q2 = RedisJobClaimQueue(second, pending_key=f"{prefix}pending", processing_key=f"{prefix}processing")
        await q1.enqueue("only-one")

        results = await asyncio.gather(q1.claim(block_ms=1000), q2.claim(block_ms=1000))
        # Exactly one worker gets the job; the other times out to None.
        assert sorted(r for r in results if r is not None) == ["only-one"]
        assert results.count(None) == 1
    finally:
        await second.aclose()
