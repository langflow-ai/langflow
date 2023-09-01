import asyncio
from typing import Any, Callable, Union
import logging

from langflow.services.base import Service
from langflow.services.task.utils import AsyncIOTaskResult, get_celery_worker_status

try:
    from celery.result import AsyncResult
    from langflow.worker import celery_app

    try:
        status = get_celery_worker_status(celery_app)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        status = {"availability": None}
    USE_CELERY = status.get("availability") is not None
except ImportError:
    USE_CELERY = False


class TaskManager(Service):
    STATUS_PENDING = "PENDING"
    STATUS_FINISHED = "FINISHED"
    STATUS_UNKNOWN = "UNKNOWN"
    name = "task_manager"

    def __init__(self):
        self.tasks = {}  # For storing asyncio tasks
        self.celery_results = {}  # For storing Celery AsyncResult instances
        if USE_CELERY:
            from langflow.worker import celery_app

            self.celery_app = celery_app

        else:
            self.celery_app = None  # To store the celery app if available
        self.use_celery = USE_CELERY

    def launch_task(
        self,
        task_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Union[int, str]:
        if USE_CELERY:
            task = task_func.apply_async(args=args, kwargs=kwargs)
            self.celery_results[task.id] = task
            return task.id
        else:
            task = asyncio.create_task(task_func(*args, **kwargs))
            task_id = str(id(task))
            self.tasks[task_id] = AsyncIOTaskResult(task)

            def set_result(future):
                try:
                    self.tasks[task_id] = AsyncIOTaskResult(future)
                except Exception as e:
                    logging.error(f"An error occurred: {e}")

            task.add_done_callback(set_result)
            return task_id

    # Update the get_task_status function in TaskManager class
    def get_task(
        self, task_id: Union[int, str]
    ) -> Union[AsyncResult, AsyncIOTaskResult]:
        if self.use_celery:
            return AsyncResult(task_id, app=self.celery_app)
        return self.tasks.get(task_id)
