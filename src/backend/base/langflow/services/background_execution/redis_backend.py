"""Scaled background backend: redis claim queue + Streams live bus + DB replay.

The facade (``BackgroundExecutionService``) delegates to this when
``settings.background_backend_is_scaled`` is True. It composes:

* ``RedisJobClaimQueue``   — hands job ids to a separate ``langflow worker`` process.
* ``JobService`` durable   — ``read_events()`` replays milestone events from the DB
  so any API replica can reattach from a Last-Event-ID cursor.
* ``RedisQueueWrapper``    — the existing Streams tail for live ephemeral frames,
  reused verbatim from the job_queue service (no second bridge built here).

``events()`` is the cross-replica reattach contract: replay durable ``job_events``
(seq > last_event_id) from the DB, then XREAD-tail the redis Stream for live
frames. A replica that never started the job can still serve the full event
history because milestones are durable and live frames are on the shared Stream.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.services.background_execution.redis_queue import RedisJobClaimQueue
from langflow.services.job_queue.service import RedisQueueWrapper

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langflow.services.jobs.service import JobService


class _StreamFrame:
    """A live (ephemeral) frame pulled off the redis Stream tail.

    ``seq`` is None because live frames are not durable — only the DB-backed
    milestones carry a Last-Event-ID seq.
    """

    __slots__ = ("event_type", "payload", "seq")

    def __init__(self, *, seq: int | None, event_type: Any, payload: Any) -> None:
        self.seq = seq
        self.event_type = event_type
        self.payload = payload


class RedisBackgroundQueue:
    """Redis-backed backend behind the BackgroundExecutionService facade."""

    def __init__(
        self,
        *,
        client: Any,
        job_service: JobService,
        stream_ttl: int = 3600,
        startup_grace_s: float = 30.0,
    ) -> None:
        self._client = client
        self._job_service = job_service
        self._stream_ttl = stream_ttl
        self._startup_grace_s = startup_grace_s
        self.claim_queue = RedisJobClaimQueue(client)

    async def enqueue(self, job_id: str) -> None:
        """Hand a queued job id to a worker process via the claim queue."""
        await self.claim_queue.enqueue(job_id)

    async def events(self, job_id: str, last_event_id: int = 0) -> AsyncIterator[Any]:
        """Replay durable events after last_event_id, then tail the live Stream.

        Any API replica can call this: durable milestones come from the DB so a
        replica that didn't start the job still serves full history; live
        ephemeral frames come off the shared redis Stream via RedisQueueWrapper.
        """
        # 1. Durable replay from the DB (the Last-Event-ID cursor is seq).
        for event in await self._job_service.read_events(job_id, after_seq=last_event_id):
            yield event

        # 2. Live tail of the redis Stream for ephemeral frames published by the
        #    worker. The wrapper self-terminates on the end-of-stream sentinel or
        #    when the stream key is gone (job finished + cleaned up).
        wrapper = RedisQueueWrapper(job_id, self._client, self._stream_ttl, startup_grace_s=self._startup_grace_s)
        try:
            while True:
                event_id, data, _ts = await wrapper.get()
                if data is None:
                    return  # end-of-stream sentinel
                yield _StreamFrame(seq=None, event_type=event_id, payload=data)
        finally:
            await wrapper.cancel()
