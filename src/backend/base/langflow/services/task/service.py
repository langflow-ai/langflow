from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from loguru import logger

from langflow.services.base import Service
from langflow.services.task.backends.anyio import AnyIOBackend
from langflow.services.task.utils import get_celery_worker_status

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService
    from langflow.services.task.backends.base import TaskBackend


def check_celery_availability():
    try:
        from langflow.worker import celery_app

        status = get_celery_worker_status(celery_app)
        logger.debug(f"Celery status: {status}")
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).debug("Celery not available")
        status = {"availability": None}
    return status


class TaskService(Service):
    name = "task_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        try:
            if self.settings_service.settings.celery_enabled:
                status = check_celery_availability()

                use_celery = status.get("availability") is not None
            else:
                use_celery = False
        except ImportError:
            use_celery = False

        self.use_celery = use_celery
        self.backend = self.get_backend()

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def get_backend(self) -> TaskBackend:
        if self.use_celery:
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
            msg = f"Task function {task_func} does not have an apply method"
            raise ValueError(msg)
        task = task_func.apply(args=args, kwargs=kwargs)

        result = task.get()
        # if result is coroutine
        if isinstance(result, Coroutine):
            result = await result
        return task.id, result

    async def launch_task(self, task_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        logger.debug(f"Launching task {task_func} with args {args} and kwargs {kwargs}")
        logger.debug(f"Using backend {self.backend}")
        task = self.backend.launch_task(task_func, *args, **kwargs)
        return await task if isinstance(task, Coroutine) else task

    def get_task(self, task_id: str) -> Any:
        return self.backend.get_task(task_id)
