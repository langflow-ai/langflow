"""Background (durable, re-attachable) execution for V2 workflows.

A background run is driven by ``_stream_event_frames`` (from
``workflow_execution``) and its protocol-native SSE frames are buffered in a
process-local ``_BackgroundRun`` so a disconnected client can re-attach and
replay. ``_BACKGROUND_RUNS`` is the bounded registry keyed by job_id; the job
row in the database lets ``GET /workflows`` and ``POST /workflows/stop`` keep
working across re-attaches.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable, Iterable
from uuid import UUID

from fastapi import BackgroundTasks, Request
from fastapi.sse import format_sse_event
from lfx.log.logger import logger
from lfx.schema.workflow import JobId, JobStatus, WorkflowJobResponse

from langflow.api.v2.adapters import (
    StreamAdapterContext,
    StreamEvent,
    UnknownStreamProtocolError,
    get_stream_adapter,
)
from langflow.api.v2.converters import ParsedWorkflowRun
from langflow.api.v2.workflow_execution import _stream_event_frames
from langflow.exceptions.api import (
    WorkflowQueueFullError,
    WorkflowResourceError,
    WorkflowServiceUnavailableError,
)
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_job_service, get_queue_service


async def _cancel_workflow_queue_job(job_id: str) -> bool:
    """Lazily call the shared build cancellation path to avoid import cycles."""
    from langflow.api.build import cancel_flow_build
    from langflow.services.job_queue.service import JobQueueNotFoundError

    try:
        return await cancel_flow_build(job_id=job_id, queue_service=get_queue_service())
    except JobQueueNotFoundError:
        return False


_CancelEventsFactory = Callable[[str], Iterable[StreamEvent]]


class _BackgroundRun:
    """In-memory buffer of a background run's protocol-native SSE frames for re-attach.

    The buffer lives in the process; restarts drop it. Multiple readers can
    re-attach concurrently and tail until the run ends. The frames are
    already serialized in the protocol the original POST requested via
    ``stream_protocol``; re-attach replays them as-is. Mixing protocols
    across a single run is not supported.

    Per-run frame count is bounded by ``_MAX_FRAMES_PER_BACKGROUND_RUN`` so a
    long verbose run (token-by-token streams, repeated tool calls) cannot
    exhaust process memory while ``_MAX_BACKGROUND_RUNS`` only caps the
    number of buffers. When the cap is reached the oldest frames are
    evicted; re-attach with ``Last-Event-ID`` past that point will start
    from the new buffer head (replay loss is preferred over OOM).
    """

    def __init__(self, user_id: str, stream_protocol: str = "agui") -> None:
        self.user_id = user_id
        self.stream_protocol = stream_protocol
        self._cancel_events: _CancelEventsFactory | None = None
        self.frames: list[bytes] = []
        # Index of the first frame still in ``frames`` (monotonic across the
        # life of the buffer). Once eviction starts, ``frames[i]`` corresponds
        # to logical event id ``base_index + i``.
        self.base_index = 0
        self.done = False
        self._cond = asyncio.Condition()

    def set_cancel_events(self, cancel_events: _CancelEventsFactory) -> None:
        self._cancel_events = cancel_events

    @property
    def has_cancel_events(self) -> bool:
        return self._cancel_events is not None

    def _append_locked(self, frame: bytes) -> None:
        self.frames.append(frame)
        overflow = len(self.frames) - _MAX_FRAMES_PER_BACKGROUND_RUN
        if overflow > 0:
            del self.frames[:overflow]
            self.base_index += overflow

    async def append(self, frame: bytes) -> None:
        async with self._cond:
            self._append_locked(frame)
            self._cond.notify_all()

    async def finish(self) -> None:
        async with self._cond:
            self.done = True
            self._cond.notify_all()

    async def finish_cancelled(self, reason: str) -> None:
        """Append cancellation terminal events and finish replay exactly once."""
        async with self._cond:
            if self.done:
                return
            events: list[StreamEvent] = []
            if self._cancel_events is not None:
                with contextlib.suppress(Exception):
                    events = list(self._cancel_events(reason))
            for event in events:
                seq = self.base_index + len(self.frames)
                self._append_locked(format_sse_event(data_str=event.data_json, id=str(seq)))
            self.done = True
            self._cond.notify_all()

    async def replay(self, start_index: int) -> AsyncIterator[bytes]:
        """Yield buffered frames from ``start_index`` and tail until done.

        ``start_index`` is in logical event-id space (matches what was emitted
        on ``id:`` lines). If the caller's ``Last-Event-ID`` points before the
        buffer's current head (frames evicted under memory pressure), we
        replay from the head and the caller observes a gap.
        """
        idx = max(start_index, 0)
        while True:
            async with self._cond:
                head = self.base_index
                tail = head + len(self.frames)
                idx = max(idx, head)
                while idx >= tail and not self.done:
                    await self._cond.wait()
                    head = self.base_index
                    tail = head + len(self.frames)
                    idx = max(idx, head)
                snapshot = self.frames[idx - head :]
                finished = self.done
            for frame in snapshot:
                yield frame
            idx += len(snapshot)
            if finished and idx >= self.base_index + len(self.frames):
                return


# Process-local registry of background runs keyed by job_id, bounded by
# ``_MAX_BACKGROUND_RUNS`` (oldest evicted first). Re-attach reads this.
_MAX_BACKGROUND_RUNS = 100
# Per-run frame ceiling. Caps memory for a single long/verbose run so a
# token-streaming flow can't exhaust the process. 10k frames covers minutes
# of dense token streams with room to spare; beyond that we evict oldest.
_MAX_FRAMES_PER_BACKGROUND_RUN = 10_000
_BACKGROUND_RUNS: dict[str, _BackgroundRun] = {}
_WORKFLOW_CANCELLED_MESSAGE = "Workflow run cancelled."


async def _finalize_job_status(job_uuid: UUID, terminal_status: JobStatus) -> None:
    """Update job status to a terminal value, but never overwrite CANCELLED.

    ``stop_workflow`` sets the job to CANCELLED. The buffer task runs in
    parallel and reaches its ``finally`` block shortly after; if it
    unconditionally wrote COMPLETED/FAILED it would race with the cancellation
    and silently overwrite the user's stop intent. Re-read the row first and
    skip the update if a cancellation already landed.
    """
    job_service = get_job_service()
    try:
        job = await job_service.get_job_by_job_id(job_id=job_uuid)
    except Exception:  # noqa: BLE001
        job = None
    if job is not None and job.status == JobStatus.CANCELLED:
        return
    with contextlib.suppress(Exception):
        await job_service.update_job_status(
            job_uuid,
            terminal_status,
            finished_timestamp=True,
        )


async def _clear_background_run(job_id: str) -> None:
    """Pop the background run registry entry and wake any re-attach waiters.

    Used for true cleanup paths that should discard replay state, such as
    failed scheduling or test teardown. Cancellation normally finishes through
    the owning buffer task so it can append protocol-native terminal events
    before replay is marked done.
    """
    bg_run = _BACKGROUND_RUNS.pop(job_id, None)
    if bg_run is not None:
        await bg_run.finish()


async def _finish_cancelled_background_run(job_id: str) -> None:
    """Finish a stopped local run when no owner task is available to do it."""
    bg_run = _BACKGROUND_RUNS.get(job_id)
    if bg_run is None or bg_run.done:
        return
    if not bg_run.has_cancel_events:
        with contextlib.suppress(UnknownStreamProtocolError):
            adapter = get_stream_adapter(
                bg_run.stream_protocol,
                StreamAdapterContext(run_id=job_id, thread_id=job_id),
            )
            bg_run.set_cancel_events(adapter.cancel_events)
    await bg_run.finish_cancelled(_WORKFLOW_CANCELLED_MESSAGE)


async def _register_background_run(job_id: str, bg_run: _BackgroundRun) -> None:
    """Register a background run, evicting a completed entry when full.

    Prefer evicting the oldest *completed* run so a long-running job's
    re-attach handle survives. If every slot is still active, evict the
    oldest one anyway to keep the registry bounded, cancel its still-running
    buffer writer so it stops appending into a run no reader can find, and log
    a warning.
    """
    if len(_BACKGROUND_RUNS) >= _MAX_BACKGROUND_RUNS:
        evict_key = next(
            (key for key, run in _BACKGROUND_RUNS.items() if run.done),
            None,
        )
        evicted_running = False
        if evict_key is None:
            evict_key = next(iter(_BACKGROUND_RUNS))
            evicted_running = True
            logger.warning(
                "Background run registry full with no completed entries; "
                "evicting still-running job %s to make room for %s",
                evict_key,
                job_id,
            )
        _BACKGROUND_RUNS.pop(evict_key, None)
        if evicted_running:
            # Stop the orphaned buffer writer: without its registry entry no
            # reader can find it, but the coroutine keeps appending frames.
            # cancel_flow_build raises CancelledError into the build loop, which
            # runs the buffer's finally/finish_cancelled path.
            with contextlib.suppress(Exception):
                await _cancel_workflow_queue_job(evict_key)
    _BACKGROUND_RUNS[job_id] = bg_run


async def _buffer_background_run(
    *,
    bg_run: _BackgroundRun,
    flow: FlowRead,
    parsed: ParsedWorkflowRun,
    job_id: str,
    current_user: UserRead,
    stream_protocol: str,
) -> None:
    """Run a background flow, buffer its frames, and finalize job status.

    The adapter is resolved from ``stream_protocol`` so re-attach replays
    frames in the protocol the caller requested. Validation of
    ``stream_protocol`` happens at the route handler; this function still
    guards against ``UnknownStreamProtocolError`` because it runs as a
    fire-and-forget background coroutine. If adapter registration breaks
    between the route's check and this call (e.g. a registry mutation), we
    flip the job to FAILED and exit cleanly rather than dying silently and
    leaving the job stuck at QUEUED.

    The buffer's terminal-status detection keys off
    ``adapter.terminal_error_type``.
    """
    try:
        adapter = get_stream_adapter(
            stream_protocol,
            StreamAdapterContext(
                run_id=parsed.run_id or job_id,
                thread_id=parsed.session_id or str(flow.id),
            ),
        )
    except UnknownStreamProtocolError:
        # Fire-and-forget coroutine: do not raise, the route already returned.
        await bg_run.finish()
        job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
        await _finalize_job_status(job_uuid, JobStatus.FAILED)
        return

    bg_run.set_cancel_events(adapter.cancel_events)
    terminal_error_type = adapter.terminal_error_type
    fresh_background_tasks = BackgroundTasks()
    errored = False
    cancelled = False
    job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
    try:
        with contextlib.suppress(Exception):
            await get_job_service().update_job_status(job_uuid, JobStatus.IN_PROGRESS)
        async for frame, event_type in _stream_event_frames(
            adapter=adapter,
            flow_id=flow.id,
            flow_name=flow.name,
            background_tasks=fresh_background_tasks,
            parsed=parsed,
            current_user=current_user,
            # Build under the job id so the run's vertex builds are persisted
            # keyed by job_id and GET-status reconstruction can find them.
            run_id=job_id,
            track_job_status=False,
        ):
            if terminal_error_type is not None and event_type == terminal_error_type:
                errored = True
            await bg_run.append(frame)
    except asyncio.CancelledError:
        cancelled = True
        await bg_run.finish_cancelled(_WORKFLOW_CANCELLED_MESSAGE)
        raise
    finally:
        if not cancelled:
            await bg_run.finish()
        # ``generate_flow_events`` queues telemetry, tracing teardown, and
        # other callbacks on this ``BackgroundTasks`` instance. In FastAPI's
        # request lifecycle those run after the response is sent; the
        # background path has no response carrying them, so drain the queue
        # explicitly. Suppressed so a single failing telemetry callback does
        # not derail job-status finalization.
        with contextlib.suppress(Exception):
            await fresh_background_tasks()
        if not cancelled:
            # ``update_job_status`` queries the Job table by its UUID primary key;
            # passing the raw string would silently miss every row.
            await _finalize_job_status(job_uuid, JobStatus.FAILED if errored else JobStatus.COMPLETED)


async def execute_workflow_background(
    parsed: ParsedWorkflowRun,
    flow: FlowRead,
    job_id: JobId,
    current_user: UserRead,
    http_request: Request,  # noqa: ARG001
    stream_protocol: str,
) -> WorkflowJobResponse:
    """Run a workflow in the background, buffering protocol-native events for re-attach.

    A job row is created so ``GET /workflows`` and ``POST /workflows/stop`` keep
    working. The buffer task is scheduled through the queue service under
    ``job_id`` so ``/stop`` can revoke it. Graph construction happens inside
    the v1 build-vertex loop driven by ``_stream_event_frames`` with the
    adapter selected by ``stream_protocol``; re-attach replays the frames in
    that same protocol's wire shape.
    """
    try:
        flow_id_str = str(flow.id)
        job_id_str = str(job_id)

        await get_job_service().create_job(
            job_id=job_id,
            flow_id=flow_id_str,
            user_id=current_user.id,
        )

        bg_run = _BackgroundRun(user_id=str(current_user.id), stream_protocol=stream_protocol)
        await _register_background_run(job_id_str, bg_run)

        try:
            queue_service = get_queue_service()
            queue_service.create_queue(job_id_str)
            queue_service.start_job(
                job_id_str,
                _buffer_background_run(
                    bg_run=bg_run,
                    flow=flow,
                    parsed=parsed,
                    job_id=job_id_str,
                    current_user=current_user,
                    stream_protocol=stream_protocol,
                ),
            )
        except BaseException:
            # If queue creation or scheduling fails after the bg_run is
            # registered, the buffer would stay live with ``done=False`` and
            # any re-attach client would block on ``_cond.wait()`` forever
            # (the task that would call ``finish()`` was never scheduled).
            # Clear the registry, mark the job FAILED, then re-raise.
            await _clear_background_run(job_id_str)
            await _finalize_job_status(job_id, JobStatus.FAILED)
            raise
        return WorkflowJobResponse(job_id=job_id_str, flow_id=parsed.flow_id, status=JobStatus.QUEUED)

    except (WorkflowResourceError, WorkflowServiceUnavailableError, WorkflowQueueFullError):
        raise
    except MemoryError as exc:
        raise WorkflowResourceError from exc
