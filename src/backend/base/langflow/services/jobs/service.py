"""Job service for managing workflow job status and tracking."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlmodel import col, func, select

from langflow.services.base import Service
from langflow.services.database.models.jobs.crud import (
    get_latest_jobs_by_asset_ids,
    update_job_status,
)
from langflow.services.database.models.jobs.model import (
    ExecutionSignal,
    Job,
    JobEvent,
    JobStatus,
    JobType,
    SignalType,
)
from langflow.services.deps import session_scope
from langflow.services.jobs.exceptions import DuplicateJobError

# Bounded retries for append_event's optimistic seq assignment. Real contention is
# at most a couple of concurrent appenders per job (a worker plus the orphan sweep,
# or multiple processes in the scaled backend), so this is comfortably generous.
_APPEND_EVENT_MAX_RETRIES = 50


class JobService(Service):
    """Service for managing workflow jobs."""

    name = "jobs_service"

    def __init__(self):
        """Initialize the job service."""
        self.set_ready()

    async def get_jobs_by_flow_id(
        self, flow_id: UUID | str, user_id: UUID, page: int = 1, page_size: int = 10
    ) -> list[Job]:
        """Get jobs for a specific flow with pagination, filtered by user.

        Args:
            flow_id: The flow ID to filter jobs by
            user_id: The user ID to enforce ownership
            page: Page number (1-indexed)
            page_size: Number of jobs per page

        Returns:
            List of Job objects for the specified flow
        """
        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)

        async with session_scope() as session:
            stmt = (
                select(Job)
                .where(Job.flow_id == flow_id)
                .where((Job.user_id == user_id) | (Job.user_id.is_(None)))
                .order_by(col(Job.created_timestamp).desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.exec(stmt)
            return list(result.all())

    async def get_job_by_job_id(self, job_id: UUID | str, user_id: UUID | None = None) -> Job | None:
        """Get job for a specific job ID.

        Args:
            job_id: The job ID to filter jobs by
            user_id: When provided, restricts the result to jobs owned by this user
                or legacy jobs with no owner (user_id IS NULL).

        Returns:
            Job object for the specified job ID, or None if not found or not accessible
        """
        if isinstance(job_id, str):
            job_id = UUID(job_id)

        async with session_scope() as session:
            stmt = select(Job).where(Job.job_id == job_id)
            if user_id:
                stmt = stmt.where((Job.user_id == user_id) | (Job.user_id.is_(None)))
            result = await session.exec(stmt)
            return result.first()

    async def create_job(
        self,
        job_id: UUID,
        flow_id: UUID,
        job_type: JobType = JobType.WORKFLOW,
        asset_id: UUID | None = None,
        asset_type: str | None = None,
        user_id: UUID | None = None,
        dedupe_key: str | None = None,
    ) -> Job:
        """Create a new job record with QUEUED status.

        Args:
            job_id: The job ID
            flow_id: The flow ID
            user_id: The user ID
            job_type: The job type
            asset_id: The asset ID
            asset_type: The asset type
            user_id: The user ID who owns this job
            dedupe_key: Optional idempotency key to prevent duplicate jobs for the same batch

        Returns:
            Created Job object
        """
        if isinstance(job_id, str):
            job_id = UUID(job_id)

        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)

        async with session_scope() as session:
            if dedupe_key is not None:
                # Scope uniqueness to the owner: a client-controlled
                # idempotency_key flows into dedupe_key, so a GLOBAL count would
                # let user A collide with / DoS user B's key (and the error would
                # leak that a job with that key exists for someone else). When
                # user_id is None (single-tenant AUTO_LOGIN), the ownerless rows
                # form their own dedupe space.
                stmt = (
                    select(func.count())
                    .select_from(Job)
                    .where(Job.dedupe_key == dedupe_key)
                    .where(col(Job.status).in_([JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.COMPLETED]))
                )
                stmt = (
                    stmt.where(Job.user_id == user_id)
                    if user_id is not None
                    else stmt.where(col(Job.user_id).is_(None))
                )
                result = await session.exec(stmt)
                if result.one() > 0:
                    msg = f"A non-retryable job with dedupe_key={dedupe_key!r} already exists"
                    raise DuplicateJobError(msg)

            job = Job(
                job_id=job_id,
                flow_id=flow_id,
                status=JobStatus.QUEUED,
                type=job_type,
                asset_id=asset_id,
                asset_type=asset_type,
                user_id=user_id,
                dedupe_key=dedupe_key,
            )
            session.add(job)
            await session.flush()
            return job

    async def update_job_status(
        self, job_id: UUID, status: JobStatus, *, finished_timestamp: bool = False
    ) -> Job | None:
        """Update job status and optionally set finished timestamp.

        Args:
            job_id: The job ID to update
            status: New status value
            finished_timestamp: If True, set finished_timestamp to current time

        Returns:
            Updated Job object or None if not found
        """
        async with session_scope() as session:
            finished_at = datetime.now(timezone.utc) if finished_timestamp else None
            return await update_job_status(session, job_id, status, finished_timestamp=finished_at)

    async def update_job_metadata(
        self,
        job_id: UUID,
        patch: dict,
        *,
        replace: bool = False,
    ) -> Job | None:
        """Merge ``patch`` into ``job.job_metadata`` (or replace it).

        Domain-owned per-job context lives here — KB ingestion writes
        counters and per-item outcomes, workflow runs can record their
        own keys, etc. The wrapped coroutine inside
        ``execute_with_status`` calls this as it makes progress so the
        UI can read partial state without waiting for the job to
        finish.

        Args:
            job_id: The job ID to update.
            patch: Top-level keys to merge into the existing dict. Keys
                in ``patch`` overwrite same-named keys on the existing
                row; nested dicts are NOT deep-merged — callers that
                want deep-merge semantics should read, merge, and pass
                the full result.
            replace: When ``True``, replace ``job_metadata`` outright
                instead of merging. Use when the caller is the sole
                writer and wants a known-shape blob (e.g. KB ingestion
                finalize).

        Returns:
            The updated Job, or ``None`` if the row does not exist.
        """
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return None
            if replace or job.job_metadata is None:
                job.job_metadata = dict(patch)
            else:
                # Shallow merge — callers wanting deep-merge own the
                # composition. This keeps the helper predictable.
                job.job_metadata = {**job.job_metadata, **patch}
            session.add(job)
            await session.flush()
            return job

    async def set_result(self, job_id: UUID, result: dict | None) -> Job | None:
        """Persist the durable terminal result blob for a job.

        ``None`` clears a previously-written result (used when a late stop
        reconciles a racing completion to CANCELLED and the completed-run result
        must not linger on the terminal row).

        Returns the updated Job, or None if the row does not exist.
        """
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return None
            job.result = result
            session.add(job)
            await session.flush()
            return job

    async def set_error(self, job_id: UUID, error: dict) -> Job | None:
        """Persist the durable terminal error blob for a job.

        Returns the updated Job, or None if the row does not exist.
        """
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return None
            job.error = error
            session.add(job)
            await session.flush()
            return job

    async def append_event(self, job_id: UUID, event_type: str, payload: dict) -> int:
        """Append a durable event for a job and return its per-job seq.

        seq is assigned as max(existing seq for job) + 1. UNIQUE(job_id, seq)
        guards against concurrent double-assignment: a colliding writer hits
        IntegrityError, and we retry with a freshly re-read max so every event
        lands gap-free even when a worker and the orphan sweep (or, in the
        scaled backend, multiple processes) append to the same job at once.
        """
        last_exc: Exception | None = None
        for attempt in range(_APPEND_EVENT_MAX_RETRIES):
            try:
                async with session_scope() as session:
                    stmt = select(func.max(JobEvent.seq)).where(JobEvent.job_id == job_id)
                    result = await session.exec(stmt)
                    current_max = result.one()
                    next_seq = (current_max or 0) + 1
                    event = JobEvent(job_id=job_id, seq=next_seq, event_type=event_type, payload=payload)
                    session.add(event)
                    await session.flush()
                    return next_seq
            except IntegrityError as exc:
                # Lost the (job_id, seq) race — re-read max and try again.
                last_exc = exc
            except OperationalError as exc:
                # SQLite "database is locked"/busy under concurrent writers is transient.
                if "lock" not in str(exc).lower() and "busy" not in str(exc).lower():
                    raise
                last_exc = exc
            # Yield + brief backoff so the contending writer can commit before we retry.
            await asyncio.sleep(min(0.05, 0.002 * (attempt + 1)))
        # Exhausted retries under sustained contention — surface the last collision.
        msg = f"append_event exhausted {_APPEND_EVENT_MAX_RETRIES} retries for job {job_id} (seq contention)"
        raise RuntimeError(msg) from last_exc

    async def read_events(self, job_id: UUID, after_seq: int = 0) -> list[JobEvent]:
        """Return durable events for a job with seq > after_seq, ordered by seq.

        ``after_seq`` is the SSE Last-Event-ID cursor; pass 0 to read from the
        start.
        """
        async with session_scope() as session:
            stmt = (
                select(JobEvent)
                .where(JobEvent.job_id == job_id)
                .where(JobEvent.seq > after_seq)
                .order_by(col(JobEvent.seq).asc())
            )
            result = await session.exec(stmt)
            return list(result.all())

    async def write_signal(self, job_id: UUID, signal_type: SignalType, data: dict | None = None) -> ExecutionSignal:
        """Write a control signal for a job (e.g. STOP).

        The runner consumes it at the next vertex boundary and stamps
        ``consumed_at``.
        """
        async with session_scope() as session:
            signal = ExecutionSignal(job_id=job_id, signal_type=signal_type, data=data)
            session.add(signal)
            await session.flush()
            await session.refresh(signal)
            return signal

    async def unconsumed_signals(self, job_id: UUID) -> list[ExecutionSignal]:
        """Return signals for a job that have not yet been consumed, oldest first."""
        async with session_scope() as session:
            stmt = (
                select(ExecutionSignal)
                .where(ExecutionSignal.job_id == job_id)
                .where(col(ExecutionSignal.consumed_at).is_(None))
                .order_by(col(ExecutionSignal.created_at).asc())
            )
            result = await session.exec(stmt)
            return list(result.all())

    async def consume_signals(self, job_id: UUID, signal_type: SignalType) -> int:
        """Stamp ``consumed_at`` on a job's unconsumed signals of ``signal_type``.

        The runner calls this once it has acted on a STOP so the signal does not
        linger: ``unconsumed_signals`` filters on ``consumed_at IS NULL``, so an
        unstamped STOP would (a) grow the table forever and (b) make a later
        re-enqueued run of the same job self-cancel off the stale signal. Returns
        the number of rows stamped.
        """
        now = datetime.now(timezone.utc)
        async with session_scope() as session:
            stmt = (
                select(ExecutionSignal)
                .where(ExecutionSignal.job_id == job_id)
                .where(ExecutionSignal.signal_type == signal_type)
                .where(col(ExecutionSignal.consumed_at).is_(None))
            )
            result = await session.exec(stmt)
            rows = list(result.all())
            for row in rows:
                row.consumed_at = now
                session.add(row)
            await session.flush()
            return len(rows)

    async def heartbeat(self, job_id: UUID, owner: str) -> None:
        """Stamp the running owner + a fresh heartbeat on the job row.

        This is the liveness signal a reconciler reads to tell a live in-flight
        run from a genuinely orphaned one: only the running owner refreshes it,
        and a reconciler only fails/requeues a job whose heartbeat is STALE
        (``is_lease_stale``). Stored in ``job_metadata`` (no new column, matching
        the attempt-accounting decision in the design) via a shallow merge so the
        persisted request / retry flags are preserved.
        """
        now = datetime.now(timezone.utc).isoformat()
        await self.update_job_metadata(job_id, {"owner": owner, "heartbeat_at": now})

    @staticmethod
    def is_lease_stale(job: Job, *, lease_ttl_s: float) -> bool:
        """True when a job's heartbeat is older than ``lease_ttl_s`` (or absent).

        An absent heartbeat means the owner never recorded liveness (it died in
        the QUEUED->IN_PROGRESS window, or this is a legacy row), so it is
        treated as stale and reconcilable. A fresh heartbeat (within the TTL)
        means a live owner is running the job and a reconciler must NOT touch it.
        """
        meta = job.job_metadata or {}
        raw = meta.get("heartbeat_at")
        if not raw:
            return True
        try:
            hb = datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            return True
        if hb.tzinfo is None:
            hb = hb.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - hb).total_seconds()
        return age > lease_ttl_s

    async def increment_attempt_if(self, job_id: UUID, *, expected: int, new: int) -> bool:
        """Atomically bump ``job_metadata.attempt`` from ``expected`` to ``new``.

        Returns True only for the single caller whose read-modify-write observed
        ``attempt == expected`` and committed. Concurrent reconcilers reading the
        same ``expected`` race on the row, but UNIQUE row identity + a re-read
        under the write lock means only one transaction's conditional UPDATE
        matches: every other sees ``rowcount == 0`` and returns False. This
        closes the lost-update window where two reconcilers both bumped 1->2 and
        each requeued, pushing a job past ``max_attempts``.

        Portable across SQLite and Postgres: the conditional UPDATE matches the
        JSON-extracted attempt cast to integer, the same single-row-conditional
        primitive ``claim_queued_job`` relies on.
        """
        from sqlalchemy import Integer
        from sqlalchemy import cast as sa_cast
        from sqlmodel import update

        attempt_expr = sa_cast(col(Job.job_metadata)["attempt"].as_string(), Integer)
        async with session_scope() as session:
            # Read the current metadata so we can write back a full merged blob
            # (JSON columns are replaced wholesale, not patched in place).
            job = await session.get(Job, job_id)
            if job is None:
                return False
            merged = {**(job.job_metadata or {}), "attempt": new}
            stmt = update(Job).where(Job.job_id == job_id, attempt_expr == expected).values(job_metadata=merged)
            result = await session.exec(stmt)  # type: ignore[call-overload]
            await session.flush()
            return result.rowcount == 1

    async def retry_requeue_claim(self, job_id: UUID, *, expected_attempt: int) -> bool:
        """Atomically bump ``attempt`` AND flip IN_PROGRESS->QUEUED for a retry requeue.

        A SINGLE conditional UPDATE guarded by BOTH ``attempt == expected_attempt``
        AND ``status == IN_PROGRESS``. The winner sets ``attempt = expected+1`` and
        ``status = QUEUED`` in one statement; every racing reconciler then sees
        either a changed attempt or a non-IN_PROGRESS status and gets
        ``rowcount == 0``. This closes the window that a separate increment +
        ``update_job_status(QUEUED)`` left open, where a second reconciler could
        read the already-bumped attempt on a still-IN_PROGRESS row and bump it
        again past ``max_attempts``. Portable across SQLite and Postgres.
        """
        from sqlalchemy import Integer
        from sqlalchemy import cast as sa_cast
        from sqlmodel import update

        attempt_expr = sa_cast(col(Job.job_metadata)["attempt"].as_string(), Integer)
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return False
            merged = {**(job.job_metadata or {}), "attempt": expected_attempt + 1}
            stmt = (
                update(Job)
                .where(
                    Job.job_id == job_id,
                    attempt_expr == expected_attempt,
                    Job.status == JobStatus.IN_PROGRESS,
                )
                .values(job_metadata=merged, status=JobStatus.QUEUED)
            )
            result = await session.exec(stmt)  # type: ignore[call-overload]
            await session.flush()
            return result.rowcount == 1

    async def claim_queued_lease(self, job_id: UUID, *, owner: str, lease_ttl_s: float) -> bool:
        """Lease-claim a QUEUED row WITHOUT flipping its status. Returns True if won.

        Single-flight ownership for the default re-enqueue path that, unlike
        ``claim_queued_job``, does NOT move the row to IN_PROGRESS. Keeping the
        row QUEUED means a re-enqueue that crashes before the runner emits its
        first transition leaves the job re-runnable (the sweep never fails QUEUED
        rows, and the next boot re-claims it once this lease goes stale) instead
        of becoming a stranded IN_PROGRESS that gets failed worker_lost. The
        runner's ``execute_with_status`` performs the real QUEUED->IN_PROGRESS
        flip when it actually starts.

        The claim succeeds only when the row is QUEUED and its current lease is
        absent or stale, and the conditional UPDATE matches the EXACT prior
        ``heartbeat_at`` we read, so two workers racing the same stale row see
        only one ``rowcount == 1``. Portable across SQLite and Postgres.
        """
        from sqlmodel import update

        hb_expr = col(Job.job_metadata)["heartbeat_at"].as_string()
        now = datetime.now(timezone.utc).isoformat()
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None or job.status != JobStatus.QUEUED:
                return False
            meta = job.job_metadata or {}
            prior_hb = meta.get("heartbeat_at")
            # A fresh lease means another worker already owns this claim window.
            if not self.is_lease_stale(job, lease_ttl_s=lease_ttl_s):
                return False
            merged = {**meta, "owner": owner, "heartbeat_at": now}
            # Guard on the exact prior heartbeat so a concurrent claimer that
            # already stamped its own loses the conditional UPDATE.
            guard = hb_expr.is_(None) if prior_hb is None else hb_expr == prior_hb
            stmt = (
                update(Job)
                .where(Job.job_id == job_id, Job.status == JobStatus.QUEUED, guard)
                .values(job_metadata=merged)
            )
            result = await session.exec(stmt)  # type: ignore[call-overload]
            await session.flush()
            return result.rowcount == 1

    async def queued_workflow_job_ids(self) -> list[UUID]:
        """Return the ids of every QUEUED workflow job (for strand recovery)."""
        async with session_scope() as session:
            stmt = select(Job.job_id).where(
                Job.status == JobStatus.QUEUED,
                Job.type == JobType.WORKFLOW,
            )
            result = await session.exec(stmt)
            return list(result.all())

    async def claim_queued_job(self, job_id: UUID) -> bool:
        """Atomically claim a QUEUED job for execution. Returns True if we won.

        Single-flight guard for the startup sweep: a conditional
        ``UPDATE job SET status=IN_PROGRESS WHERE job_id=? AND status='QUEUED'``
        means only ONE racer's update affects a row (``rowcount == 1``); every
        other concurrent sweeper sees ``rowcount == 0`` and must not enqueue.
        Works identically on SQLite and Postgres (a single-row conditional UPDATE
        is atomic on both), so two uvicorn workers booting against one DB cannot
        both re-run the same non-idempotent QUEUED job.
        """
        from sqlmodel import update

        async with session_scope() as session:
            stmt = (
                update(Job)
                .where(Job.job_id == job_id, Job.status == JobStatus.QUEUED)
                .values(status=JobStatus.IN_PROGRESS)
            )
            result = await session.exec(stmt)  # type: ignore[call-overload]
            await session.flush()
            return result.rowcount == 1

    async def sweep_orphans(self, *, lease_ttl_s: float = 30.0) -> list[UUID]:
        """Reconcile GENUINELY orphaned IN_PROGRESS jobs (stale/absent heartbeat).

        Liveness-aware: only an IN_PROGRESS row whose heartbeat is older than
        ``lease_ttl_s`` (or never recorded) is treated as orphaned. A row with a
        FRESH heartbeat means a live owner is mid-run, so the sweep must NOT
        touch it — this is what stops a booting worker B from flipping worker A's
        actively-running job FAILED(worker_lost) under ``gunicorn -w N``.

        For a real orphan, mark it FAILED with a worker_lost error, stamp
        finished_timestamp, and append a terminal ``run_failed`` event so a
        reattacher always sees a clean end. QUEUED jobs are intentionally
        untouched (at-least-once: they get re-picked by a fresh worker).

        Returns the ids of the jobs transitioned to FAILED.
        """
        error_payload = {"type": "worker_lost"}
        reconciled: list[UUID] = []
        # Per-reconciled forensic identifiers, captured inside the session loop
        # while the rows are loaded so the worker_lost log can carry flow_id/
        # user_id without a second query.
        reconciled_meta: dict[UUID, tuple[str | None, str | None]] = {}
        async with session_scope() as session:
            stmt = select(Job).where(Job.status == JobStatus.IN_PROGRESS)
            result = await session.exec(stmt)
            in_progress = list(result.all())
            now = datetime.now(timezone.utc)
            for job in in_progress:
                if not self.is_lease_stale(job, lease_ttl_s=lease_ttl_s):
                    # Live owner still heartbeating — leave the run alone.
                    continue
                job.status = JobStatus.FAILED
                job.error = dict(error_payload)
                job.finished_timestamp = now
                session.add(job)
                reconciled.append(job.job_id)
                reconciled_meta[job.job_id] = (
                    str(job.flow_id) if job.flow_id is not None else None,
                    str(job.user_id) if job.user_id is not None else None,
                )
            await session.flush()
        # Function-local import: background_execution imports from jobs, so a
        # module-level import here would risk a cycle. The metrics module itself
        # only pulls in deps, so the local import is cheap and safe. Only the
        # backend label for the log is needed — outcome counts are DB-derived in
        # the API-side collector, not emitted in-process here.
        from lfx.log import logger

        from langflow.services.background_execution import metrics as bg_metrics

        backend = bg_metrics.current_backend()
        # Append the terminal milestone via append_event (its own session) so the
        # IntegrityError/seq-collision retry applies: a seq collision with a
        # concurrent appender can no longer roll back the whole sweep.
        for job_id in reconciled:
            await self.append_event(job_id, "run_failed", dict(error_payload))
            # One structured line per reconciled orphan. event_type="bg_job" is the
            # marker key (structlog reserves "event" for the message); a logging
            # failure must never break the sweep, so the emit is guarded.
            flow_id, user_id = reconciled_meta.get(job_id, (None, None))
            with contextlib.suppress(Exception):
                extra = {"flow_id": flow_id, "user_id": user_id}
                await logger.ainfo(
                    "background job worker_lost",
                    event_type="bg_job",
                    job_id=str(job_id),
                    status="failed",
                    reason="worker_lost",
                    backend=backend,
                    **{k: v for k, v in extra.items() if v is not None},
                )
        return reconciled

    async def get_latest_jobs_by_asset_ids(self, asset_ids: Sequence[UUID | str]) -> dict[UUID, Job]:
        """Get the latest job for each asset ID in a single batch query.

        Args:
            asset_ids: List of asset IDs (UUID or string) to fetch jobs for

        Returns:
            Dictionary mapping asset_id (UUID) to the latest Job object
        """
        # Convert all asset_ids to UUID
        uuid_asset_ids = [UUID(aid) if isinstance(aid, str) else aid for aid in asset_ids]

        async with session_scope() as session:
            return await get_latest_jobs_by_asset_ids(session, uuid_asset_ids)

    async def cancel_in_flight_jobs_by_asset(
        self,
        asset_id: UUID | str,
        asset_type: str,
        *,
        user_id: UUID | None = None,
    ) -> list[UUID]:
        """Mark every queued / in-progress job for ``asset_id`` CANCELLED.

        Used by the asset-delete flows (KB, Memory Base, …) so an
        in-flight ingestion stops writing to (and thereby recreating)
        the asset's storage. The ingestion's own ``is_job_cancelled``
        poll picks up the new status and bails out via the cancelled
        handler.

        Returns the ids of the jobs transitioned. Empty list when
        nothing is in flight.
        """
        normalized_id = UUID(asset_id) if isinstance(asset_id, str) else asset_id
        async with session_scope() as session:
            stmt = select(Job).where(
                Job.asset_id == normalized_id,
                Job.asset_type == asset_type,
                col(Job.status).in_([JobStatus.QUEUED, JobStatus.IN_PROGRESS]),
            )
            if user_id is not None:
                stmt = stmt.where((Job.user_id == user_id) | (col(Job.user_id).is_(None)))
            result = await session.exec(stmt)
            jobs = list(result.all())
            if not jobs:
                return []
            now = datetime.now(timezone.utc)
            for job in jobs:
                job.status = JobStatus.CANCELLED
                job.finished_timestamp = now
                session.add(job)
            await session.flush()
            return [job.job_id for job in jobs]

    async def execute_with_status(self, job_id: UUID, run_coro_func, *args, **kwargs):
        """Wrapper that manages job status lifecycle around a coroutine.

        This function:
        1. Updates status to IN_PROGRESS before execution
        2. Executes the wrapped function
        3. Updates status to COMPLETED on success or FAILED on error
        4. Sets finished_timestamp when done

        Args:
            job_id: The job ID
            run_coro_func: The coroutine function to wrap
            *args: Positional arguments to pass to run_coro_func
            **kwargs: Keyword arguments to pass to run_coro_func

        Returns:
            The result from run_coro_func

        Raises:
            Exception: Re-raises any exception from run_coro_func after updating status
        """
        from lfx.log import logger

        await logger.ainfo(f"Starting job execution: job_id={job_id}")

        try:
            # Update to IN_PROGRESS
            await logger.adebug(f"Updating job {job_id} status to IN_PROGRESS")
            await self.update_job_status(job_id, JobStatus.IN_PROGRESS)

            # Execute the wrapped function
            await logger.ainfo(f"Executing job function for job_id={job_id}")
            result = await run_coro_func(*args, **kwargs)

        except AssertionError as e:
            # Handle missing required arguments
            await logger.aerror(f"Job {job_id} failed with AssertionError: {e}")
            await self.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
            raise

        except asyncio.TimeoutError as e:
            # Handle timeout specifically
            await logger.aerror(f"Job {job_id} timed out: {e}")
            await self.update_job_status(job_id, JobStatus.TIMED_OUT, finished_timestamp=True)
            raise

        except asyncio.CancelledError as exc:
            # Check the message code to determine if this was user-initiated or system-initiated
            if exc.args and exc.args[0] == "LANGFLOW_USER_CANCELLED":
                # User-initiated cancellation, update status to CANCELLED
                await logger.awarning(f"Job {job_id} was cancelled by user")
                await self.update_job_status(job_id, JobStatus.CANCELLED, finished_timestamp=True)
            else:
                # System-initiated cancellation - update status to FAILED
                await logger.awarning(f"Job {job_id} was cancelled by system")
                await self.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
            raise

        except Exception as e:
            # Handle any other error
            await logger.aexception(f"Job {job_id} failed with unexpected error: {e}")
            await self.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
            raise
        else:
            # Update to COMPLETED
            await logger.ainfo(f"Job {job_id} completed successfully")
            await self.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)
            return result

    async def _validate_ownership(self, job_id: UUID, user_id: UUID) -> Job:
        """Verify that a job exists and belongs to the specified user.

        Raises:
            ValueError: If the job is not found or is NOT owned by the user.
        """
        job = await self.get_job_by_job_id(job_id)
        if job is None:
            msg = f"Job {job_id} not found"
            raise ValueError(msg)
        if job.user_id is not None and job.user_id != user_id:
            msg = f"Access denied for job {job_id}"
            raise ValueError(msg)
        return job
