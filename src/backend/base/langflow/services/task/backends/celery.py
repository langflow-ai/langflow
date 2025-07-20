from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from celery.result import AsyncResult

from langflow.services.task.backends.base import TaskBackend
from langflow.worker import celery_app

if TYPE_CHECKING:
    from celery import Task


class CeleryBackend(TaskBackend):
    name = "celery"

    def __init__(self) -> None:
        self.celery_app = celery_app

    def launch_task(self, task_func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[str, AsyncResult]:
        # I need to type the delay method to make it easier

        if not hasattr(task_func, "delay"):
            msg = f"Task function {task_func} does not have a delay method"
            raise ValueError(msg)
        task: Task = task_func.delay(*args, **kwargs)
        return task.id, AsyncResult(task.id, app=self.celery_app)

    def get_task(self, task_id: str) -> Any:
        return AsyncResult(task_id, app=self.celery_app)
