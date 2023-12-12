from typing import Any, Callable, Optional, Tuple
import anyio
from langflow.services.task.backends.base import TaskBackend
from loguru import logger


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
    def result(self) -> Any:
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
    name = "anyio"

    def __init__(self):
        self.tasks = {}

    async def launch_task(
        self, task_func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Tuple[Optional[str], Optional[AnyIOTaskResult]]:
        """
        Launch a new task in an asynchronous manner.

        Parameters:
            task_func: The asynchronous function to run.
            *args: Positional arguments to pass to task_func.
            **kwargs: Keyword arguments to pass to task_func.

        Returns:
            A tuple containing a unique task ID and the task result object.
        """
        async with anyio.create_task_group() as tg:
            try:
                task_result = AnyIOTaskResult(tg)
                tg.start_soon(task_result.run, task_func, *args, **kwargs)
                task_id = str(id(task_result))
                self.tasks[task_id] = task_result
                logger.info(f"Task {task_id} started.")
                return task_id, task_result
            except Exception as e:
                logger.error(f"An error occurred while launching the task: {e}")
                return None, None

    def get_task(self, task_id: str) -> Any:
        return self.tasks.get(task_id)
