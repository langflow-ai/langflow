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

import contextlib
import uuid
from typing import TYPE_CHECKING, Any

from langflow.services.background_execution.redis_queue import RedisJobClaimQueue
from langflow.services.database.models.jobs.model import JobStatus, SignalType
from langflow.services.job_queue.service import (
    _CANCEL_CHANNEL_PREFIX,
    RedisJobQueueService,
    RedisQueueWrapper,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langflow.services.jobs.service import JobService


def _as_signal_job_id(job_id: str) -> Any:
    """Best-effort coerce a job id string to a UUID for the durable signal row.

    The facade always passes a real UUID string, so the durable STOP row keys
    match ``unconsumed_signals(UUID)`` lookups. A non-UUID id (the pure pub/sub
    wire test runs with a noop job service) is passed through unchanged.
    """
    if isinstance(job_id, uuid.UUID):
        return job_id
    with contextlib.suppress(ValueError, AttributeError, TypeError):
        return uuid.UUID(job_id)
    return job_id


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

    # ----------------------------------------------------------- worker claim

    async def claim(self, *, block_ms: int = 1000) -> str | None:
        """Claim a job id off the queue for a worker (delegates to the claim queue)."""
        return await self.claim_queue.claim(block_ms=block_ms)

    async def complete(self, job_id: str) -> None:
        """Release a worker's lease on a job (delegates to the claim queue)."""
        await self.claim_queue.complete(job_id)

    # ---------------------------------------------------------------- control

    async def stop(self, job_id: str, *, marker_ttl: int = 60) -> None:
        """Request a cooperative stop: durable signal first, then pub/sub fast-path.

        The ExecutionSignal(STOP) row is the source of truth — a worker polls
        unconsumed_signals at vertex boundaries and stops even if the pub/sub
        message is missed (worker restart, late subscribe). The redis marker +
        PUBLISH is the fast-path so the owning worker reacts immediately.

        The marker/channel conventions mirror RedisJobQueueService exactly so a
        worker running the existing cancel dispatcher / marker-check picks these
        up unchanged (we reuse, not reimplement, the wire path).
        """
        # 1. Durable source of truth. Coerce to UUID so the DB row keys match
        #    unconsumed_signals(UUID) lookups; tolerate non-UUID ids (used in the
        #    pure pub/sub wire test with a noop job service) by passing them
        #    through unchanged.
        await self._job_service.write_signal(_as_signal_job_id(job_id), SignalType.STOP)
        # 2. Fast-path: set the marker (race-safe for a worker that hasn't
        #    subscribed yet) then publish on the cancel channel.
        marker_key = f"{RedisJobQueueService._CANCEL_MARKER_PREFIX}{job_id}"  # noqa: SLF001
        channel = f"{_CANCEL_CHANNEL_PREFIX}{job_id}"
        await self._client.set(marker_key, "1", ex=marker_ttl)
        await self._client.publish(channel, "1")

    # ------------------------------------------------------------- watchdog

    async def requeue_lost(self) -> list[str]:
        """Reconcile orphaned processing-list ids per the at-most-once policy.

        For each id still on the processing list (claimed by a worker that did
        not complete it):

        * QUEUED          -> never started; safe to requeue (at-least-once).
        * IN_PROGRESS     -> in-flight when the worker died. By default this is
          at-most-once: mark FAILED with error {"type": "worker_lost"}. Flows
          that opt in via job_metadata.retry_safe are requeued, bumping
          job_metadata.attempt, until attempt reaches max_attempts.
        * terminal states -> just drop from the processing list.

        Returns the ids that were requeued onto the pending list.
        """
        requeued: list[str] = []
        for job_id in await self.claim_queue.processing_ids():
            job = await self._job_service.get_job_by_job_id(job_id)
            if job is None:
                # No durable row — nothing to reconcile; drop the stale id.
                await self.claim_queue.complete(job_id)
                continue

            if job.status == JobStatus.QUEUED:
                await self._requeue(job_id)
                requeued.append(job_id)
                continue

            if job.status == JobStatus.IN_PROGRESS:
                meta = job.job_metadata or {}
                if meta.get("retry_safe"):
                    attempt = int(meta.get("attempt", 1))
                    max_attempts = int(meta.get("max_attempts", 1))
                    if attempt < max_attempts:
                        await self._job_service.update_job_metadata(job.job_id, {"attempt": attempt + 1})
                        await self._job_service.update_job_status(job.job_id, JobStatus.QUEUED)
                        await self._requeue(job_id)
                        requeued.append(job_id)
                        continue
                # Default at-most-once, or retries exhausted: fail worker_lost.
                # set_error only stores the blob, so flip the status to FAILED
                # (with a finished timestamp) explicitly.
                await self._job_service.update_job_status(job.job_id, JobStatus.FAILED, finished_timestamp=True)
                await self._job_service.set_error(job.job_id, {"type": "worker_lost"})
                await self.claim_queue.complete(job_id)
                continue

            # Terminal (COMPLETED / FAILED / CANCELLED / TIMED_OUT): drop the id.
            await self.claim_queue.complete(job_id)
        return requeued

    async def _requeue(self, job_id: str) -> None:
        """Move an id from the processing list back to pending for re-claim."""
        await self.claim_queue.complete(job_id)
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
