from abc import ABC, abstractmethod
from typing import Any, Callable, Union


class TaskBackend(ABC):
    @abstractmethod
    def launch_task(
        self, task_func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Union[int, str]:
        pass

    @abstractmethod
    def get_task(self, task_id: Union[int, str]) -> Any:
        pass
