from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class TaskBackend(ABC):
    name: str

    @abstractmethod
    def launch_task(self, task_func: Callable[..., Any], *args: Any, **kwargs: Any):
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Any:
        pass
