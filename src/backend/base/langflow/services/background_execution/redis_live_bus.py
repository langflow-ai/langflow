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


class RedisStreamLiveBus:
    """Producer-side live bus that XADDs JobRunner frames to a redis Stream."""

    def __init__(self, client: Any, *, ttl: int = 3600) -> None:
        self._client = client
        self._ttl = ttl

    @staticmethod
    def _stream_key(job_id: str) -> str:
        return f"{_STREAM_PREFIX}{job_id}"

    async def publish(self, job_id: str, frame: LiveFrame) -> None:
        """XADD one framed event onto the job's redis Stream.

        ``frame.seq`` rides in the ``event_id`` field so a consumer can recover
        the durable cursor for live milestone frames; ``frame.data`` is the
        already-SSE-framed bytes, byte-compatible with the durable replay path.
        """
        key = self._stream_key(job_id)
        fields = {"event_id": str(frame.seq), "data": frame.data, "ts": str(time.time())}
        await self._client.xadd(key, fields, maxlen=10_000, approximate=True)
        await self._client.expire(key, self._ttl)

    async def close(self, job_id: str) -> None:
        """Write the end-of-stream sentinel so tailing consumers terminate cleanly."""
        key = self._stream_key(job_id)
        fields = {"event_id": "__sentinel__", "data": _STREAM_SENTINEL_DATA, "ts": str(time.time())}
        await self._client.xadd(key, fields, maxlen=10_000, approximate=True)
        await self._client.expire(key, self._ttl)
