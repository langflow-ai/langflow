import traceback
from collections.abc import Callable
from typing import Any

import anyio
from loguru import logger

from langflow.services.task.backends.base import TaskBackend


class AnyIOTaskResult:
    def __init__(self, scope) -> None:
        self._scope = scope
        self._status = "PENDING"
        self._result = None
        self._exception: Exception | None = None

    @property
    def status(self) -> str:
        if self._status == "DONE":
            return "FAILURE" if self._exception is not None else "SUCCESS"
        return self._status

    @property
    def traceback(self) -> str:
        if self._traceback is not None:
            return "".join(traceback.format_tb(self._traceback))
        return ""

    @property
    def result(self) -> Any:
        return self._result

    def ready(self) -> bool:
        return self._status == "DONE"

    async def run(self, func, *args, **kwargs) -> None:
        try:
            self._result = await func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            self._exception = e
            self._traceback = e.__traceback__
        finally:
            self._status = "DONE"


class AnyIOBackend(TaskBackend):
    name = "anyio"

    def __init__(self) -> None:
        self.tasks: dict[str, AnyIOTaskResult] = {}

    async def launch_task(
        self, task_func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> tuple[str | None, AnyIOTaskResult | None]:
        """Launch a new task in an asynchronous manner.

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
            except Exception:  # noqa: BLE001
                logger.exception("An error occurred while launching the task")
                return None, None

            task_id = str(id(task_result))
            self.tasks[task_id] = task_result
            logger.info(f"Task {task_id} started.")
            return task_id, task_result

    def get_task(self, task_id: str) -> Any:
        return self.tasks.get(task_id)
