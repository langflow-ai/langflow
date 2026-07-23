"""Scaled background backend: the durable job table IS the work queue.

The facade (``BackgroundExecutionService``) delegates to this when
``settings.background_backend == "scaled"``. There is no broker: the API only
persists the QUEUED job row (``submit`` already does), and separate
``langflow worker`` processes lease-claim rows off the SAME database via
``JobService.claim_next_queued_lease`` — the exact-heartbeat conditional UPDATE
that is already the single-flight primitive for every other reconciler.

Because the queue and the system of record are one table, the redis backend's
failure modes are structurally impossible here: there is no pending/processing
list to drift from the DB (``recover_stranded_queued`` has no equivalent —
a QUEUED row *is* enqueued by definition), and no LREM token protocol (the
conditional UPDATE is the single flight).

``events()`` is the cross-replica reattach contract: replay durable
``job_events`` (seq > last_event_id), then poll the same table for new rows
until the job reaches a terminal status. Ephemeral token frames are not
transported — both existing reattach paths (the in-memory bus and the redis
Stream tail) already drop them via seq-dedup, so durable milestones are the
effective contract on every backend.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import TYPE_CHECKING, Any

from langflow.services.database.models.jobs.model import JobStatus, SignalType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langflow.services.jobs.service import JobService

# Durable statuses that mean the run is over (the event tail drains and ends).
_TERMINAL_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT})
# Statuses that end the event tail: terminal runs, plus SUSPENDED — a paused
# run will produce no more durable frames until it is resumed, so a tail
# waiting on it would poll forever (mirrors the default backend's is_done).
_TAIL_END_STATUSES = _TERMINAL_STATUSES | {JobStatus.SUSPENDED}


def _coerce_uuid(job_id: Any) -> Any:
    """Best-effort coerce a job id string to a UUID for durable-row lookups.

    Callers normally pass a real UUID string, so DB lookups key correctly.
    A non-UUID id is passed through unchanged (tolerated so a test with a
    non-UUID id does not crash the coerce). Shared with the worker loop's
    heartbeat-on-claim stamp.
    """
    if isinstance(job_id, uuid.UUID):
        return job_id
    with contextlib.suppress(ValueError, AttributeError, TypeError):
        return uuid.UUID(job_id)
    return job_id


class DBBackgroundQueue:
    """Database-backed backend behind the BackgroundExecutionService facade."""

    def __init__(
        self,
        *,
        job_service: JobService,
        owner: str | None = None,
        lease_ttl_s: float = 45.0,
        poll_interval_s: float = 0.5,
    ) -> None:
        self._job_service = job_service
        self._owner = owner
        self._lease_ttl_s = lease_ttl_s
        self._poll_interval_s = poll_interval_s

    async def enqueue(self, job_id: str) -> None:
        """No-op: the QUEUED row ``submit`` persisted IS the enqueue.

        Workers poll ``claim_next_queued_lease`` on their idle cadence, so a
        fresh row is picked up within one ``idle_block_ms`` window.
        """
        # ponytail: claim is poll-based; add a pg NOTIFY wake here if the
        # up-to-one-poll claim latency ever matters for background jobs.

    async def teardown(self) -> None:
        """Nothing to close: the backend holds no connection of its own."""

    # ----------------------------------------------------------- worker claim

    async def claim(self, *, block_ms: int = 1000) -> str | None:
        """Lease-claim the oldest claimable QUEUED job, waiting up to block_ms.

        Mirrors the blocking-pop contract the worker loop expects: try to claim,
        and when the queue is empty sleep out the block window before returning
        None so the loop does not hot-spin. The claim stamps owner + heartbeat
        (fresh lease) while LEAVING the row QUEUED — the runner's
        ``execute_with_status`` performs the real QUEUED->IN_PROGRESS flip, so a
        worker that crashes before starting leaves the job re-claimable once its
        lease goes stale.
        """
        job_id = await self._job_service.claim_next_queued_lease(
            owner=self._owner or "worker:unknown",
            lease_ttl_s=self._lease_ttl_s,
        )
        if job_id is not None:
            return str(job_id)
        await asyncio.sleep(max(block_ms, 0) / 1000.0)
        return None

    # ---------------------------------------------------------------- control

    async def stop(self, job_id: str) -> None:
        """Request a cooperative stop via the durable STOP signal.

        Identical to every other backend: the ExecutionSignal(STOP) row is the
        single source of truth, polled by the worker's JobRunner at durable
        vertex/milestone boundaries, so a stop lands at the next boundary and
        survives a worker restart.
        """
        await self._job_service.write_signal(_coerce_uuid(job_id), SignalType.STOP)

    # ------------------------------------------------------------- watchdog

    async def requeue_lost(self, *, lease_ttl_s: float = 45.0) -> list[str]:
        """Reconcile IN_PROGRESS jobs whose worker died (stale/absent lease).

        Liveness-aware: a fresh heartbeat means a live worker owns the run, so
        the row is left untouched. For a genuine orphan:

        * retry-safe flows (job_metadata.retry_safe) are flipped back to QUEUED
          via ``retry_requeue_claim`` — the atomic attempt-bump + status flip —
          until ``attempt`` reaches ``max_attempts``. A QUEUED row is claimable
          by any worker, so the flip IS the re-enqueue.
        * everything else is failed worker_lost (at-most-once for in-flight
          work), with a terminal ``run_failed`` event so a reattached tail ends.

        QUEUED rows need no recovery pass: a stale-leased QUEUED row is
        re-claimable by ``claim_next_queued_lease`` directly.

        Returns the ids flipped back to QUEUED.
        """
        requeued: list[str] = []
        for job_id in await self._job_service.in_progress_workflow_job_ids():
            job = await self._job_service.get_job_by_job_id(job_id)
            if job is None or job.status != JobStatus.IN_PROGRESS:
                continue
            if not self._job_service.is_lease_stale(job, lease_ttl_s=lease_ttl_s):
                continue

            meta = job.job_metadata or {}
            if meta.get("retry_safe"):
                attempt = int(meta.get("attempt", 1))
                max_attempts = int(meta.get("max_attempts", 1))
                if attempt < max_attempts:
                    # Atomic bump+flip guarded by attempt==expected AND
                    # status==IN_PROGRESS, so concurrent watchdogs cannot push a
                    # job past max_attempts (the loser sees rowcount 0).
                    if await self._job_service.retry_requeue_claim(job.job_id, expected_attempt=attempt):
                        requeued.append(str(job_id))
                    continue
            # Default at-most-once, or retries exhausted: fail worker_lost with
            # a terminal event so any reattached tail terminates cleanly. The
            # conditional IN_PROGRESS->FAILED flip is the single-flight token:
            # only the watchdog whose UPDATE matched writes the error blob and
            # appends run_failed, so N concurrent watchdogs cannot append
            # duplicate terminal milestones.
            if await self._job_service.fail_in_progress_job(job.job_id):
                await self._job_service.set_error(job.job_id, {"type": "worker_lost"})
                await self._job_service.append_event(job.job_id, "run_failed", {"type": "worker_lost"})
        return requeued

    # ------------------------------------------------------------- event tail

    async def events(self, job_id: str, last_event_id: int = 0) -> AsyncIterator[Any]:
        """Replay durable events after last_event_id, then poll for new ones.

        Any API replica can call this: everything rides the shared database.
        The tail polls ``read_events`` on ``poll_interval_s`` while the job is
        live. Termination needs a grace pass: CANCELLED, TIMED_OUT, and
        worker_lost all flip the terminal STATUS before their terminal EVENT is
        appended (``execute_with_status`` writes the status, then the runner's
        finally appends ``run_cancelled``/``run_timed_out``; ``requeue_lost``
        flips FAILED, then appends ``run_failed``), so a tail that returned on
        the first terminal observation could end without the terminal
        milestone. On observing a terminal status the tail therefore drains,
        waits one more poll interval, drains again, and ends. The gap between
        flip and append is a handful of sequential DB round trips (widest on
        the CANCELLED path), comfortably inside the default 0.5s interval —
        an operator tuning ``background_poll_interval_s`` very low narrows the
        grace window with it, degrading to a status-only stream end (never a
        hang).

        A job that no worker ever claims stays QUEUED and the tail keeps
        polling: deliberately client-bounded (the job may start any moment;
        two PK-indexed queries per interval), matching the semantics of
        waiting on a queued run.
        """
        # ponytail: poll-based tail (<= poll_interval_s added latency per
        # milestone); switch to pg LISTEN/NOTIFY wakes if that ever matters.
        highest = last_event_id
        durable_id = _coerce_uuid(job_id)

        async def _drain() -> AsyncIterator[Any]:
            nonlocal highest
            for event in await self._job_service.read_events(durable_id, after_seq=highest):
                seq = getattr(event, "seq", None)
                if seq is not None:
                    highest = max(highest, seq)
                yield event

        while True:
            async for event in _drain():
                yield event

            job = await self._job_service.get_job_by_job_id(durable_id)
            if job is None or job.status in _TAIL_END_STATUSES:
                # Grace pass: drain, give the terminal-event append one poll
                # interval to land, drain once more, then end the stream.
                async for event in _drain():
                    yield event
                await asyncio.sleep(self._poll_interval_s)
                async for event in _drain():
                    yield event
                return
            await asyncio.sleep(self._poll_interval_s)
