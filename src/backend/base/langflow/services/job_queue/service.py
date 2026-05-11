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
        sentinel to be written before the task exits.  This guarantees that
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
        itself after emitting ``on_end``.  If the coroutine raises an unexpected
        exception before doing so, this wrapper:

        1. Emits an ``on_error`` event so consumers can distinguish a crash from a
           clean end — both cases deliver ``(None, None, ts)`` as the terminal item,
           but a crash is always preceded by an error event in the stream.
        2. Puts the raw ``(None, None, ts)`` sentinel so the bridge flushes and
           writes ``_STREAM_SENTINEL_DATA`` to the Redis Stream before cleanup
           deletes the key, preventing consumers from hanging indefinitely.

        ``asyncio.CancelledError`` is not caught here; the caller (``cleanup_job`` /
        ``cancel_flow_build``) is responsible for those paths and already handles
        sentinel delivery via bridge cancellation + stream-key deletion.
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
    for a job that was started on a different worker process.  A background
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
    # How long to keep polling before giving up on a stream that has never appeared.
    # Protects against the early-poll race where the consumer wrapper is created
    # before the producer worker has issued its first XADD.
    _STARTUP_GRACE_S = 30.0

    def __init__(self, job_id: str, client: Any, ttl: int) -> None:
        self._job_id = job_id
        self._client = client
        self._ttl = ttl
        self._buffer: asyncio.Queue = asyncio.Queue()
        self._last_id = "0-0"  # read from the beginning of the stream
        # Flips to True the first time XREAD returns messages for this stream.
        # Until then, "stream key does not exist" is NOT treated as end-of-stream
        # — it just means the producer hasn't written its first event yet.
        self._observed_stream: bool = False
        self._created_at: float = time.monotonic()
        self._fill_task: asyncio.Task = asyncio.create_task(self._fill_from_redis())

    @property
    def _stream_key(self) -> str:
        return f"{self.STREAM_PREFIX}{self._job_id}"

    async def _fill_from_redis(self) -> None:
        """Read events from the Redis Stream and forward them to the local buffer."""
        try:
            while True:
                try:
                    results = await self._client.xread(
                        {self._stream_key: self._last_id},
                        block=self._XREAD_BLOCK_MS,
                        count=self._XREAD_BATCH_COUNT,
                    )
                except Exception as exc:  # noqa: BLE001
                    await logger.awarning(f"RedisQueueWrapper read error for {self._job_id}: {exc}")
                    await asyncio.sleep(self._READ_ERROR_BACKOFF_S)
                    continue

                if results:
                    self._observed_stream = True
                    for _, messages in results:
                        for msg_id, fields in messages:
                            self._last_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                            data = fields.get(b"data")
                            ts = float(fields.get(b"ts", b"0") or b"0")
                            if data == _STREAM_SENTINEL_DATA:
                                await self._buffer.put((None, None, ts))
                                return
                            event_id = (fields.get(b"event_id") or b"").decode()
                            await self._buffer.put((event_id, data, ts))
                # No results within the block timeout.
                elif not self._observed_stream:
                    # Stream hasn't appeared yet — the producer may not have issued its
                    # first XADD (early-poll race between workers).  Keep blocking until
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
        return self._buffer.empty()

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

    Known limitations
    -----------------
    * Cross-worker *cancel*: cancelling a build running on Worker A from Worker B
      silently no-ops (returns success).  True cross-worker cancel would require an
      additional Redis signal channel checked inside the build loop.
    """

    STREAM_PREFIX = _STREAM_PREFIX
    OWNER_PREFIX = _OWNER_PREFIX

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 1,
        url: str | None = None,
        ttl: int = 3600,
    ) -> None:
        super().__init__()
        self._redis_host = host
        self._redis_port = port
        self._redis_db = db
        self._redis_url = url
        self._ttl = ttl
        self._client: Any = None
        self._connection_check_task: asyncio.Task | None = None
        self._bridge_tasks: dict[str, asyncio.Task] = {}
        self._consumer_wrappers: dict[str, RedisQueueWrapper] = {}

    def _stream_key(self, job_id: str) -> str:
        return f"{self.STREAM_PREFIX}{job_id}"

    def _owner_key(self, job_id: str) -> str:
        return f"{self.OWNER_PREFIX}{job_id}"

    def start(self) -> None:
        """Create the Redis client and start the periodic cleanup routine."""
        from redis.asyncio import StrictRedis

        if self._redis_url:
            self._client = StrictRedis.from_url(self._redis_url)
        else:
            self._client = StrictRedis(host=self._redis_host, port=self._redis_port, db=self._redis_db)
        super().start()
        # Schedule a connectivity check so startup logs a clear error if Redis is unreachable.
        self._connection_check_task = asyncio.create_task(self._check_connection())
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
        """Stop the service, cancel all bridge tasks, and close the Redis client."""
        if self._connection_check_task and not self._connection_check_task.done():
            self._connection_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._connection_check_task
        self._connection_check_task = None

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
            wrapper = RedisQueueWrapper(job_id, self._client, self._ttl)
            self._consumer_wrappers[job_id] = wrapper
        return wrapper

    def get_queue_data(self, job_id: str) -> tuple[asyncio.Queue, EventManager, asyncio.Task | None, float | None]:  # type: ignore[override]
        """Return queue data for a job, always backed by a Redis Stream consumer.

        The queue returned is always a :class:`RedisQueueWrapper` that reads from the
        Redis Stream, regardless of whether the job was started on this worker.  This
        avoids the race condition that would occur if the bridge coroutine and the HTTP
        consumer both read from the same local ``asyncio.Queue``.

        * **Same-worker path**: the bridge is the sole reader of the local queue; the
          HTTP consumer reads from Redis via the wrapper.  The real ``asyncio.Task`` and
          ``EventManager`` are returned from the local registry so that disconnect
          handling and ownership checks work normally.
        * **Cross-worker path**: no local entry exists; a null ``EventManager`` and
          ``None`` task are returned (cross-worker cancel is a known limitation).
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
        sweep never sees them.  Their ``RedisQueueWrapper._fill_task`` exits on
        its own (sentinel or ``exists()=False``), but the dict entry in
        ``_consumer_wrappers`` stays forever unless we explicitly prune it here.
        """
        await super()._cleanup_old_queues()

        # Only prune wrappers that are NOT owned by this worker (i.e. absent from
        # self._queues).  Same-worker wrappers are removed by cleanup_job(); touching
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
        # the Redis-key deletion below is scoped to the owning worker only.  A
        # cross-worker poll populates _consumer_wrappers but not _queues; deleting
        # the stream/owner keys from that worker would corrupt an in-flight build on
        # the true owner.
        is_owner = job_id in self._queues

        wrapper = self._consumer_wrappers.pop(job_id, None)
        if wrapper is not None:
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
                await self._client.delete(self._stream_key(job_id), self._owner_key(job_id))
                await logger.adebug(f"Redis keys deleted for job_id {job_id}")

    async def register_job_owner(self, job_id: str, user_id: UUID) -> None:
        """Store the job owner in Redis for cross-worker ownership checks."""
        self._job_owners[job_id] = user_id
        if self._client:
            await self._client.set(self._owner_key(job_id), str(user_id), ex=self._ttl)

    async def get_job_owner(self, job_id: str) -> UUID | None:
        """Retrieve the job owner, checking Redis when not found locally.

        The Redis key TTL is refreshed on every successful cross-worker lookup so
        that long-running builds (agent loops, large RAG ingests, etc.) do not lose
        their ownership anchor mid-flight.  The in-memory path is not TTL-bound.
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
