from __future__ import annotations

import asyncio

from loguru import logger

from langflow.events.event_manager import EventManager, create_default_event_manager
from langflow.services.base import Service


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
        logger.debug("JobQueueService stopped: all job queues have been cleaned up.")

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
        if job_id in self._queues:
            msg = f"Queue for job_id {job_id} already exists"
            logger.error(msg)
            raise ValueError(msg)

        if self._closed:
            msg = "Queue service is closed"
            logger.error(msg)
            raise RuntimeError(msg)

        main_queue: asyncio.Queue = asyncio.Queue()
        event_manager = create_default_event_manager(main_queue)

        # Register the queue without an active task.
        self._queues[job_id] = (main_queue, event_manager, None, None)
        logger.debug(f"Queue and event manager successfully created for job_id {job_id}")
        return main_queue, event_manager

    def start_job(self, job_id: str, task_coro) -> None:
        """Start an asynchronous task for a given job, replacing any existing active task.

        The method performs the following:
          - Verifies the presence of a registered queue for the job.
          - Cancels any currently running task associated with the job.
          - Launches a new asynchronous task using the provided coroutine.
          - Updates the internal registry with the new task.

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

        # Initiate the new asynchronous task.
        task = asyncio.create_task(task_coro)
        self._queues[job_id] = (main_queue, event_manager, task, None)
        logger.debug(f"New task started for job_id {job_id}")

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
            logger.debug(f"No queue found for job_id {job_id} during cleanup.")
            return

        logger.debug(f"Commencing cleanup for job_id {job_id}")
        main_queue, _event_manager, task, _ = self._queues[job_id]

        # Cancel the associated task if it is still running.
        if task and not task.done():
            logger.debug(f"Cancelling active task for job_id {job_id}")
            task.cancel()
            await asyncio.wait([task])
            # Log any exceptions that occurred during the task's execution.
            if exc := task.exception():
                logger.error(f"Error in task for job_id {job_id}: {exc}")
            logger.debug(f"Task cancellation complete for job_id {job_id}")

        # Clear the queue since we just cancelled the task or it has completed
        items_cleared = 0
        while not main_queue.empty():
            try:
                main_queue.get_nowait()
                items_cleared += 1
            except asyncio.QueueEmpty:
                break

        logger.debug(f"Removed {items_cleared} items from queue for job_id {job_id}")
        # Remove the job entry from the registry
        self._queues.pop(job_id, None)
        logger.debug(f"Cleanup successful for job_id {job_id}: resources have been released.")

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
                logger.debug("Periodic cleanup task received cancellation signal.")
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Exception encountered during periodic cleanup: {exc}")

    async def _cleanup_old_queues(self) -> None:
        """Scan all registered job queues and clean up those with completed or failed tasks."""
        current_time = asyncio.get_running_loop().time()

        for job_id in list(self._queues.keys()):
            _, _, task, cleanup_time = self._queues[job_id]
            if task:
                logger.debug(
                    f"Queue {job_id} status - Done: {task.done()}, "
                    f"Cancelled: {task.cancelled()}, "
                    f"Has exception: {task.exception() is not None if task.done() else 'N/A'}"
                )

                # Check if task should be marked for cleanup
                if task and (task.cancelled() or (task.done() and task.exception() is not None)):
                    if cleanup_time is None:
                        # Mark for cleanup by setting the timestamp
                        self._queues[job_id] = (
                            self._queues[job_id][0],
                            self._queues[job_id][1],
                            self._queues[job_id][2],
                            current_time,
                        )
                        logger.debug(f"Job queue for job_id {job_id} marked for cleanup - Task cancelled or failed")
                    elif current_time - cleanup_time >= self.CLEANUP_GRACE_PERIOD:
                        # Enough time has passed, perform the actual cleanup
                        logger.debug(f"Cleaning up job_id {job_id} after grace period")
                        await self.cleanup_job(job_id)
