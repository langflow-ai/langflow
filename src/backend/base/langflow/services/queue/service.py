import asyncio

from loguru import logger

from langflow.events.event_manager import EventManager
from langflow.services.base import Service


class QueueService(Service):
    name = "queue_service"

    def __init__(self) -> None:
        self._queues: dict[str, tuple[asyncio.Queue, asyncio.Queue, EventManager, asyncio.Task | None]] = {}

    def create_queue(self, job_id: str) -> tuple[asyncio.Queue, asyncio.Queue, EventManager]:
        """Create a new queue set for a job.

        Args:
            job_id: The unique identifier for the job

        Returns:
            tuple: (main_queue, client_queue, event_manager)
        """
        if job_id in self._queues:
            msg = f"Queue for job_id {job_id} already exists"
            raise ValueError(msg)

        main_queue: asyncio.Queue = asyncio.Queue()
        client_queue: asyncio.Queue = asyncio.Queue()
        event_manager = EventManager(queue=main_queue)

        # Store without task for now
        self._queues[job_id] = (main_queue, client_queue, event_manager, None)
        return main_queue, client_queue, event_manager

    def set_task(self, job_id: str, task: asyncio.Task) -> None:
        """Set the task for a job.

        Args:
            job_id: The unique identifier for the job
            task: The asyncio task for the job
        """
        if job_id not in self._queues:
            msg = f"No queue found for job_id {job_id}"
            raise ValueError(msg)

        main_queue, client_queue, event_manager, _ = self._queues[job_id]
        self._queues[job_id] = (main_queue, client_queue, event_manager, task)

    def get_queue_data(self, job_id: str) -> tuple[asyncio.Queue, asyncio.Queue, EventManager, asyncio.Task | None]:
        """Get the queue data for a job.

        Args:
            job_id: The unique identifier for the job

        Returns:
            tuple: (main_queue, client_queue, event_manager, task)
        """
        if job_id not in self._queues:
            msg = f"No queue found for job_id {job_id}"
            raise ValueError(msg)

        return self._queues[job_id]

    def remove_queue(self, job_id: str) -> None:
        """Remove a queue set for a job.

        Args:
            job_id: The unique identifier for the job
        """
        if job_id in self._queues:
            _, _, _, task = self._queues[job_id]
            if task and not task.done():
                task.cancel()
            del self._queues[job_id]
            logger.debug(f"Removed queue for job_id {job_id}")

    def cleanup_old_queues(self) -> None:
        """Remove all completed or cancelled queues."""
        for job_id in list(self._queues.keys()):
            _, _, _, task = self._queues[job_id]
            if task and (task.done() or task.cancelled()):
                self.remove_queue(job_id)
