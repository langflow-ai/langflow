"""Real-redis: RedisStreamLiveBus refreshes the Stream TTL in batches, not per-XADD.

The v1 Streams bridge explicitly avoids an ``EXPIRE`` on every ``XADD`` because it
doubles redis round-trips per frame and caps single-job streaming throughput
(``_TTL_REFRESH_EVENTS``/``_TTL_REFRESH_SECS``). The new live bus must carry the
same mitigation: a high-token-rate flow that publishes hundreds of frames should
issue an EXPIRE on the first frame and then only periodically, not once per
frame. We count REAL ``expire`` calls (a thin counting wrapper over the real
client that still executes the command) while publishing a burst, and assert the
expire count is a small fraction of the frame count and that the key still has a
TTL set (semantics preserved).
"""

from __future__ import annotations

import pytest
from langflow.services.background_execution.live_bus import LiveFrame
from langflow.services.background_execution.redis_live_bus import RedisStreamLiveBus
from langflow.services.job_queue.service import _STREAM_PREFIX


@pytest.mark.asyncio
async def test_ttl_refresh_is_batched_not_per_frame(real_redis):
    job_id = "ttl-job"
    stream_key = f"{_STREAM_PREFIX}{job_id}"

    # Thin counting wrapper: forwards EVERY call to the real client (no behavior
    # change) and tallies expire() invocations. Not a mock — the real EXPIRE runs.
    class _CountingClient:
        def __init__(self, inner):
            self._inner = inner
            self.expire_calls = 0

        async def expire(self, *args, **kwargs):
            self.expire_calls += 1
            return await self._inner.expire(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    counting = _CountingClient(real_redis)
    bus = RedisStreamLiveBus(counting, ttl=60)

    n_frames = 250
    try:
        for i in range(n_frames):
            await bus.publish(job_id, LiveFrame(seq=i, data=f"f{i}".encode()))
        await bus.close(job_id)

        # Per-frame EXPIRE would be ~251; batched refresh must be a small fraction.
        assert counting.expire_calls <= 10, (
            f"EXPIRE issued {counting.expire_calls} times for {n_frames} frames; TTL refresh is not batched"
        )
        # Semantics preserved: the key still carries a positive TTL.
        ttl = await real_redis.ttl(stream_key)
        assert ttl > 0, f"stream key TTL not set after batched refresh: {ttl}"
    finally:
        await real_redis.delete(stream_key)
