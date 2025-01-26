from __future__ import annotations

import asyncio
import contextlib

from loguru import logger

from langflow.events.event_manager import EventManager, create_default_event_manager
from langflow.services.base import Service


class QueueService(Service):
    name = "queue_service"

    def __init__(self) -> None:
        self._queues: dict[str, tuple[asyncio.Queue, EventManager, asyncio.Task | None]] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._closed = False

    async def start(self) -> None:
        """Start the queue service and its cleanup task."""
        self._closed = False
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self) -> None:
        """Stop the queue service and cleanup all resources."""
        self._closed = True
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        # Cleanup all queues
        for job_id in list(self._queues.keys()):
            await self.cleanup_job(job_id)

    def create_queue(self, job_id: str) -> tuple[asyncio.Queue, EventManager]:
        """Create a new queue set for a job.

        Args:
            job_id: The unique identifier for the job

        Returns:
            tuple: (main_queue, event_manager)
        """
        if job_id in self._queues:
            msg = f"Queue for job_id {job_id} already exists"
            raise ValueError(msg)

        if self._closed:
            msg = "Queue service is closed"
            raise RuntimeError(msg)

        main_queue: asyncio.Queue = asyncio.Queue()
        event_manager = create_default_event_manager(main_queue)

        # Store without task initially
        self._queues[job_id] = (main_queue, event_manager, None)
        logger.debug(f"Created queue for job_id {job_id}")
        return main_queue, event_manager

    def start_job(self, job_id: str, task_coro) -> None:
        """Start a job's task.

        Args:
            job_id: The unique identifier for the job
            task_coro: The coroutine to run as a task
        """
        if job_id not in self._queues:
            msg = f"No queue found for job_id {job_id}"
            raise ValueError(msg)

        main_queue, event_manager, existing_task = self._queues[job_id]

        if existing_task and not existing_task.done():
            existing_task.cancel()

        # Create and start the task
        task = asyncio.create_task(task_coro)
        self._queues[job_id] = (main_queue, event_manager, task)
        logger.debug(f"Started task for job_id {job_id}")

    def get_queue_data(self, job_id: str) -> tuple[asyncio.Queue, EventManager, asyncio.Task | None]:
        """Get the queue data for a job.

        Args:
            job_id: The unique identifier for the job

        Returns:
            tuple: (main_queue, event_manager, task)
        """
        if job_id not in self._queues:
            msg = f"No queue found for job_id {job_id}"
            raise ValueError(msg)

        return self._queues[job_id]

    async def cleanup_job(self, job_id: str) -> None:
        """Remove a queue set for a job and cleanup its resources."""
        if job_id in self._queues:
            main_queue, event_manager, task = self._queues[job_id]

            # Cancel the task if it exists and is still running
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

            # Clear the queues
            while not main_queue.empty():
                try:
                    main_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            # Remove from storage
            del self._queues[job_id]
            logger.debug(f"Cleaned up queue for job_id {job_id}")

    async def _periodic_cleanup(self) -> None:
        """Periodically clean up completed or cancelled queues."""
        while not self._closed:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_old_queues()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.exception(f"Error in periodic cleanup: {exc}")

    async def _cleanup_old_queues(self) -> None:
        """Remove all completed or cancelled queues."""
        for job_id in list(self._queues.keys()):
            _, _, task = self._queues[job_id]
            if task and (task.done() or task.cancelled()):
                await self.cleanup_job(job_id)
