from typing import Any, Callable, Coroutine, Union
from langflow.utils.logger import configure
from loguru import logger
from langflow.services.base import Service
from langflow.services.task.backends.anyio import AnyIOBackend
from langflow.services.task.backends.base import TaskBackend
from langflow.services.task.utils import get_celery_worker_status


def check_celery_availability():
    try:
        from langflow.worker import celery_app

        status = get_celery_worker_status(celery_app)
        logger.debug(f"Celery status: {status}")
    except Exception as exc:
        logger.debug(f"Celery not available: {exc}")
        status = {"availability": None}
    return status


try:
    configure()
    status = check_celery_availability()

    USE_CELERY = status.get("availability") is not None
except ImportError:
    USE_CELERY = False


class TaskService(Service):
    name = "task_service"

    def __init__(self):
        self.backend = self.get_backend()
        self.use_celery = USE_CELERY

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def get_backend(self) -> TaskBackend:
        if USE_CELERY:
            from langflow.services.task.backends.celery import CeleryBackend

            logger.debug("Using Celery backend")
            return CeleryBackend()
        logger.debug("Using AnyIO backend")
        return AnyIOBackend()

    # In your TaskService class
    async def launch_and_await_task(
        self,
        task_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not self.use_celery:
            return None, await task_func(*args, **kwargs)
        if not hasattr(task_func, "apply"):
            raise ValueError(f"Task function {task_func} does not have an apply method")
        task = task_func.apply(args=args, kwargs=kwargs)
        result = task.get()
        return task.id, result

    async def launch_task(
        self, task_func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        logger.debug(f"Launching task {task_func} with args {args} and kwargs {kwargs}")
        logger.debug(f"Using backend {self.backend}")
        task = self.backend.launch_task(task_func, *args, **kwargs)
        return await task if isinstance(task, Coroutine) else task

    def get_task(self, task_id: Union[int, str]) -> Any:
        return self.backend.get_task(task_id)
