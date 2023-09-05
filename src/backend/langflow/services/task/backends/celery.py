from typing import Any, Callable
from celery.result import AsyncResult  # type: ignore
from langflow.services.task.backends.base import TaskBackend
from langflow.worker import celery_app


class CeleryBackend(TaskBackend):
    def __init__(self):
        self.celery_app = celery_app

    def launch_task(
        self, task_func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> str:
        if not hasattr(task_func, "delay"):
            raise ValueError(f"Task function {task_func} does not have a delay method")
        task = task_func.delay(*args, **kwargs)
        return task.id

    def get_task(self, task_id: str) -> Any:
        return AsyncResult(task_id, app=self.celery_app)
