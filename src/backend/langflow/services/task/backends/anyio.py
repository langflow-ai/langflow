from typing import Any, Callable, Tuple
import anyio
from langflow.services.task.backends.base import TaskBackend


class AnyIOTaskResult:
    def __init__(self, scope):
        self._scope = scope
        self._status = "PENDING"
        self._result = None
        self._exception = None

    @property
    def status(self) -> str:
        if self._status == "DONE":
            return "FAILURE" if self._exception is not None else "SUCCESS"
        return self._status

    @property
    def result(self) -> any:
        return self._result

    def ready(self) -> bool:
        return self._status == "DONE"

    async def run(self, func, *args, **kwargs):
        try:
            self._result = await func(*args, **kwargs)
        except Exception as e:
            self._exception = e
        finally:
            self._status = "DONE"


class AnyIOBackend(TaskBackend):
    def __init__(self):
        self.tasks = {}

    async def launch_task(
        self, task_func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Tuple[str, AnyIOTaskResult]:  # sourcery skip: remove-unnecessary-cast
        async with anyio.create_task_group() as tg:
            task_result = AnyIOTaskResult(tg)
            await tg.spawn(task_result.run, task_func, *args, **kwargs)
            task_id = str(id(task_result))
            self.tasks[task_id] = task_result
            return task_id, task_result

    def get_task(self, task_id: int) -> AnyIOTaskResult:
        return self.tasks.get(task_id)
