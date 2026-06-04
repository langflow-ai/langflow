"""Redis-backed job-claim queue for the scaled background backend.

This is the *work-claim* queue, distinct from the Redis Streams *event* bus
(``RedisJobQueueService`` / ``RedisQueueWrapper``). A ``langflow worker`` process
claims job ids off the pending list and runs the ``JobRunner``; the API process
only enqueues. We keep this deliberately small and reuse the existing Streams +
cancel machinery for everything else.

Claim protocol
--------------
* ``enqueue(job_id)``  -> ``LPUSH pending_key job_id``
* ``claim(block_ms)``  -> ``BRPOPLPUSH pending_key processing_key`` (atomic move)
* ``complete(job_id)`` -> ``LREM processing_key 0 job_id``

The atomic move to a processing list means a worker crash *after* claim but
*before* complete leaves the id recoverable: the watchdog (see
``RedisBackgroundQueue.requeue_lost``) reconciles stale processing-list ids.
FIFO is preserved because ``LPUSH`` pushes to the head and ``BRPOPLPUSH`` pops
from the tail.
"""

from __future__ import annotations

from typing import Any

_PENDING_KEY = "langflow:bg:pending"
_PROCESSING_KEY = "langflow:bg:processing"


class RedisJobClaimQueue:
    """Thin LPUSH/BRPOPLPUSH job-claim queue over a redis client."""

    def __init__(
        self,
        client: Any,
        *,
        pending_key: str = _PENDING_KEY,
        processing_key: str = _PROCESSING_KEY,
    ) -> None:
        self._client = client
        self.pending_key = pending_key
        self.processing_key = processing_key

    async def enqueue(self, job_id: str) -> None:
        await self._client.lpush(self.pending_key, job_id)

    async def claim(self, *, block_ms: int = 1000) -> str | None:
        """Atomically move one id from pending to processing, blocking up to block_ms.

        Returns the claimed job id, or None when the pending list stays empty
        for the whole timeout window. ``BRPOPLPUSH`` timeout is in seconds
        (float accepted on redis>=6); convert from the millisecond argument.
        """
        timeout_s = max(block_ms / 1000.0, 0.0)
        raw = await self._client.brpoplpush(self.pending_key, self.processing_key, timeout=timeout_s)
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw

    async def complete(self, job_id: str) -> int:
        """Remove ``job_id`` from the processing list. Returns the count removed.

        ``LREM`` is atomic and returns how many entries it deleted, so a
        reconciler can use a non-zero return as a single-flight token: only the
        caller whose LREM actually removed the id owns the follow-up requeue,
        and concurrent reconcilers that removed nothing (0) must not re-enqueue.
        """
        return int(await self._client.lrem(self.processing_key, 0, job_id))

    async def processing_ids(self) -> list[str]:
        """Return all ids currently on the processing list (for the watchdog)."""
        raw = await self._client.lrange(self.processing_key, 0, -1)
        return [r.decode() if isinstance(r, bytes) else r for r in raw]
