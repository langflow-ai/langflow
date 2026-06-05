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
from langflow.services.job_queue.service import RedisQueueWrapper

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langflow.services.jobs.service import JobService

# Durable statuses that mean the run is over (the reconciler just drops the id).
_TERMINAL_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT})


def _as_signal_job_id(job_id: str) -> Any:
    """Best-effort coerce a job id string to a UUID for the durable signal row.

    The facade always passes a real UUID string, so the durable STOP row keys
    match ``unconsumed_signals(UUID)`` lookups. A non-UUID id is passed through
    unchanged (tolerated so a test with a non-UUID id does not crash the coerce).
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

    async def teardown(self) -> None:
        """Close the redis client so the API replica does not leak its pool.

        The worker process closes its own client on shutdown; the API-side facade
        must close the one it built for this backend too (matches build_worker's
        explicit ``aclose``). Best-effort: a close error must not mask shutdown.
        """
        client = self._client
        if client is not None and hasattr(client, "aclose"):
            with contextlib.suppress(Exception):
                await client.aclose()

    # ----------------------------------------------------------- worker claim

    async def claim(self, *, block_ms: int = 1000) -> str | None:
        """Claim a job id off the queue for a worker (delegates to the claim queue)."""
        return await self.claim_queue.claim(block_ms=block_ms)

    async def complete(self, job_id: str) -> int:
        """Release a worker's lease on a job. Returns the processing-list count removed."""
        return await self.claim_queue.complete(job_id)

    # ---------------------------------------------------------------- control

    async def stop(self, job_id: str) -> None:
        """Request a cooperative stop via the durable STOP signal.

        The ExecutionSignal(STOP) row is the single source of truth: the worker's
        JobRunner polls ``unconsumed_signals`` at each durable vertex/milestone
        boundary and cooperatively cancels, so a stop lands at the next boundary
        and survives a worker restart or late subscribe.

        There is deliberately NO redis pub/sub fast-path here. The background
        worker (run_worker_loop -> WorkerJobRunner -> JobRunner) does not run the
        v1 RedisJobQueueService cancel dispatcher and nothing else subscribes to a
        cancel channel or checks a cancel marker, so a PUBLISH/marker would be a
        no-op in production — a misleading dead fast-path. Scaled stop latency is
        therefore one vertex-boundary poll (bounded by the run's durable-frame
        cadence), proven by the scaled-stop real-redis test.
        """
        # Coerce to UUID so the DB row keys match unconsumed_signals(UUID)
        # lookups; tolerate a non-UUID id by passing it through unchanged.
        await self._job_service.write_signal(_as_signal_job_id(job_id), SignalType.STOP)

    # ------------------------------------------------------------- watchdog

    async def requeue_lost(self, *, lease_ttl_s: float = 45.0) -> list[str]:
        """Reconcile GENUINELY orphaned processing-list ids (stale/absent lease).

        Lease-aware: a processing-list id whose job row has a FRESH heartbeat
        (younger than ``lease_ttl_s``) belongs to a LIVE worker still running it,
        so it is left untouched — this is what stops a booting/scaled-up worker B
        from re-claiming and DOUBLE-RUNNING a job worker A is mid-running, and
        from failing A's live job. Only an id whose lease is stale or never
        recorded is treated as orphaned. A worker stamps a heartbeat on claim,
        so even a just-claimed QUEUED row (still in the QUEUED->IN_PROGRESS
        window) is protected until its lease actually expires.

        For a genuinely orphaned id:

        * QUEUED          -> never started; safe to requeue (at-least-once).
        * IN_PROGRESS     -> in-flight when the worker died. By default this is
          at-most-once: mark FAILED with error {"type": "worker_lost"}. Flows
          that opt in via job_metadata.retry_safe are requeued, atomically
          bumping job_metadata.attempt, until attempt reaches max_attempts.
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

            if job.status in _TERMINAL_STATUSES:
                # Terminal (COMPLETED / FAILED / CANCELLED / TIMED_OUT): drop.
                await self.claim_queue.complete(job_id)
                continue

            # Liveness gate: a fresh lease means a live worker owns this run.
            if not self._job_service.is_lease_stale(job, lease_ttl_s=lease_ttl_s):
                continue

            if job.status == JobStatus.QUEUED:
                # Single-flight via the LREM token so two reconcilers (or a
                # reconciler racing the worker that just flipped it to QUEUED)
                # cannot both push it back to pending.
                if await self._requeue(job_id):
                    requeued.append(job_id)
                continue

            # IN_PROGRESS with a stale/absent lease — the worker died mid-run.
            meta = job.job_metadata or {}
            if meta.get("retry_safe"):
                attempt = int(meta.get("attempt", 1))
                max_attempts = int(meta.get("max_attempts", 1))
                if attempt < max_attempts:
                    # Atomic bump+flip in ONE conditional UPDATE guarded by both
                    # attempt==expected AND status==IN_PROGRESS, so two watchdogs
                    # racing the same lost job cannot both bump it past the cap (the
                    # loser sees status already QUEUED -> rowcount 0). Closes the
                    # window a separate increment + status flip left open.
                    if await self._job_service.retry_requeue_claim(
                        job.job_id, expected_attempt=attempt
                    ) and await self._requeue(job_id):
                        requeued.append(job_id)
                    # Lost the race: another reconciler already handled it; skip.
                    continue
            # Default at-most-once, or retries exhausted: fail worker_lost.
            # set_error only stores the blob, so flip the status to FAILED
            # (with a finished timestamp) explicitly.
            await self._job_service.update_job_status(job.job_id, JobStatus.FAILED, finished_timestamp=True)
            await self._job_service.set_error(job.job_id, {"type": "worker_lost"})
            # One structured line per reconciled orphan. event_type="bg_job" is the
            # marker key (structlog reserves "event" for the message); a logging
            # failure must never break the watchdog, so the emit is guarded.
            with contextlib.suppress(Exception):
                from lfx.log import logger

                extra = {
                    "flow_id": str(job.flow_id) if job.flow_id is not None else None,
                    "user_id": str(job.user_id) if job.user_id is not None else None,
                    "attempt": int(meta["attempt"]) if "attempt" in meta else None,
                }
                await logger.ainfo(
                    "background job worker_lost",
                    event_type="bg_job",
                    job_id=str(job.job_id),
                    status="failed",
                    reason="worker_lost",
                    backend="scaled",
                    **{k: v for k, v in extra.items() if v is not None},
                )
            await self.claim_queue.complete(job_id)
        return requeued

    async def _requeue(self, job_id: str) -> bool:
        """Move an id from processing back to pending. Returns True if we owned it.

        The ``complete`` LREM is the single-flight token: only the reconciler
        whose LREM actually removed the id (count > 0) re-enqueues it, so two
        watchdogs racing the same orphaned id cannot push two pending entries.
        """
        removed = await self.claim_queue.complete(job_id)
        if removed <= 0:
            return False
        await self.claim_queue.enqueue(job_id)
        return True

    async def recover_stranded_queued(self) -> list[str]:
        """Re-enqueue QUEUED workflow rows present on NEITHER redis list.

        Covers the API-crash window between persisting a QUEUED row and the
        ``enqueue`` LPUSH (and a redis pending-list loss): such a row is in the
        DB but invisible to ``requeue_lost`` (which scans only the processing
        list). Without this the job is stuck QUEUED forever in scaled mode.

        Each stranded id is claimed atomically (``claim_queued_job`` flips it to
        IN_PROGRESS only if it wins), then immediately put back to QUEUED and
        LPUSHed so a real worker re-runs it. The flip-and-restore is the
        single-flight guard so two workers' watchdogs cannot both LPUSH it.
        Returns the ids re-enqueued.
        """
        on_redis = set(await self.claim_queue.processing_ids())
        pending = await self._client.lrange(self.claim_queue.pending_key, 0, -1)
        on_redis.update(p.decode() if isinstance(p, bytes) else p for p in pending)

        recovered: list[str] = []
        for job_id in await self._job_service.queued_workflow_job_ids():
            sid = str(job_id)
            if sid in on_redis:
                continue
            # Claim atomically: only the winner re-enqueues. Restore to QUEUED so
            # a real runner re-runs it (claim flips it IN_PROGRESS as the guard).
            if not await self._job_service.claim_queued_job(job_id):
                continue
            await self._job_service.update_job_status(job_id, JobStatus.QUEUED)
            await self.claim_queue.enqueue(sid)
            recovered.append(sid)
        return recovered

    async def events(self, job_id: str, last_event_id: int = 0) -> AsyncIterator[Any]:
        """Replay durable events after last_event_id, then tail the live Stream.

        Any API replica can call this: durable milestones come from the DB so a
        replica that didn't start the job still serves full history; live
        ephemeral frames come off the shared redis Stream via RedisQueueWrapper.

        Dedup-at-the-seam: the worker publishes every durable milestone to BOTH
        the DB and the Stream, so a Stream tail from ``0-0`` would re-deliver each
        milestone already replayed from the DB. We track the highest durable seq
        replayed and skip any Stream frame whose stamped seq is ``<= highest`` —
        the SAME rule the in-memory bus uses (``item.seq <= highest: continue``),
        so the default and scaled reattach paths agree: each milestone is
        delivered exactly once, and an ephemeral frame is passed only when its seq
        is strictly newer than everything already seen.
        """
        # 1. Durable replay from the DB (the Last-Event-ID cursor is seq).
        highest = last_event_id
        for event in await self._job_service.read_events(job_id, after_seq=last_event_id):
            seq = getattr(event, "seq", None)
            if seq is not None:
                highest = max(highest, seq)
            yield event

        # 2. Live tail of the redis Stream. Each Stream frame carries the durable
        #    seq the worker stamped (``event_id`` field); skip any frame already
        #    covered by the DB replay so it is not delivered twice. The wrapper
        #    self-terminates on the end-of-stream sentinel or when the stream key
        #    is gone (job finished + cleaned up).
        wrapper = RedisQueueWrapper(job_id, self._client, self._stream_ttl, startup_grace_s=self._startup_grace_s)
        try:
            while True:
                event_id, data, _ts = await wrapper.get()
                if data is None:
                    return  # end-of-stream sentinel
                frame_seq = self._parse_stream_seq(event_id)
                if frame_seq is not None and frame_seq <= highest:
                    # Already replayed from the DB (or seen before the reattach
                    # cursor) — drop so the milestone is delivered exactly once.
                    continue
                if frame_seq is not None:
                    highest = frame_seq
                yield _StreamFrame(seq=None, event_type=event_id, payload=data)
        finally:
            await wrapper.cancel()

    @staticmethod
    def _parse_stream_seq(event_id: Any) -> int | None:
        """Parse the durable seq the worker stamped on a Stream frame's ``event_id``.

        ``RedisStreamLiveBus`` sets ``event_id = str(frame.seq)``; a non-numeric
        value (a legacy/foreign frame) has no durable seq, so it is never deduped.
        """
        try:
            return int(event_id)
        except (TypeError, ValueError):
            return None
