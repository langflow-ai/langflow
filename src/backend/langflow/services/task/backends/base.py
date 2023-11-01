from abc import ABC, abstractmethod
from typing import Any, Callable


class TaskBackend(ABC):
    @abstractmethod
    def launch_task(self, task_func: Callable[..., Any], *args: Any, **kwargs: Any):
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Any:
        pass
