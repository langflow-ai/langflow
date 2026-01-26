from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langflow.exceptions.api import WorkflowResourceError, WorkflowServiceUnavailableError
from langflow.services.base import Service
from langflow.services.deps import get_queue_service
from langflow.services.task.backends.anyio import AnyIOBackend
from langflow.services.task.backends.celery import CeleryBackend

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

    from langflow.services.task.backends.base import TaskBackend


class TaskService(Service):
    name = "task_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        self.use_celery = self.settings_service.settings.celery_enabled
        self.backend = self.get_backend()

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def get_backend(self) -> TaskBackend:
        if self.use_celery:
            return CeleryBackend()
        return AnyIOBackend()

    async def fire_and_forget_task(self, task_func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        """Launch a task in the background and forget about it.

        Note: This is required since the local AnyIOBackend does not support background tasks
        natively in a non-blocking way for the API.

        This method abstracts the background execution. If Celery is enabled,
        it uses the distributed queue. Otherwise, it uses the JobQueueService
        to manage and track the asynchronous task locally.

        Args:
            task_func: The task function to launch.
            *args: Positional arguments for the task function.
            **kwargs: Keyword arguments for the task function.

        Returns:
            str: A task_id that can be used to track or cancel the task via JobQueueService.
        """
        if self.use_celery:
            task_id, _ = self.backend.launch_task(task_func, *args, **kwargs)
            return task_id

        graph = kwargs.get("graph")
        task_id = graph.run_id if graph and hasattr(graph, "run_id") else str(uuid4())
        # Create a job queue for the task and track the job execution using the
        # JobQueueService
        job_queue_service = get_queue_service()
        try:
            job_queue_service.create_queue(task_id)
            job_queue_service.start_job(task_id, task_func(*args, **kwargs))
        except (RuntimeError, ValueError) as e:
            await job_queue_service.cleanup_job(task_id)
            msg = f"Local task queue error: {e!s}"
            raise WorkflowServiceUnavailableError(msg) from e
        except MemoryError as e:
            await job_queue_service.cleanup_job(task_id)
            msg = f"Memory exhaustion during local task creation: {e!s}"
            raise WorkflowResourceError(msg) from e
        except Exception:
            await job_queue_service.cleanup_job(task_id)
            raise
        return task_id

    # In your TaskService class
    async def launch_and_await_task(
        self,
        task_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        return await task_func(*args, **kwargs)

    async def launch_task(self, task_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        task = self.backend.launch_task(task_func, *args, **kwargs)
        return await task if isinstance(task, Coroutine) else task
