"""Redis Streams live bus for the scaled background worker.

The worker's ``JobRunner`` drives the SAME interface the in-memory bus exposes
(``publish(job_id, LiveFrame)`` + ``close(job_id)``), but in the scaled backend
the frames must be visible to ANY API replica, not just the local process. This
bus XADDs each frame onto the shared redis Stream keyed ``langflow:queue:{job_id}``
— the exact key + field shape ``RedisQueueWrapper`` already consumes — so
``RedisBackgroundQueue.events()`` can tail it cross-replica. We reuse the wrapper
verbatim; this is only the producer half (no second bridge).

Stream protocol (matches RedisQueueWrapper):
* live frame  -> ``XADD key * event_id <seq> data <bytes> ts <ts>``
* close       -> ``XADD key * event_id __sentinel__ data __sentinel__ ts <ts>``
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from langflow.services.job_queue.service import _STREAM_PREFIX, _STREAM_SENTINEL_DATA

if TYPE_CHECKING:
    from langflow.services.background_execution.live_bus import LiveFrame

# Refresh the stream TTL on the first frame, then every _TTL_REFRESH_EVENTS frames
# *or* every _TTL_REFRESH_SECS seconds, whichever comes first (and always on
# close). Calling expire() on every XADD doubles redis round-trips per frame and
# caps single-job throughput; periodic refresh preserves the TTL semantics at
# ~1/100 the cost. Mirrors the v1 Streams bridge (job_queue/service.py).
_TTL_REFRESH_EVENTS = 100
_TTL_REFRESH_SECS = 30.0


class RedisStreamLiveBus:
    """Producer-side live bus that XADDs JobRunner frames to a redis Stream."""

    def __init__(self, client: Any, *, ttl: int = 3600) -> None:
        self._client = client
        self._ttl = ttl
        # Per-job TTL-refresh bookkeeping so a high-token-rate flow does not issue
        # an EXPIRE on every frame. job_id -> (event_count, last_refresh_monotonic).
        self._ttl_state: dict[str, tuple[int, float]] = {}

    @staticmethod
    def _stream_key(job_id: str) -> str:
        return f"{_STREAM_PREFIX}{job_id}"

    def _needs_ttl_refresh(self, job_id: str) -> bool:
        """Decide whether this frame should refresh the TTL, advancing the counter."""
        count, last = self._ttl_state.get(job_id, (0, 0.0))
        now = time.monotonic()
        needs = count == 0 or count % _TTL_REFRESH_EVENTS == 0 or (now - last) >= _TTL_REFRESH_SECS
        self._ttl_state[job_id] = (count + 1, now if needs else last)
        return needs

    async def publish(self, job_id: str, frame: LiveFrame) -> None:
        """XADD one framed event onto the job's redis Stream.

        ``frame.seq`` rides in the ``event_id`` field so a consumer can recover
        the durable cursor for live milestone frames; ``frame.data`` is the
        already-SSE-framed bytes, byte-compatible with the durable replay path.
        The TTL is refreshed in batches (see ``_needs_ttl_refresh``), not on every
        XADD, so a high-token-rate flow does not double its redis round-trips.
        """
        key = self._stream_key(job_id)
        fields = {"event_id": str(frame.seq), "data": frame.data, "ts": str(time.time())}
        await self._client.xadd(key, fields, maxlen=10_000, approximate=True)
        if self._needs_ttl_refresh(job_id):
            await self._client.expire(key, self._ttl)

    async def close(self, job_id: str) -> None:
        """Write the end-of-stream sentinel so tailing consumers terminate cleanly."""
        key = self._stream_key(job_id)
        fields = {"event_id": "__sentinel__", "data": _STREAM_SENTINEL_DATA, "ts": str(time.time())}
        await self._client.xadd(key, fields, maxlen=10_000, approximate=True)
        # Always refresh on close so the final TTL window covers the full stream.
        await self._client.expire(key, self._ttl)
        self._ttl_state.pop(job_id, None)
