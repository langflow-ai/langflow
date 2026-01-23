from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from langflow.services.task.backends.base import TaskBackend

if TYPE_CHECKING:
    from celery import Task


class CeleryBackend(TaskBackend):
    name = "celery"

    def __init__(self) -> None:
        from langflow.worker import celery_app

        self.celery_app = celery_app

    # TODO: Barebones implementation, needs check like task_func being decorated with celery Task
    # dedicated error handling for celery specific errors and retries
    def launch_task(self, task_func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[str, Any]:
        from langflow.exceptions.api import WorkflowResourceError, WorkflowServiceUnavailableError

        # I need to type the delay method to make it easier
        if not hasattr(task_func, "delay"):
            msg = f"Task function {task_func} does not have a delay method"
            raise ValueError(msg)
        try:
            task: Task = task_func.delay(*args, **kwargs)
        except Exception as e:
            # Handle common celery/broker errors
            # OperationalError usually means the broker is down or unreachable
            # kombu is a required dependency of celery
            from kombu.exceptions import OperationalError

            if isinstance(e, (OperationalError, ConnectionError)):
                msg = f"Task queue broker is unavailable: {e!s}"
                raise WorkflowServiceUnavailableError(msg) from e
            if isinstance(e, MemoryError):
                msg = f"Memory exhaustion during task submission: {e!s}"
                raise WorkflowResourceError(msg) from e
            raise
        return task.id, task

    def get_task(self, task_id: str) -> Any:
        from celery.result import AsyncResult

        return AsyncResult(task_id, app=self.celery_app)
