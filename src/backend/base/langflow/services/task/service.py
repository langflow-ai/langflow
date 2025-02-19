from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from langflow.services.base import Service
from langflow.services.task.backends.anyio import AnyIOBackend

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService
    from langflow.services.task.backends.base import TaskBackend


class TaskService(Service):
    name = "task_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        self.use_celery = False
        self.backend = self.get_backend()

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def get_backend(self) -> TaskBackend:
        return AnyIOBackend()

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
