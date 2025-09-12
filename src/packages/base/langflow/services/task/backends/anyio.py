from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any

import anyio

from langflow.services.task.backends.base import TaskBackend

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType


class AnyIOTaskResult:
    def __init__(self) -> None:
        self._status = "PENDING"
        self._result = None
        self._exception: Exception | None = None
        self._traceback: TracebackType | None = None
        self.cancel_scope: anyio.CancelScope | None = None

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

    async def run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        try:
            async with anyio.CancelScope() as scope:
                self.cancel_scope = scope
                self._result = await func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            self._exception = e
            self._traceback = e.__traceback__
        finally:
            self._status = "DONE"


class AnyIOBackend(TaskBackend):
    """Backend for handling asynchronous tasks using AnyIO."""

    name = "anyio"

    def __init__(self) -> None:
        """Initialize the AnyIO backend with an empty task dictionary."""
        self.tasks: dict[str, AnyIOTaskResult] = {}
        self._run_tasks: list[anyio.TaskGroup] = []

    async def launch_task(
        self, task_func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> tuple[str, AnyIOTaskResult]:
        """Launch a new task in an asynchronous manner.

        Args:
            task_func: The asynchronous function to run.
            *args: Positional arguments to pass to task_func.
            **kwargs: Keyword arguments to pass to task_func.

        Returns:
            tuple[str, AnyIOTaskResult]: A tuple containing the task ID and task result object.

        Raises:
            RuntimeError: If task creation fails.
        """
        try:
            task_result = AnyIOTaskResult()

            # Create task ID before starting the task
            task_id = str(id(task_result))
            self.tasks[task_id] = task_result

            # Start the task in the background using TaskGroup
            async with anyio.create_task_group() as tg:
                tg.start_soon(task_result.run, task_func, *args, **kwargs)
                self._run_tasks.append(tg)

        except Exception as e:
            msg = f"Failed to launch task: {e!s}"
            raise RuntimeError(msg) from e
        return task_id, task_result

    def get_task(self, task_id: str) -> AnyIOTaskResult | None:
        """Retrieve a task by its ID.

        Args:
            task_id: The unique identifier of the task.

        Returns:
            AnyIOTaskResult | None: The task result object if found, None otherwise.
        """
        return self.tasks.get(task_id)

    async def cleanup_task(self, task_id: str) -> None:
        """Clean up a completed task and its resources.

        Args:
            task_id: The unique identifier of the task to clean up.
        """
        if task := self.tasks.get(task_id):
            if task.cancel_scope:
                task.cancel_scope.cancel()
            self.tasks.pop(task_id, None)
