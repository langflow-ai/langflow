from typing import Any, Callable, Union
import logging

from langflow.services.base import Service
from langflow.services.task.backends.anyio import AnyIOBackend
from langflow.services.task.backends.base import TaskBackend
from langflow.services.task.utils import get_celery_worker_status

try:
    from langflow.worker import celery_app

    try:
        status = get_celery_worker_status(celery_app)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        status = {"availability": None}
    USE_CELERY = status.get("availability") is not None
except ImportError:
    USE_CELERY = False


class TaskManager(Service):
    name = "task_manager"

    def __init__(self):
        self.backend = self.get_backend()
        self.use_celery = USE_CELERY

    def get_backend(self) -> TaskBackend:
        if USE_CELERY:
            from langflow.services.task.backends.celery import CeleryBackend

            return CeleryBackend()
        return AnyIOBackend()

    # In your TaskManager class
    async def launch_and_await_task(
        self,
        task_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not self.use_celery:
            return None, await task_func(*args, **kwargs)
        task = task_func.apply(args=args, kwargs=kwargs)
        result = task.get()
        return task.id, result

    async def launch_task(
        self, task_func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Union[str, str]:
        return await self.backend.launch_task(task_func, *args, **kwargs)

    def get_task(self, task_id: Union[int, str]) -> Any:
        return self.backend.get_task(task_id)
