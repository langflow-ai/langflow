from typing import Any, Callable
from celery.result import AsyncResult
from langflow.services.task.backends.base import TaskBackend
from langflow.worker import celery_app


class CeleryBackend(TaskBackend):
    def __init__(self):
        self.celery_app = celery_app

    def launch_task(
        self, task_func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> str:
        task = task_func.apply_async(args=args, kwargs=kwargs)
        return task.id

    def get_task(self, task_id: str) -> AsyncResult:
        return AsyncResult(task_id, app=self.celery_app)
