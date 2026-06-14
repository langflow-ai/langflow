from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Coroutine

from lfx.log.logger import logger

from langflow.events.event_manager import EventManager
from langflow.services.base import Service

if TYPE_CHECKING:
    from uuid import UUID

# Sentinel value written to Redis Streams to signal end-of-stream to consumers.
_STREAM_SENTINEL_DATA = b"__sentinel__"

# Shared Redis key prefix for job event streams. Producer (RedisJobQueueService) and
# consumer (RedisQueueWrapper) MUST agree on this — keep a single source of truth.
_STREAM_PREFIX = "langflow:queue:"
_OWNER_PREFIX = "langflow:owner:"
# Pub/Sub channel for cross-worker cancel signals. Any worker can publish here;
# the producer worker subscribes when the job starts and cancels the local task.
_CANCEL_CHANNEL_PREFIX = "langflow:cancel:"
# Activity heartbeat key written by polling and streaming responses. The
# polling watchdog scans these to detect abandoned builds (client gave up).
_ACTIVITY_PREFIX = "langflow:activity:"


class JobQueueNotFoundError(Exception):
    """Exception raised when a job queue is not found."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Job queue not found for job_id: {job_id}")


class JobQueueService(Service):
    """Asynchronous service for managing job-specific queues and their associated tasks.

    This service allows clients to:
      - Create dedicated asyncio queues for individual jobs.
      - Associate each queue with an EventManager, enabling event-driven handling.
      - Launch and manage asynchronous tasks that process these job queues.
      - Safely clean up resources by cancelling active tasks and emptying queues.
      - Automatically perform periodic cleanup of inactive or completed job queues.

    The cleanup process follows a two-phase approach:
      1. When a task is cancelled or fails, it is marked for cleanup by setting a timestamp
      2. The actual cleanup only occurs after CLEANUP_GRACE_PERIOD seconds have elapsed
         since the task was marked

    Attributes:
        name (str): Unique identifier for the service.
        _queues (dict[str, tuple[asyncio.Queue, EventManager, asyncio.Task | None, float | None]]):
            Dictionary mapping job IDs to a tuple containing:
              * The job's asyncio.Queue instance.
              * The associated EventManager instance.
              * The asyncio.Task processing the job (if any).
              * The cleanup timestamp (if any).
        _cleanup_task (asyncio.Task | None): Background task for periodic cleanup.
        _closed (bool): Flag indicating whether the service is currently active.
        CLEANUP_GRACE_PERIOD (int): Number of seconds to wait after a task is marked for cleanup
            before actually removing it. This grace period allows for:
              * Pending operations to complete
              * Related systems to finish their work
              * Inspection or recovery if needed
            Default is 300 seconds (5 minutes).

    Example:
        service = JobQueueService()
        await service.start()
        queue, event_manager = service.create_queue("job123")
        service.start_job("job123", some_async_coroutine())
        # Retrieve and use the queue data as needed
        data = service.get_queue_data("job123")
        await service.cleanup_job("job123")
        await service.stop()
    """

    name = "job_queue_service"

    def __init__(self) -> None:
        """Initialize the JobQueueService.

        Sets up the internal registry for job queues, initializes the cleanup task, and sets the service state
        to active.
        """
        self._queues: dict[str, tuple[asyncio.Queue, EventManager, asyncio.Task | None, float | None]] = {}
        self._job_owners: dict[str, UUID] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._closed = False
        self.ready = False
        self.CLEANUP_GRACE_PERIOD = 300  # 5 minutes before cleaning up marked tasks

    def is_started(self) -> bool:
        """Check if the JobQueueService has started.

        Returns:
            bool: True if the service has started, False otherwise.
        """
        return self._cleanup_task is not None

    @property
    def cross_worker_cancel_enabled(self) -> bool:
        """True when this backend can deliver cancels across worker processes.

        Callers using ``signal_cancel`` to reach a build owned by another
        worker must check this first: when False, ``signal_cancel`` exists but
        is a no-op (returns 0 without setting the persistent marker), so
        treating its return value as a successful cross-worker dispatch is
        misleading.
        """
        return False

    def set_ready(self) -> None:
        if not self.is_started():
            self.start()
        super().set_ready()

    def start(self) -> None:
        """Start the JobQueueService and begin the periodic cleanup routine.

        This method marks the service as active and launches a background task that
        periodically checks and cleans up job queues whose tasks have been completed or cancelled.
        """
        self._closed = False
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.debug("JobQueueService started: periodic cleanup task initiated.")

    async def stop(self) -> None:
        """Gracefully stop the JobQueueService by terminating background operations and cleaning up all resources.

        This coroutine performs the following steps:
            1. Marks the service as closed, preventing further job queue creation.
            2. Cancels the background periodic cleanup task and awaits its termination.
            3. Iterates over all registered job queues to clean up their resources—cancelling active tasks and
            clearing queued items.
        """
        self._closed = True
        if self._cleanup_task:
            self._cleanup_task.cancel()
            await asyncio.wait([self._cleanup_task])
            if not self._cleanup_task.cancelled():
                exc = self._cleanup_task.exception()
                if exc is not None:
                    raise exc

        # Clean up each registered job queue.
        for job_id in list(self._queues.keys()):
            await self.cleanup_job(job_id)
        await logger.adebug("JobQueueService stopped: all job queues have been cleaned up.")

    async def teardown(self) -> None:
        await self.stop()

    def metrics_snapshot(self) -> dict[str, Any]:
        """Return a read-only snapshot of queue metrics for ops/monitoring.

        Subclasses extend this dict with backend-specific fields (e.g.
        :class:`RedisJobQueueService` adds bridge / wrapper / cancel stats).
        Callers MUST NOT mutate the returned mapping — it is a fresh copy.
        """
        return {
            "backend": "memory",
            "active_jobs": len(self._queues),
        }

    def create_queue(self, job_id: str) -> tuple[asyncio.Queue, EventManager]:
        """Create and register a new queue along with its corresponding event manager for a job.

        Args:
            job_id (str): Unique identifier for the job.

        Returns:
            tuple[asyncio.Queue, EventManager]: A tuple containing:
                - The asyncio.Queue instance for handling the job's tasks or messages.
                - The EventManager instance for event handling tied to the queue.
        """
        if self._closed:
            msg = "Queue service is closed"
            raise RuntimeError(msg)

        existing_queue = self._queues.get(job_id)
        if existing_queue:
            msg = f"Queue for job_id {job_id} already exists"
            raise ValueError(msg)

        main_queue: asyncio.Queue = asyncio.Queue()
        event_manager: EventManager = self._create_default_event_manager(main_queue)

        # Register the queue without an active task.
        self._queues[job_id] = (main_queue, event_manager, None, None)
        logger.debug(f"Queue and event manager successfully created for job_id {job_id}")
        return main_queue, event_manager

    def start_job(self, job_id: str, task_coro: Coroutine) -> None:
        """Start an asynchronous task for a given job, replacing any existing active task.

        The method performs the following:
          - Verifies the presence of a registered queue for the job.
          - Cancels any currently running task associated with the job.
          - Launches a new asynchronous task using the provided coroutine.
          - Updates the internal registry with the new task.

        The coroutine is wrapped with :meth:`_guarded_task` so that any unhandled
        exception causes an ``on_error`` event to be emitted and the end-of-stream
        sentinel to be written before the task exits. This guarantees that
        cross-worker consumers can always distinguish a clean end from a crash —
        both paths terminate with the sentinel in the Redis Stream, but a crash
        will be preceded by an ``error`` event.

        Args:
            job_id (str): Unique identifier for the job.
            task_coro: A coroutine representing the job's asynchronous task.
        """
        if job_id not in self._queues:
            msg = f"No queue found for job_id {job_id}"
            logger.error(msg)
            raise ValueError(msg)

        if self._closed:
            msg = "Queue service is closed"
            logger.error(msg)
            raise RuntimeError(msg)

        main_queue, event_manager, existing_task, _ = self._queues[job_id]
        if existing_task and not existing_task.done():
            logger.debug(f"Existing task for job_id {job_id} detected; cancelling it.")
            existing_task.cancel()

        # Wrap the coroutine so that any crash emits on_error + sentinel before exit.
        task = asyncio.create_task(self._guarded_task(job_id, task_coro, event_manager, main_queue))
        self._queues[job_id] = (main_queue, event_manager, task, None)
        logger.debug(f"New task started for job_id {job_id}")

    @staticmethod
    async def _guarded_task(
        job_id: str,
        task_coro: Coroutine,
        event_manager: EventManager,
        main_queue: asyncio.Queue,
    ) -> None:
        """Run *task_coro* and guarantee the end-of-stream sentinel is written on crash.

        A well-behaved build coroutine (``generate_flow_events``) writes the sentinel
        itself after emitting ``on_end``. If the coroutine raises an unexpected
        exception before doing so, this wrapper:

        1. Emits an ``on_error`` event so consumers can distinguish a crash from a
           clean end — both cases deliver ``(None, None, ts)`` as the terminal item,
           but a crash is always preceded by an error event in the stream.
        2. Puts the raw ``(None, None, ts)`` sentinel so the bridge flushes and
           writes ``_STREAM_SENTINEL_DATA`` to the Redis Stream before cleanup
           deletes the key, preventing consumers from hanging indefinitely.

        ``asyncio.CancelledError`` is not caught here; the caller
        (``cancel_job`` / ``cancel_flow_build``) is responsible for user-initiated
        cancel paths and any backend-specific end-of-stream delivery.
        """
        try:
            await task_coro
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await logger.aerror(
                f"Unhandled exception in build task for job_id {job_id}: {exc}",
                exc_info=True,
            )
            # 1. Emit an error event so the stream carries the failure record.
            with contextlib.suppress(Exception):
                event_manager.on_error(data={"error": str(exc)})
            # 2. Write the sentinel so the bridge terminates and flushes to Redis.
            with contextlib.suppress(Exception):
                main_queue.put_nowait((None, None, time.time()))
            raise

    def get_queue_data(self, job_id: str) -> tuple[asyncio.Queue, EventManager, asyncio.Task | None, float | None]:
        """Retrieve the complete data structure associated with a job's queue.

        Args:
            job_id (str): Unique identifier for the job.

        Returns:
            tuple[asyncio.Queue, EventManager, asyncio.Task | None, float | None]:
                A tuple containing the job's main queue, its linked event manager, the associated task (if any),
                and the cleanup timestamp (if any).

        Raises:
            JobQueueNotFoundError: If the job_id is not found.
            RuntimeError: If the service is closed.
        """
        if self._closed:
            msg = f"Queue service is closed for job_id: {job_id}"
            raise RuntimeError(msg)

        try:
            return self._queues[job_id]
        except KeyError as exc:
            raise JobQueueNotFoundError(job_id) from exc

    async def register_job_owner(self, job_id: str, user_id: UUID) -> None:
        """Register the authenticated user who initiated a build job."""
        self._job_owners[job_id] = user_id

    async def get_job_owner(self, job_id: str) -> UUID | None:
        """Return the user ID that owns a job, or None if not tracked."""
        return self._job_owners.get(job_id)

    async def cleanup_job(self, job_id: str) -> None:
        """Clean up and release resources for a specific job.

        The cleanup process includes:
          1. Verifying if the job's queue is registered.
          2. Cancelling the running task (if active) and awaiting its termination.
          3. Clearing all items from the job's queue.
          4. Removing the job's entry from the internal registry.

        Args:
            job_id (str): Unique identifier for the job to be cleaned up.
        """
        if job_id not in self._queues:
            await logger.adebug(f"No queue found for job_id {job_id} during cleanup.")
            return

        await logger.adebug(f"Commencing cleanup for job_id {job_id}")
        main_queue, _event_manager, task, _ = self._queues[job_id]

        # Cancel the associated task if it is still running.
        if task and not task.done():
            await logger.adebug(f"Cancelling active task for job_id {job_id}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError as exc:
                # Check if this was a user-initiated cancellation (user called task.cancel())
                if task.cancelled():
                    # User-initiated cancellation so we explicitly called task.cancel() above
                    await logger.adebug(f"Task for job_id {job_id} was successfully cancelled.")
                    # Re-raise with user cancellation message code
                    exc.args = ("LANGFLOW_USER_CANCELLED",)
                    raise
                # System-initiated cancellation for other reasons
                await logger.adebug(f"Task for job_id {job_id} was cancelled by system.")
                exc.args = ("LANGFLOW_SYSTEM_CANCELLED",)
                raise
            except Exception as exc:
                await logger.aerror(f"Error in task for job_id {job_id} during cancellation: {exc}")
                raise
        await logger.adebug(f"Task cancellation complete for job_id {job_id}")

        # Clear the queue since we just cancelled the task or it has completed
        items_cleared = 0
        while not main_queue.empty():
            try:
                main_queue.get_nowait()
                items_cleared += 1
            except asyncio.QueueEmpty:
                break

        await logger.adebug(f"Removed {items_cleared} items from queue for job_id {job_id}")
        # Remove the job entry from the registry
        self._queues.pop(job_id, None)
        self._job_owners.pop(job_id, None)
        await logger.adebug(f"Cleanup successful for job_id {job_id}: resources have been released.")

    async def cancel_job(self, job_id: str) -> None:
        """Cancel an active job and release its resources.

        The in-memory backend can use the normal cleanup path directly. Backends
        with cross-worker consumers can override this hook when cancellation needs
        extra coordination before resource teardown.
        """
        await self.cleanup_job(job_id)

    async def _periodic_cleanup(self) -> None:
        """Execute a periodic task that cleans up completed or cancelled job queues.

        This internal coroutine continuously:
          - Sleeps for a fixed interval (60 seconds).
          - Initiates the cleanup of job queues by calling _cleanup_old_queues.
          - Monitors and logs any exceptions during the cleanup cycle.

        The loop terminates when the service is marked as closed.
        """
        while not self._closed:
            try:
                await asyncio.sleep(60)  # Sleep for 60 seconds before next cleanup attempt.
                await self._cleanup_old_queues()
            except asyncio.CancelledError:
                await logger.adebug("Periodic cleanup task received cancellation signal.")
                raise
            except Exception as exc:  # noqa: BLE001
                await logger.aerror(f"Exception encountered during periodic cleanup: {exc}")

    async def _cleanup_old_queues(self) -> None:
        """Scan all registered job queues and clean up those with completed, failed or orphaned tasks."""
        current_time = asyncio.get_running_loop().time()

        for job_id in list(self._queues.keys()):
            _, _, task, cleanup_time = self._queues[job_id]

            should_cleanup = False
            cleanup_reason = ""

            # Case 1: Orphaned queue (created but task never started)
            if task is None:
                should_cleanup = True
                cleanup_reason = "Orphaned queue (no task associated)"
            # Case 2: Task has finished (Success, Failure, or Cancellation)
            elif task.done():
                should_cleanup = True
                if task.cancelled():
                    cleanup_reason = "Task cancelled"
                elif task.exception() is not None:
                    # Don't try to log the exception yet as it might be handled elsewhere;
                    # the grace period allows other systems to inspect it if needed.
                    cleanup_reason = "Task failed with exception"
                else:
                    cleanup_reason = "Task completed successfully"

            if should_cleanup:
                if cleanup_time is None:
                    # Mark for cleanup by setting the timestamp
                    self._queues[job_id] = (
                        self._queues[job_id][0],
                        self._queues[job_id][1],
                        self._queues[job_id][2],
                        current_time,
                    )
                    await logger.adebug(f"Job queue for job_id {job_id} marked for cleanup - {cleanup_reason}")
                elif current_time - cleanup_time >= self.CLEANUP_GRACE_PERIOD:
                    # Enough time has passed, perform the actual cleanup
                    await logger.adebug(f"Cleaning up job_id {job_id} after grace period due to: {cleanup_reason}")
                    await self.cleanup_job(job_id)

    def _create_default_event_manager(self, queue: asyncio.Queue) -> EventManager:
        """Creates the default event manager with predefined events.

        Args:
            queue (asyncio.Queue): The queue to be associated with the event manager.

        Returns:
            EventManager: The configured EventManager instance.
        """
        manager = EventManager(queue)
        # Registering predefined events
        event_names_types = [
            ("on_token", "token"),
            ("on_vertices_sorted", "vertices_sorted"),
            ("on_error", "error"),
            ("on_end", "end"),
            ("on_message", "add_message"),
            ("on_remove_message", "remove_message"),
            ("on_end_vertex", "end_vertex"),
            ("on_build_start", "build_start"),
            ("on_build_end", "build_end"),
            ("on_log", "log"),
        ]
        for name, event_type in event_names_types:
            manager.register_event(name, event_type)
        return manager


class RedisQueueWrapper:
    """Consumer-side asyncio.Queue interface backed by a Redis Stream.

    Created by :class:`RedisJobQueueService` when :meth:`get_queue_data` is called
    for a job that was started on a different worker process. A background
    ``_fill_task`` reads from the Redis Stream and populates a local buffer so that
    the rest of ``build.py`` can use the familiar ``asyncio.Queue`` interface.

    Stream protocol
    ---------------
    * Normal event  →  ``XADD key * event_id <str> data <bytes> ts <float>``
    * End-of-stream →  ``XADD key * event_id __sentinel__ data __sentinel__ ts <float>``

    Self-termination
    ----------------
    The fill task exits when it:
    1. Receives the end-of-stream sentinel from the stream, **or**
    2. Detects that the stream key no longer exists (job was cleaned up).
    In both cases it puts ``(None, None, timestamp)`` into the local buffer so
    that consumers in ``build.py`` see the normal end-of-stream signal.
    """

    STREAM_PREFIX = _STREAM_PREFIX

    # Tunables for the background fill task. Kept as class-level constants so
    # subclasses or tests can override without touching the loop body.
    _XREAD_BLOCK_MS = 1000  # how long XREAD blocks waiting for new entries
    _XREAD_BATCH_COUNT = 100  # max entries fetched per XREAD call
    _READ_ERROR_BACKOFF_S = 0.5  # backoff after a transient XREAD failure
    # Default grace period. Overridable per-instance via the constructor so the
    # value can be driven from settings (LANGFLOW_REDIS_QUEUE_STARTUP_GRACE_S).
    # Protects against the early-poll race where the consumer wrapper is created
    # before the producer worker has issued its first XADD.
    _STARTUP_GRACE_S = 30.0
    # Hard cap on in-process buffered events per consumer. Bounds memory when a
    # slow client falls behind a fast producer; without it, the buffer can grow
    # without limit until the consumer drains it.
    _BUFFER_MAXSIZE = 10_000

    def __init__(self, job_id: str, client: Any, ttl: int, startup_grace_s: float | None = None) -> None:
        self._job_id = job_id
        self._client = client
        self._ttl = ttl
        # Allow callers to override the class-level grace period (driven by settings).
        if startup_grace_s is not None:
            self._STARTUP_GRACE_S = startup_grace_s
        self._buffer: asyncio.Queue = asyncio.Queue(maxsize=self._BUFFER_MAXSIZE)
        self._last_id = "0-0"  # read from the beginning of the stream
        # Flips to True the first time XREAD returns messages for this stream.
        # Until then, "stream key does not exist" is NOT treated as end-of-stream
        # — it just means the producer hasn't written its first event yet.
        self._observed_stream: bool = False
        self._created_at: float = time.monotonic()
        # Flips to True after the very first XREAD call returns (regardless of
        # whether it had results). empty() returns False until this flag is set
        # so that the while-not-empty drain loop in build.py suspends on get()
        # and lets the fill task populate the buffer before the loop exits.
        self._first_read_done: bool = False
        self._fill_task: asyncio.Task = asyncio.create_task(self._fill_from_redis())
        # Defense-in-depth: if the fill task is cancelled or crashes with an
        # unhandled exception, deliver an end-of-stream sentinel into the buffer
        # so consumers waiting on ``await get()`` are unblocked. The clean exit
        # paths inside ``_fill_from_redis`` already put the sentinel themselves;
        # this callback only fires when those paths are bypassed.
        self._fill_task.add_done_callback(self._on_fill_done)

    def _on_fill_done(self, task: asyncio.Task) -> None:
        """Ensure the consumer is unblocked if the fill task exits unexpectedly.

        A clean exit (sentinel received, stream cleaned up, grace exhausted)
        already puts the sentinel into the buffer. Cancellation and unhandled
        exceptions skip that path — this callback catches both gaps so the
        consumer's ``await queue.get()`` never blocks forever.

        Done callbacks run synchronously, so we use the non-blocking
        ``put_nowait``. If the buffer happens to be at capacity (slow consumer
        + bounded buffer), evict the oldest item to make room: losing one event
        is strictly preferable to leaving the consumer stuck.
        """
        if not task.cancelled() and task.exception() is None:
            # Clean exit: _fill_from_redis already put the sentinel.
            return
        if not task.cancelled():
            exc = task.exception()
            logger.error(
                f"RedisQueueWrapper fill task raised for job {self._job_id}: {exc!r} "
                "— delivering end-of-stream sentinel so the consumer is not left hanging."
            )
        if self._buffer.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._buffer.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            self._buffer.put_nowait((None, None, time.time()))

    @property
    def _stream_key(self) -> str:
        return f"{self.STREAM_PREFIX}{self._job_id}"

    async def _fill_from_redis(self) -> None:
        """Read events from the Redis Stream and forward them to the local buffer."""
        _error_start: float | None = None
        try:
            while True:
                try:
                    results = await self._client.xread(
                        {self._stream_key: self._last_id},
                        block=self._XREAD_BLOCK_MS,
                        count=self._XREAD_BATCH_COUNT,
                    )
                except Exception as exc:  # noqa: BLE001
                    now = time.monotonic()
                    if _error_start is None:
                        _error_start = now
                    elapsed = now - _error_start
                    await logger.awarning(
                        f"RedisQueueWrapper read error for {self._job_id} (elapsed {elapsed:.1f}s): {exc}"
                    )
                    if elapsed >= self._STARTUP_GRACE_S:
                        await logger.aerror(
                            f"RedisQueueWrapper: persistent Redis error for {self._job_id} "
                            f"after {elapsed:.1f}s; delivering end-of-stream sentinel."
                        )
                        await self._buffer.put((None, None, time.time()))
                        return
                    await asyncio.sleep(self._READ_ERROR_BACKOFF_S)
                    continue
                _error_start = None  # reset on successful XREAD

                self._first_read_done = True
                if results:
                    self._observed_stream = True
                    for _, messages in results:
                        for msg_id, fields in messages:
                            data = fields.get(b"data")
                            ts = float(fields.get(b"ts", b"0") or b"0")
                            if data == _STREAM_SENTINEL_DATA:
                                await self._buffer.put((None, None, ts))
                                self._last_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                                return
                            event_id = (fields.get(b"event_id") or b"").decode()
                            await self._buffer.put((event_id, data, ts))
                            # Advance cursor only after the item is safely in the buffer.
                            # Advancing before the await would skip this message on cancellation.
                            self._last_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                # No results within the block timeout.
                elif not self._observed_stream:
                    # Stream hasn't appeared yet — the producer may not have issued its
                    # first XADD (early-poll race between workers). Keep blocking until
                    # the startup grace period expires to avoid a false end-of-stream.
                    elapsed = time.monotonic() - self._created_at
                    if elapsed > self._STARTUP_GRACE_S:
                        await logger.awarning(
                            f"RedisQueueWrapper: stream for {self._job_id} never appeared "
                            f"after {elapsed:.1f}s; treating as end-of-stream."
                        )
                        await self._buffer.put((None, None, time.time()))
                        return
                    # Otherwise keep looping — next XREAD will block again.
                elif not await self._client.exists(self._stream_key):
                    # Stream was observed before and the key is now gone — the job
                    # was cleaned up on the producer side; signal end-of-stream.
                    await self._buffer.put((None, None, time.time()))
                    return
        except asyncio.CancelledError:
            return

    # ------------------------------------------------------------------
    # asyncio.Queue-compatible interface used by build.py
    # ------------------------------------------------------------------

    def empty(self) -> bool:
        # Before the first XREAD completes the local buffer is empty even if
        # Redis already has events queued. Returning False here causes the
        # while-not-empty drain loop in build.py to suspend on await get(),
        # which yields to the event loop so the fill task can run its first
        # XREAD and populate the buffer. After warm-up, delegate to the
        # actual buffer state.
        return self._first_read_done and self._buffer.empty()

    async def get(self):
        return await self._buffer.get()

    def get_nowait(self):
        return self._buffer.get_nowait()

    def put_nowait(self, item) -> None:
        """No-op: this wrapper is consumer-only; producers write via the bridge."""

    def fill_done(self) -> bool:
        """Return True if the background fill task has finished."""
        return self._fill_task.done()

    async def cancel(self) -> None:
        """Cancel the background fill task."""
        if not self._fill_task.done():
            self._fill_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._fill_task

    async def finish_with_sentinel(self) -> None:
        """Stop the fill task and wake active consumers with an end-of-stream item.

        Mirrors ``_on_fill_done``: when the buffer is full because the consumer
        is gone or slow, evict the oldest item and ``put_nowait`` the sentinel
        instead of awaiting. Losing one buffered event is strictly preferable
        to a teardown that hangs forever on a closed-out consumer.
        """
        if not self._fill_task.done():
            self._fill_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._fill_task
        if self._buffer.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._buffer.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            self._buffer.put_nowait((None, None, time.time()))


class RedisJobQueueService(JobQueueService):
    """Redis-backed job queue service for multi-worker deployments.

    Replaces the in-memory :class:`JobQueueService` with one that uses Redis
    Streams as a shared event bus, so that build events published by the worker
    that started the job can be consumed by any other worker that receives the
    subsequent HTTP poll / streaming request.

    Architecture
    ------------
    Producer (build worker)::

        EventManager → local asyncio.Queue → bridge coroutine → Redis Stream

    Consumer (poll worker)::

        Redis Stream → RedisQueueWrapper fill task → local buffer → HTTP response

    Configuration
    -------------
    Set ``LANGFLOW_JOB_QUEUE_TYPE=redis`` and, optionally:

    * ``LANGFLOW_REDIS_QUEUE_DB`` (default ``1``, separate from cache DB ``0``)
    * ``LANGFLOW_REDIS_QUEUE_URL`` (full URL, overrides host/port/db)
    * ``LANGFLOW_REDIS_QUEUE_HOST`` / ``LANGFLOW_REDIS_QUEUE_PORT``

    Cross-worker cancel
    -------------------
    When ``cancel_channel_enabled=True`` (the default), the service runs a
    single Redis PSUBSCRIBE dispatcher per worker over the pattern
    ``langflow:cancel:*``. Any worker can publish a cancel signal via
    :meth:`signal_cancel`; the worker that owns the job (i.e. has an entry in
    ``self._queues``) cancels the local task, flushes a sentinel through the
    bridge so cross-worker consumers see end-of-stream promptly, and triggers
    fast cleanup of the Redis stream + owner keys.

    Note: callers of :meth:`signal_cancel` are responsible for any
    authorization checks. The HTTP cancel endpoint already verifies job
    ownership before calling through; programmatic callers must do the same.

    Cross-worker passive disconnect is also wired through: when a client closes
    its streaming connection on a worker that doesn't own the job, the streaming
    response's disconnect handler calls :meth:`signal_cancel` so the owning
    worker stops emitting events promptly instead of running to natural
    completion. See ``langflow.api.build.create_flow_response``.
    """

    STREAM_PREFIX = _STREAM_PREFIX
    OWNER_PREFIX = _OWNER_PREFIX
    CANCEL_CHANNEL_PREFIX = _CANCEL_CHANNEL_PREFIX
    ACTIVITY_PREFIX = _ACTIVITY_PREFIX

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 1,
        url: str | None = None,
        ttl: int = 3600,
        startup_grace_s: float = 30.0,
        cancel_marker_ttl: int = 60,
        polling_stale_threshold_s: float = 90.0,
        polling_watchdog_interval_s: float = 15.0,
        *,
        cancel_channel_enabled: bool = True,
    ) -> None:
        super().__init__()
        self._redis_host = host
        self._redis_port = port
        self._redis_db = db
        self._redis_url = url
        self._ttl = ttl
        self._startup_grace_s = startup_grace_s
        self._cancel_channel_enabled = cancel_channel_enabled
        self._cancel_marker_ttl = cancel_marker_ttl
        self._polling_stale_threshold_s = polling_stale_threshold_s
        self._polling_watchdog_interval_s = polling_watchdog_interval_s
        self._client: Any = None
        self._connection_check_task: asyncio.Task | None = None
        self._bridge_tasks: dict[str, asyncio.Task] = {}
        self._consumer_wrappers: dict[str, RedisQueueWrapper] = {}
        self._owner_refresh_tasks: dict[str, asyncio.Task] = {}
        # Single PSUBSCRIBE task per worker — handles every job's cancel channel.
        # Replaces the previous per-job subscriber so connection-pool usage is O(1)
        # in active job count.
        self._cancel_dispatcher_task: asyncio.Task | None = None
        # Periodic loop that publishes cancel for owned jobs whose activity
        # heartbeat has gone stale (client abandoned a polling build). Started
        # only when polling_stale_threshold_s > 0.
        self._polling_watchdog_task: asyncio.Task | None = None
        # Strong references for short-lived fire-and-forget tasks (marker check,
        # post-cancel cleanup). Each task removes itself on completion. Without
        # this, asyncio is free to GC the task while it's still scheduled.
        self._background_tasks: set[asyncio.Task] = set()
        # Counters used for observability — bumped on each cancel event.
        self._cancel_stats: dict[str, int] = {
            "published": 0,
            "marker_hit": 0,
            "dispatched_owned": 0,
            "dispatched_foreign": 0,
            "publish_errors": 0,
            "dispatcher_reconnects": 0,
            "dispatcher_internal_errors": 0,
            "polling_watchdog_kills": 0,
            "activity_touch_errors": 0,
            "activity_get_errors": 0,
            "activity_parse_errors": 0,
        }
        # Monotonic timestamp of when each owned job entered start_job. Used
        # by the polling watchdog to grant a brand-new job a grace window
        # before reclaiming it if the activity key hasn't been written yet.
        self._job_start_times: dict[str, float] = {}

    @property
    def cross_worker_cancel_enabled(self) -> bool:
        """Reflects ``cancel_channel_enabled`` for the Redis backend.

        When False, ``signal_cancel`` short-circuits to a 0 return without
        setting the marker, so cross-worker delivery is genuinely unavailable.
        """
        return self._cancel_channel_enabled

    def _stream_key(self, job_id: str) -> str:
        return f"{self.STREAM_PREFIX}{job_id}"

    def _owner_key(self, job_id: str) -> str:
        return f"{self.OWNER_PREFIX}{job_id}"

    def _cancel_channel(self, job_id: str) -> str:
        return f"{self.CANCEL_CHANNEL_PREFIX}{job_id}"

    def _spawn_background(self, coro) -> asyncio.Task:
        """Schedule a fire-and-forget task with a strong reference until completion.

        Without holding a strong reference, asyncio is free to garbage-collect a
        scheduled task before it runs. Each task removes itself on completion.
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    def start(self) -> None:
        """Create the Redis client, start the periodic cleanup, and run one cancel dispatcher."""
        from redis.asyncio import StrictRedis

        if self._redis_url:
            self._client = StrictRedis.from_url(self._redis_url)
        else:
            self._client = StrictRedis(host=self._redis_host, port=self._redis_port, db=self._redis_db)
        super().start()
        # Schedule a connectivity check so startup logs a clear error if Redis is unreachable.
        self._connection_check_task = asyncio.create_task(self._check_connection())
        # One PSUBSCRIBE per worker handles every job's cancel channel — bounded
        # connection-pool usage regardless of how many jobs are active.
        if self._cancel_channel_enabled:
            self._cancel_dispatcher_task = asyncio.create_task(self._run_cancel_dispatcher())
        # Polling watchdog: reclaim owned jobs whose activity heartbeat has gone
        # stale (client abandoned a polling build). Runs independently of the
        # pub/sub cancel channel — it uses only local state and _handle_cancel
        # directly, so disabling cancel_channel_enabled must not silence it.
        # Disabled entirely when threshold <= 0.
        if self._polling_stale_threshold_s > 0:
            self._polling_watchdog_task = asyncio.create_task(self._run_polling_watchdog())
        logger.debug("RedisJobQueueService started.")

    async def _check_connection(self) -> None:
        """Ping Redis and log a prominent error if the connection is unavailable."""
        try:
            await self._client.ping()
            await logger.adebug("RedisJobQueueService: Redis connection OK.")
        except Exception as exc:  # noqa: BLE001
            await logger.aerror(
                f"RedisJobQueueService: cannot reach Redis at "
                f"{self._redis_url or f'{self._redis_host}:{self._redis_port} db={self._redis_db}'} — {exc}. "
                "Build events will NOT be delivered. "
                "Set LANGFLOW_JOB_QUEUE_TYPE=asyncio or start Redis before running Langflow."
            )

    async def stop(self) -> None:
        """Stop the service, cancel all background tasks, and close the Redis client."""
        if self._connection_check_task and not self._connection_check_task.done():
            self._connection_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._connection_check_task
        self._connection_check_task = None

        if self._cancel_dispatcher_task and not self._cancel_dispatcher_task.done():
            self._cancel_dispatcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cancel_dispatcher_task
        self._cancel_dispatcher_task = None

        if self._polling_watchdog_task and not self._polling_watchdog_task.done():
            self._polling_watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._polling_watchdog_task
        self._polling_watchdog_task = None

        # Wait briefly for any fire-and-forget background tasks (marker checks,
        # post-cancel cleanups) so they don't leak across stop boundaries.
        for refresh_task in list(self._owner_refresh_tasks.values()):
            if not refresh_task.done():
                refresh_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await refresh_task
        self._owner_refresh_tasks.clear()

        for bg in list(self._background_tasks):
            if not bg.done():
                bg.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await bg
        self._background_tasks.clear()

        for bridge in list(self._bridge_tasks.values()):
            if not bridge.done():
                bridge.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await bridge
        self._bridge_tasks.clear()
        for wrapper in list(self._consumer_wrappers.values()):
            await wrapper.cancel()
        self._consumer_wrappers.clear()
        await super().stop()
        if self._client:
            await self._client.aclose()
            self._client = None
        await logger.adebug("RedisJobQueueService stopped.")

    def create_queue(self, job_id: str) -> tuple[asyncio.Queue, EventManager]:
        """Create a local queue + EventManager and start the producer bridge to Redis."""
        local_queue, event_manager = super().create_queue(job_id)
        bridge = asyncio.create_task(self._bridge_to_redis(job_id, local_queue))
        self._bridge_tasks[job_id] = bridge
        return local_queue, event_manager

    # Refresh the stream TTL on the first event, then every _TTL_REFRESH_EVENTS
    # events *or* every _TTL_REFRESH_SECS seconds, whichever comes first.
    # Calling expire() on every XADD doubles Redis round-trips and caps
    # single-job throughput; periodic refresh preserves semantics at ~1/100 the cost.
    _TTL_REFRESH_EVENTS = 100
    _TTL_REFRESH_SECS = 30.0

    async def _bridge_to_redis(self, job_id: str, local_queue: asyncio.Queue) -> None:
        """Drain the local queue and publish each event to the Redis Stream.

        Items are read from the local asyncio.Queue (written by EventManager) and
        forwarded to a Redis Stream via XADD so that any worker can consume them.
        If Redis is temporarily unavailable the item is re-queued and the bridge
        backs off before retrying, preventing event loss.
        """
        stream_key = self._stream_key(job_id)
        _max_retry_delay = 4.0
        _retry_delay = 0.1
        in_flight_item = None
        published = False
        event_count = 0
        last_ttl_refresh = time.monotonic()
        try:
            while True:
                item = await local_queue.get()
                in_flight_item = item
                published = False
                event_id, data, ts = item
                is_sentinel = data is None
                fields = (
                    {"event_id": "__sentinel__", "data": _STREAM_SENTINEL_DATA, "ts": str(ts)}
                    if is_sentinel
                    else {"event_id": event_id or "", "data": data, "ts": str(ts)}
                )
                # Refresh TTL on first event, every N events, every M seconds, or on sentinel.
                now = time.monotonic()
                needs_ttl_refresh = (
                    event_count == 0
                    or event_count % self._TTL_REFRESH_EVENTS == 0
                    or (now - last_ttl_refresh) >= self._TTL_REFRESH_SECS
                    or is_sentinel
                )
                while True:
                    try:
                        if not published:
                            await self._client.xadd(stream_key, fields, maxlen=10_000, approximate=True)
                            published = True
                        if needs_ttl_refresh:
                            await self._client.expire(stream_key, self._ttl)
                            last_ttl_refresh = time.monotonic()
                        in_flight_item = None
                        _retry_delay = 0.1
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:  # noqa: BLE001
                        await logger.awarning(
                            f"Bridge XADD failed for job_id {job_id} (retrying in {_retry_delay}s): {exc}"
                        )
                        await asyncio.sleep(_retry_delay)
                        _retry_delay = min(_retry_delay * 2, _max_retry_delay)
                event_count += 1
                if is_sentinel:
                    return
        except asyncio.CancelledError:
            if in_flight_item is not None and not published:
                local_queue.put_nowait(in_flight_item)
            return

    def _get_consumer_wrapper(self, job_id: str) -> RedisQueueWrapper:
        """Return the cached Redis stream consumer for a job, creating it if needed."""
        wrapper = self._consumer_wrappers.get(job_id)
        if wrapper is None:
            wrapper = RedisQueueWrapper(
                job_id,
                self._client,
                self._ttl,
                startup_grace_s=self._startup_grace_s,
            )
            self._consumer_wrappers[job_id] = wrapper
        return wrapper

    # Persistent marker that :meth:`signal_cancel` sets in addition to publishing.
    # Closes the race where a cancel signal is sent before the worker's dispatcher
    # finishes PSUBSCRIBE (or before this worker has even started the job). On
    # ``start_job`` the worker checks the marker; if present, fires cancel immediately.
    _CANCEL_MARKER_PREFIX = "langflow:cancel-marker:"

    def _cancel_marker_key(self, job_id: str) -> str:
        return f"{self._CANCEL_MARKER_PREFIX}{job_id}"

    def start_job(self, job_id: str, task_coro) -> None:  # type: ignore[override]
        """Start the build task, then check for any pre-arrived cancel marker."""
        # Record start time BEFORE super().start_job() so the watchdog never
        # sees the job in self._queues without a corresponding start timestamp.
        self._job_start_times[job_id] = time.monotonic()
        super().start_job(job_id, task_coro)
        if job_id in self._job_owners:
            self._ensure_owner_refresh_task(job_id)
        if not self._cancel_channel_enabled or self._client is None:
            return
        # Initialize the activity heartbeat so the watchdog gives clients the
        # configured threshold to make first contact before reclaiming the job.
        self._spawn_background(self.touch_activity(job_id))
        # Cancel may have been signaled before we registered this job_id. Check
        # the persistent marker in a background task to avoid making start_job async.
        self._spawn_background(self._check_pending_cancel_marker(job_id))

    def _activity_key(self, job_id: str) -> str:
        return f"{self.ACTIVITY_PREFIX}{job_id}"

    async def touch_activity(self, job_id: str) -> None:
        """Refresh the activity heartbeat for *job_id*.

        Called by polling and streaming responses to signal "client still here".
        The polling watchdog scans these keys to detect abandoned builds.

        TTL is set to 4x the stale threshold (min 60s) so the activity key
        outlives a single dropped touch without the watchdog misclassifying
        the job as abandoned — Redis keeps the value around long enough for
        the next successful refresh to land. Errors here are non-fatal but
        observable via :attr:`_cancel_stats` (``activity_touch_errors``);
        sustained heartbeat failure combined with the start-time grace window
        in :meth:`_run_polling_watchdog` keeps an in-flight build alive even
        through a brief Redis outage.
        """
        if self._client is None or self._polling_stale_threshold_s <= 0:
            return
        ttl = max(int(self._polling_stale_threshold_s * 4), 60)
        try:
            await self._client.set(self._activity_key(job_id), str(time.time()), ex=ttl)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._cancel_stats["activity_touch_errors"] += 1
            await logger.adebug(f"touch_activity SET failed for {job_id}: {exc}")

    def _owner_refresh_interval_s(self) -> float:
        """Return the owner-key refresh cadence for active Redis jobs."""
        return max(min(self._ttl / 2, 30.0), 0.1)

    async def _set_owner_key(self, job_id: str, user_id: UUID) -> None:
        if self._client:
            await self._client.set(self._owner_key(job_id), str(user_id), ex=self._ttl)

    def _ensure_owner_refresh_task(self, job_id: str) -> None:
        task = self._owner_refresh_tasks.get(job_id)
        if task is None or task.done():
            self._owner_refresh_tasks[job_id] = asyncio.create_task(self._refresh_owner_key_until_done(job_id))

    async def _refresh_owner_key_until_done(self, job_id: str) -> None:
        """Keep the Redis owner key alive while this worker still owns the job."""
        current_task = asyncio.current_task()
        try:
            while not self._closed and job_id in self._queues:
                user_id = self._job_owners.get(job_id)
                if user_id is not None and self._client is not None:
                    try:
                        await self._set_owner_key(job_id, user_id)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:  # noqa: BLE001
                        await logger.adebug(f"owner key refresh failed for {job_id}: {exc}")
                await asyncio.sleep(self._owner_refresh_interval_s())
        finally:
            if self._owner_refresh_tasks.get(job_id) is current_task:
                self._owner_refresh_tasks.pop(job_id, None)

    async def _check_pending_cancel_marker(self, job_id: str) -> None:
        """Race-safety check: if a cancel marker exists, fire it immediately."""
        marker_key = self._cancel_marker_key(job_id)
        try:
            if await self._client.exists(marker_key):
                await self._client.delete(marker_key)
                self._cancel_stats["marker_hit"] += 1
                await self._handle_cancel(job_id, source="marker")
        except Exception as exc:  # noqa: BLE001
            await logger.awarning(f"Pending cancel marker check failed for {job_id}: {exc}")

    async def _run_polling_watchdog(self) -> None:
        """Periodically reclaim owned jobs whose activity heartbeat has gone stale.

        Each tick scans :attr:`_queues` (jobs this worker owns), filters to
        jobs that have a registered owner (i.e. user-facing flow builds that
        expect client polling/streaming), and pulls their activity timestamp
        from Redis. Missing-or-older-than :attr:`_polling_stale_threshold_s`
        means the client gave up.

        **Why the owner filter:** The :class:`TaskService` also uses
        :meth:`start_job` for server-internal tasks that have no polling client
        and never call :meth:`touch_activity`. Without the filter, every such
        task would trip the start-time fallback at the threshold and get
        cancelled mid-flight if it ran longer than the threshold — even though
        no client was ever waiting on it. Registered ownership is the
        existing signal for "user-facing build with an expected client", so
        scope the watchdog to that set.

        Brand-new jobs are protected by a start-time grace window: if the
        activity key is missing (e.g. the background ``touch_activity`` from
        ``start_job`` hasn't completed yet, or Redis was briefly unreachable),
        the watchdog skips the kill until ``time - job_start >= threshold``.
        Without this, a slow first SET could nuke an active build the moment
        its first watchdog tick fires.

        Cancellation goes through :meth:`_handle_cancel` directly rather than
        ``signal_cancel`` for owned jobs — there is no need to round-trip
        through pubsub when this worker already holds the cancel target, and
        bypassing the wire path keeps the ``cancel_stats["published"]``
        counter honest as a count of *external* cancels only.
        """
        interval = max(self._polling_watchdog_interval_s, 0.05)
        threshold = self._polling_stale_threshold_s
        while True:
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return
            if self._closed or self._client is None:
                continue
            now = time.time()
            now_mono = time.monotonic()
            # Iterate a snapshot so concurrent inserts don't disturb the scan.
            for job_id in list(self._queues.keys()):
                # Only watch jobs with a registered owner — TaskService and
                # other server-internal callers use start_job without
                # registering ownership, and they never refresh activity
                # heartbeats. See the docstring for rationale.
                if job_id not in self._job_owners:
                    continue
                try:
                    raw = await self._client.get(self._activity_key(job_id))
                except Exception as exc:  # noqa: BLE001
                    self._cancel_stats["activity_get_errors"] += 1
                    await logger.adebug(f"polling watchdog: GET failed for {job_id}: {exc}")
                    continue
                # Default to "infinitely stale" so a missed elif below cannot
                # leave `last` unbound; the if-branches narrow this down.
                last = 0.0
                if raw is None:
                    # Activity key not in Redis. Could be a brand-new job whose
                    # background touch hasn't landed yet, or a touch_activity
                    # failure (counter bumped elsewhere). Respect the start-time
                    # grace window before reclaiming.
                    start_ts = self._job_start_times.get(job_id)
                    if start_ts is None or (now_mono - start_ts) < threshold:
                        continue
                else:
                    try:
                        last = float(raw.decode() if isinstance(raw, bytes) else raw)
                    except (ValueError, TypeError) as exc:
                        self._cancel_stats["activity_parse_errors"] += 1
                        await logger.awarning(
                            f"polling watchdog: ignoring malformed activity value for {job_id}: {exc}"
                        )
                        continue
                age = now - last if last > 0 else float("inf")
                if age <= threshold:
                    continue
                # Stale → cancel this job. Local cancel on owned jobs skips the
                # pubsub round-trip and stays correct even during a dispatcher
                # reconnect window.
                self._cancel_stats["polling_watchdog_kills"] += 1
                await logger.ainfo(f"polling watchdog: reclaiming abandoned job {job_id} (age={age:.1f}s)")
                await self._handle_cancel(job_id, source="watchdog")
                with contextlib.suppress(Exception):
                    await self._client.delete(self._activity_key(job_id))

    # Reconnect tunables — class-level so tests can override without patching the loop.
    _DISPATCHER_RECONNECT_INITIAL_BACKOFF_S = 0.5
    _DISPATCHER_RECONNECT_MAX_BACKOFF_S = 30.0

    async def _run_cancel_dispatcher(self) -> None:
        """PSUBSCRIBE loop with auto-reconnect.

        The dispatcher is the single point of cross-worker cancel delivery for
        this worker. If the pubsub connection dies (Redis restart, network
        blip, broker timeout), we MUST reconnect — otherwise the worker becomes
        silently blind to cancels until restart.

        Strategy:
        * Each iteration of the outer loop opens a fresh pubsub.
        * On successful PSUBSCRIBE the backoff resets.
        * Any non-cancel exception is logged at warning, backoff doubles up to
          ``_DISPATCHER_RECONNECT_MAX_BACKOFF_S``, and we retry.
        * redis-py may also reconnect the active pubsub connection internally;
          the connection callback below records those transparent reconnects.
        * ``asyncio.CancelledError`` (service stop) breaks out cleanly.
        """
        pattern = f"{self.CANCEL_CHANNEL_PREFIX}*"
        backoff = self._DISPATCHER_RECONNECT_INITIAL_BACKOFF_S
        while True:
            pubsub = self._client.pubsub()
            try:
                await pubsub.psubscribe(pattern)
                self._register_cancel_dispatcher_reconnect_callback(pubsub)
                backoff = self._DISPATCHER_RECONNECT_INITIAL_BACKOFF_S
                await logger.adebug(f"RedisJobQueueService: cancel dispatcher subscribed to {pattern}")
                async for message in pubsub.listen():
                    if message.get("type") != "pmessage":
                        continue
                    channel = message.get("channel")
                    if channel is None:
                        continue
                    channel_str = channel.decode() if isinstance(channel, bytes) else channel
                    if not channel_str.startswith(self.CANCEL_CHANNEL_PREFIX):
                        continue
                    job_id = channel_str[len(self.CANCEL_CHANNEL_PREFIX) :]
                    await self._handle_cancel(job_id, source="pubsub")
                # listen() returned cleanly — treat as a soft disconnect and reconnect.
                self._cancel_stats["dispatcher_reconnects"] += 1
                await logger.awarning(f"Cancel dispatcher pubsub.listen() ended; reconnecting in {backoff:.1f}s")
            except asyncio.CancelledError:
                with contextlib.suppress(Exception):
                    await pubsub.punsubscribe(pattern)
                await self._close_pubsub(pubsub)
                return
            except (ConnectionError, TimeoutError, OSError) as exc:
                # Expected transient failure: Redis dropped the pubsub, network
                # blip, broker restart. Reconnect quietly via the backoff loop.
                self._cancel_stats["dispatcher_reconnects"] += 1
                await logger.awarning(f"Cancel dispatcher disconnect (retrying in {backoff:.1f}s): {exc!r}")
            except Exception as exc:  # noqa: BLE001
                # Unexpected exception — likely a bug in dispatch logic, NOT a
                # Redis problem. Surface at error level with traceback so it
                # reaches Sentry / log aggregation, then still reconnect so a
                # one-off bug doesn't kill cross-worker cancel permanently.
                self._cancel_stats["dispatcher_reconnects"] += 1
                self._cancel_stats["dispatcher_internal_errors"] += 1
                await logger.aerror(
                    f"Cancel dispatcher internal error (retrying in {backoff:.1f}s): {exc!r}",
                    exc_info=True,
                )
            # Clean up the dead pubsub before sleeping + retrying.
            with contextlib.suppress(Exception):
                await pubsub.punsubscribe(pattern)
            await self._close_pubsub(pubsub)
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                return
            backoff = min(backoff * 2, self._DISPATCHER_RECONNECT_MAX_BACKOFF_S)

    async def _on_cancel_dispatcher_connection_reconnect(self, _connection: Any) -> None:
        """Record redis-py reconnects that happen inside an active PubSub."""
        self._cancel_stats["dispatcher_reconnects"] += 1
        with contextlib.suppress(Exception):
            await logger.awarning("Cancel dispatcher pubsub connection reconnected transparently")

    def _register_cancel_dispatcher_reconnect_callback(self, pubsub: Any) -> None:
        connection = getattr(pubsub, "connection", None)
        register = getattr(connection, "register_connect_callback", None)
        if register is not None:
            with contextlib.suppress(Exception):
                register(self._on_cancel_dispatcher_connection_reconnect)

    async def _close_pubsub(self, pubsub: Any) -> None:
        """Close a pubsub object regardless of redis-py version.

        Newer redis-py (>=5) exposes ``aclose``; older releases used ``close``.
        """
        connection = getattr(pubsub, "connection", None)
        deregister = getattr(connection, "deregister_connect_callback", None)
        if deregister is not None:
            with contextlib.suppress(Exception):
                deregister(self._on_cancel_dispatcher_connection_reconnect)
        close = getattr(pubsub, "aclose", None) or getattr(pubsub, "close", None)
        if close is None:
            return
        with contextlib.suppress(Exception):
            result = close()
            if asyncio.iscoroutine(result):
                await result

    async def _apply_cancel(self, job_id: str, *, source: str, wait_for_cleanup: bool) -> None:
        """Apply a cancel signal for *job_id* if this worker owns the job.

        Cancels the local task, flushes a sentinel through the bridge so cross-worker
        consumers see end-of-stream promptly, and triggers fast cleanup of the
        Redis stream + owner keys. No-op if this worker doesn't own the job
        (the owning worker's dispatcher will receive the same publish for
        pub/sub cancels).
        """
        entry = self._queues.get(job_id)
        if entry is None:
            self._cancel_stats["dispatched_foreign"] += 1
            await logger.adebug(f"Cancel for {job_id} ignored on this worker (not owner); source={source}")
            return
        self._cancel_stats["dispatched_owned"] += 1
        await logger.ainfo(f"Cancel applied to {job_id} (source={source})")
        main_queue, _, task, _ = entry
        if task is not None and not task.done():
            task.cancel()
        # Flush a sentinel so the bridge publishes the Redis end-of-stream marker
        # before cleanup deletes the stream key.
        with contextlib.suppress(Exception):
            main_queue.put_nowait((None, None, time.time()))
        # Trigger fast cleanup; runs as a fire-and-forget task that swallows the
        # expected CancelledError re-raised by super().cleanup_job.
        cleanup_task = self._spawn_background(self._post_cancel_cleanup(job_id))
        if wait_for_cleanup:
            # Keep cleanup alive even if the HTTP request is cancelled while the
            # endpoint is waiting for confirmation.
            await asyncio.shield(cleanup_task)

    async def _handle_cancel(self, job_id: str, *, source: str) -> None:
        """Apply a received pub/sub or marker cancel signal for *job_id*."""
        await self._apply_cancel(job_id, source=source, wait_for_cleanup=False)

    # Max time _post_cancel_cleanup waits on cleanup_job before giving up.
    # Bounds the lifetime of the background task even under Redis pathology
    # (e.g. a hung DELETE). Periodic cleanup will still reap stale state later.
    _POST_CANCEL_CLEANUP_TIMEOUT_S = 10.0

    async def _post_cancel_cleanup(self, job_id: str) -> None:
        """Fire-and-forget cleanup wrapper that runs after the bridge has flushed.

        Waits for the bridge task to drain the sentinel we just put on the local
        queue and publish the Redis end-of-stream marker before cancelling it via
        :meth:`cleanup_job`. Without this wait, a fast cleanup races the bridge
        and may cancel it before XADD completes, leaving cross-worker consumers
        without the sentinel record in the stream.

        The outer :data:`_POST_CANCEL_CLEANUP_TIMEOUT_S` bounds total runtime so
        a stuck cleanup_job (e.g. Redis stalls during stream DELETE) does not
        leak this background task forever; periodic cleanup will reap whatever
        state remains on its next pass.
        """
        bridge = self._bridge_tasks.get(job_id)
        if bridge is not None and not bridge.done():
            # ``shield`` keeps the bridge alive even if our task is cancelled
            # during the wait; the inner timeout caps the worst case if XADD
            # is stuck (cross-worker consumers can still recover via the
            # missing-stream-key sentinel path). Narrow the except to the
            # timeout case only so real bridge failures bubble up.
            try:
                await asyncio.wait_for(asyncio.shield(bridge), timeout=2.0)
            except asyncio.TimeoutError:
                await logger.awarning(
                    f"Post-cancel cleanup: bridge sentinel flush timed out for {job_id}; "
                    "cross-worker consumers may see late end-of-stream."
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                await logger.awarning(f"Post-cancel cleanup: bridge wait failed for {job_id}: {exc!r}")
        try:
            await asyncio.wait_for(
                self.cleanup_job(job_id),
                timeout=self._POST_CANCEL_CLEANUP_TIMEOUT_S,
            )
        except asyncio.CancelledError:
            # Expected: super().cleanup_job re-raises after a user-initiated cancel.
            pass
        except asyncio.TimeoutError:
            await logger.awarning(
                f"Post-cancel cleanup timed out for {job_id} after "
                f"{self._POST_CANCEL_CLEANUP_TIMEOUT_S:.1f}s; periodic cleanup will retry."
            )
        except Exception as exc:  # noqa: BLE001
            await logger.awarning(f"Post-cancel cleanup error for {job_id}: {exc}")

    async def cancel_job(self, job_id: str) -> None:
        """Cancel an owned Redis job after publishing an end-of-stream sentinel.

        ``cleanup_job`` alone cancels the bridge before the cancelled build task
        can publish a terminal stream record. Route explicit same-worker cancels
        through the same sentinel-flush path used by cross-worker pub/sub cancels
        so any Redis-backed consumer terminates promptly.
        """
        await self._apply_cancel(job_id, source="local", wait_for_cleanup=True)

    async def signal_cancel(self, job_id: str) -> int:
        """Publish a cancel signal for *job_id* across all worker dispatchers.

        Authorization note: this method does not perform any authorization check.
        Callers must verify the caller has rights to cancel the job — the HTTP
        cancel endpoint does this via ``_verify_job_ownership`` before calling
        through.

        Returns the number of dispatchers reached by the PUBLISH. A return of 0
        is not necessarily a failure — the persistent marker key is also set, so
        a worker that picks up the job *after* this publish will still process
        the cancel during its start_job marker check.

        Raises:
            redis exceptions if the Redis connection is unavailable. Callers
            that want best-effort behaviour should wrap in their own try/except.
        """
        if not self._cancel_channel_enabled or self._client is None:
            return 0
        try:
            # Set the marker first so any worker that races the publish still sees it.
            await self._client.set(self._cancel_marker_key(job_id), "1", ex=self._cancel_marker_ttl)
            receivers = int(await self._client.publish(self._cancel_channel(job_id), "1"))
        except Exception:
            self._cancel_stats["publish_errors"] += 1
            raise
        self._cancel_stats["published"] += 1
        await logger.ainfo(f"signal_cancel: job_id={job_id} receivers={receivers}")
        return receivers

    def metrics_snapshot(self) -> dict[str, Any]:  # type: ignore[override]
        """Extend the base snapshot with Redis-backed bridge / cancel observability.

        Fields:
        * ``bridge_count`` — active bridge tasks (one per locally-owned job).
        * ``consumer_wrapper_count`` — open cross-worker consumer wrappers.
        * ``background_task_count`` — fire-and-forget marker checks + cleanups.
        * ``cancel_dispatcher_running`` — True if the PSUBSCRIBE loop is alive.
        * ``cancel_stats`` — a copy of the cancel observability counters.
          ``dispatcher_reconnects`` counts explicit dispatcher-loop retries and
          redis-py transparent pubsub reconnect callbacks.
        """
        base = super().metrics_snapshot()
        base["backend"] = "redis"
        base["bridge_count"] = len(self._bridge_tasks)
        base["consumer_wrapper_count"] = len(self._consumer_wrappers)
        base["background_task_count"] = len(self._background_tasks)
        base["cancel_dispatcher_running"] = (
            self._cancel_dispatcher_task is not None and not self._cancel_dispatcher_task.done()
        )
        base["cancel_stats"] = dict(self._cancel_stats)
        return base

    def get_queue_data(self, job_id: str) -> tuple[asyncio.Queue, EventManager, asyncio.Task | None, float | None]:  # type: ignore[override]
        """Return queue data for a job, always backed by a Redis Stream consumer.

        The queue returned is always a :class:`RedisQueueWrapper` that reads from the
        Redis Stream, regardless of whether the job was started on this worker. This
        avoids the race condition that would occur if the bridge coroutine and the HTTP
        consumer both read from the same local ``asyncio.Queue``.

        * **Same-worker path**: the bridge is the sole reader of the local queue; the
          HTTP consumer reads from Redis via the wrapper. The real ``asyncio.Task`` and
          ``EventManager`` are returned from the local registry so that disconnect
          handling and ownership checks work normally.
        * **Cross-worker path**: no local entry exists; a null ``EventManager`` and
          ``None`` task are returned. Cancellation from this worker travels via
          :meth:`signal_cancel` rather than a local ``task.cancel()`` — the
          dispatcher on the owning worker fires the cancel, and the streaming
          response's :func:`langflow.api.build.create_flow_response.on_disconnect`
          wires this up automatically for passive client disconnects.
        """
        if self._closed:
            msg = f"Queue service is closed for job_id: {job_id}"
            raise RuntimeError(msg)

        if job_id in self._queues:
            # Same-worker: keep task + event_manager from local registry; give a Redis
            # stream wrapper to the consumer so the bridge is the only local-queue reader.
            _, event_manager, task, cleanup_time = self._queues[job_id]
            return (  # type: ignore[return-value]
                self._get_consumer_wrapper(job_id),
                event_manager,
                task,
                cleanup_time,
            )

        # Cross-worker path: create a Redis-backed consumer for the stream.
        # EventManager(None) is a null manager — send_event is a no-op (queue is None-guarded).
        return (  # type: ignore[return-value]
            self._get_consumer_wrapper(job_id),
            EventManager(None),
            None,
            None,
        )

    async def _cleanup_old_queues(self) -> None:
        """Run base queue cleanup then sweep done cross-worker consumer wrappers.

        Cross-worker jobs are never inserted into ``self._queues``, so the base
        sweep never sees them. Their ``RedisQueueWrapper._fill_task`` exits on
        its own (sentinel or ``exists()=False``), but the dict entry in
        ``_consumer_wrappers`` stays forever unless we explicitly prune it here.
        """
        await super()._cleanup_old_queues()

        # Only prune wrappers that are NOT owned by this worker (i.e. absent from
        # self._queues). Same-worker wrappers are removed by cleanup_job(); touching
        # them here would race with the grace-period logic in the base class.
        done_cross_worker = [
            job_id
            for job_id, wrapper in self._consumer_wrappers.items()
            if job_id not in self._queues and wrapper.fill_done()
        ]
        for job_id in done_cross_worker:
            wrapper = self._consumer_wrappers.pop(job_id, None)
            if wrapper is not None:
                await logger.adebug(f"Swept done cross-worker consumer wrapper for job_id {job_id}")

    async def cleanup_job(self, job_id: str) -> None:
        """Cancel local task and bridge, then delete the Redis Stream and owner keys."""
        # Capture ownership before super() pops the entry from self._queues so that
        # the Redis-key deletion below is scoped to the owning worker only. A
        # cross-worker poll populates _consumer_wrappers but not _queues; deleting
        # the stream/owner keys from that worker would corrupt an in-flight build on
        # the true owner.
        is_owner = job_id in self._queues
        # Drop the watchdog start-time entry alongside ownership.
        self._job_start_times.pop(job_id, None)

        owner_refresh_task = self._owner_refresh_tasks.pop(job_id, None)
        if owner_refresh_task is not None and not owner_refresh_task.done():
            owner_refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await owner_refresh_task

        wrapper = self._consumer_wrappers.pop(job_id, None)
        if wrapper is not None:
            if is_owner:
                await wrapper.finish_with_sentinel()
            else:
                await wrapper.cancel()

        bridge = self._bridge_tasks.pop(job_id, None)
        if bridge and not bridge.done():
            bridge.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await bridge

        try:
            await super().cleanup_job(job_id)
        finally:
            if is_owner and self._client:
                # Best-effort delete of all Redis state owned by this job.
                # Combined into one DEL so a single round-trip handles them.
                # Truly best-effort: a Redis failure here must not escape and
                # break stop() / explicit cancel, which is most likely to happen
                # exactly when Redis is unhealthy.
                try:
                    await self._client.delete(
                        self._stream_key(job_id),
                        self._owner_key(job_id),
                        self._activity_key(job_id),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    await logger.awarning(f"Redis key cleanup failed for job_id {job_id}: {exc!r}")
                else:
                    await logger.adebug(f"Redis keys deleted for job_id {job_id}")

    async def register_job_owner(self, job_id: str, user_id: UUID) -> None:
        """Store the job owner in Redis for cross-worker ownership checks."""
        self._job_owners[job_id] = user_id
        await self._set_owner_key(job_id, user_id)
        if job_id in self._queues:
            self._ensure_owner_refresh_task(job_id)

    async def get_job_owner(self, job_id: str) -> UUID | None:
        """Retrieve the job owner, checking Redis when not found locally.

        The Redis key TTL is refreshed on every successful cross-worker lookup so
        that long-running builds (agent loops, large RAG ingests, etc.) do not lose
        their ownership anchor mid-flight. The in-memory path is not TTL-bound.
        """
        local = self._job_owners.get(job_id)
        if local is not None:
            return local
        if self._client:
            owner_key = self._owner_key(job_id)
            value = await self._client.get(owner_key)
            if value:
                from uuid import UUID as _UUID

                # Slide the TTL forward so builds longer than the initial TTL
                # continue to pass ownership checks as long as they are polled.
                await self._client.expire(owner_key, self._ttl)
                return _UUID(value.decode())
        return None
