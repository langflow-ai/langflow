"""LangFlow Task Orchestration Service Documentation.

This module provides the core task orchestration functionality for LangFlow,
handling task lifecycle management, notifications, and processing using Celery.

Table of Contents:
1. Imports
2. TaskNotification Model
3. Database URL Helper
4. Logging Utilities
5. Subscription Management
6. TaskOrchestrationService Class
   - Initialization
   - Service Lifecycle
   - Task CRUD Operations
   - Notification System
   - Subscription Management
   - Task Processing
"""

import asyncio
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger
from pydantic import BaseModel, field_validator
from sqlmodel import select

from langflow.services.base import Service
from langflow.services.database.models.subscription.model import Subscription
from langflow.services.database.models.task.model import Task, TaskCreate, TaskRead, TaskUpdate
from langflow.services.database.service import DatabaseService

if TYPE_CHECKING:
    from langflow.services.event_bus.service import EventBusService
    from langflow.services.settings.service import SettingsService


class TaskNotification(BaseModel):
    """Represents a notification about task state changes.

    Attributes:
        task_id: Unique identifier of the task
        flow_id: Associated flow identifier
        event_type: Type of event (e.g., 'task_created')
        category: Task category
        state: Current task state
        status: Current task status
        flow_data: Optional flow execution data
        input_request: Optional input request data
    """

    task_id: str
    flow_id: str
    event_type: str
    category: str
    state: str
    status: str
    flow_data: dict | None = None
    input_request: dict | None = None

    @field_validator("task_id", "flow_id", mode="before")
    @classmethod
    def validate_str(cls, value: str) -> str:
        """Validate and convert string values to proper format."""
        try:
            return str(value)
        except ValueError as exc:
            msg = f"Invalid UUID: {value}"
            raise ValueError(msg) from exc


def add_tasks_to_database_url(database_url: str) -> str:
    """Modify database URL to create a separate database for tasks.

    Args:
        database_url: Original database connection URL

    Returns:
        Modified database URL with task-specific suffix
    """
    if database_url.startswith("sqlite://"):
        parts = database_url.rsplit(".", 1)
        return f"{parts[0]}-tasks.{parts[1]}" if len(parts) > 1 else f"{database_url}-tasks"
    if database_url.startswith(("postgresql://", "mysql://")):
        if "?" in database_url:
            base_url, params = database_url.split("?", 1)
            return f"{base_url}_tasks?{params}"
        return f"{database_url}_tasks"
    return database_url


# Define an asynchronous helper for non-blocking stream reading.
async def _async_log_stream(stream: asyncio.StreamReader, log_func: Callable) -> None:
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            log_func(line.decode().rstrip())
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error reading from stream: {e}")


async def get_subscriptions(db_service: DatabaseService, task: TaskRead):
    """Retrieve subscriptions matching task category and state.

    Args:
        db_service: Database service instance
        task: Task to match subscriptions against

    Returns:
        List of matching subscriptions
    """
    async with db_service.with_session() as session:
        result = await session.exec(
            select(Subscription).filter(
                ((Subscription.category == task.category) & (Subscription.state == task.state))
                | ((Subscription.category.is_(None)) & (Subscription.state.is_(None)))
            )
        )
        return result.all()


class TaskOrchestrationService(Service):
    """Core task orchestration service handling task lifecycle and processing."""

    name = "task_orchestration_service"

    def __init__(
        self,
        settings_service: "SettingsService",
        db_service: "DatabaseService",
        event_bus_service: "EventBusService",
    ):
        """Initialize task orchestration service.

        Args:
            settings_service: Application settings service
            db_service: Database service instance
            event_bus_service: Event bus service instance
        """
        self.settings_service = settings_service
        self.db: DatabaseService = db_service
        add_tasks_to_database_url(self.db.database_url)
        self.external_celery = settings_service.settings.external_celery
        self._celery_worker_proc = None
        self._celery_worker_proc_stdout = None
        self._celery_worker_proc_stderr = None
        self.event_bus_service = event_bus_service

    async def start(self):
        """Start the task orchestration service.

        If using internal Celery, spawns a worker process and sets up asynchronous logging using non-blocking I/O.
        For external Celery, verifies worker availability.
        """
        if not self.external_celery:
            python_executable = sys.executable
            # Start the Celery worker process asynchronously with non-blocking stdout/stderr.
            self._celery_worker_proc = await asyncio.create_subprocess_exec(
                python_executable,
                "-m",
                "celery",
                "-A",
                "langflow.worker.celery_app",
                "worker",
                "--loglevel=info",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Schedule asynchronous tasks to log the worker's stdout and stderr.
            self._celery_worker_proc_stdout = asyncio.create_task(
                _async_log_stream(self._celery_worker_proc.stdout, logger.info)
            )
            self._celery_worker_proc_stderr = asyncio.create_task(
                _async_log_stream(self._celery_worker_proc.stderr, logger.error)
            )

            # Allow some time for the worker to initialize.
            await asyncio.sleep(10)
            if self._celery_worker_proc.returncode is not None and self._celery_worker_proc.returncode != 0:
                msg = f"Celery worker failed to start with return code {self._celery_worker_proc.returncode}"
                raise RuntimeError(msg)
        else:
            from langflow.core.celery_app import celery_app

            # Ping the external Celery worker using a thread to avoid blocking.
            ping_response = await asyncio.to_thread(celery_app.control.ping, timeout=5.0)
            if not ping_response:
                logger.warning("No response from the external celery worker; please check its status.")
            else:
                logger.info(f"External celery worker responded: {ping_response}")

    async def stop(self):
        """Stop the service and terminate any running Celery worker."""
        if self._celery_worker_proc:
            self._celery_worker_proc.terminate()
            import asyncio

            try:
                await asyncio.wait_for(self._celery_worker_proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                self._celery_worker_proc.kill()
            self._celery_worker_proc = None

    async def create_task(self, task_create: TaskCreate) -> TaskRead:
        """Create a new task and publish a TaskCreated event.

        Args:
            task_create: Task creation data

        Returns:
            Created task instance
        """
        task = Task.model_validate(task_create, from_attributes=True)
        task.status = "pending"
        async with self.db.with_session() as session:
            session.add(task)
            await session.commit()
            await session.refresh(task)

        task_read = TaskRead.model_validate(task, from_attributes=True)
        # Publish TaskCreated event
        await self.event_bus_service.publish("TaskCreated", task_read.model_dump())
        return task_read

    async def update_task(self, task_id: UUID | str, task_update: TaskUpdate) -> TaskRead:
        """Update an existing task and publish a TaskUpdated event.

        Args:
            task_id: Task identifier
            task_update: Task update data

        Returns:
            Updated task instance
        """
        if isinstance(task_id, str):
            task_id = UUID(task_id)
        async with self.db.with_session() as session:
            task = (await session.exec(select(Task).where(Task.id == task_id))).first()
            if not task:
                msg = f"Task with id {task_id} not found"
                raise ValueError(msg)

            for key, value in task_update.model_dump(exclude_unset=True).items():
                setattr(task, key, value)

            await session.commit()
            await session.refresh(task)
        task_read = TaskRead.model_validate(task, from_attributes=True)

        # Publish TaskUpdated event
        await self.event_bus_service.publish("TaskUpdated", task_read.model_dump())
        return task_read

    async def get_task(self, task_id: str | UUID) -> TaskRead:
        """Retrieve a task by ID.

        Args:
            task_id: Task identifier (string or UUID)

        Returns:
            TaskRead: The task instance.

        Raises:
            ValueError: If the task is not found.
        """
        if isinstance(task_id, str):
            task_id = UUID(task_id)
        async with self.db.with_session() as session:
            task = (await session.exec(select(Task).where(Task.id == task_id))).first()
            if not task:
                msg = f"Task with id {task_id} not found"
                raise ValueError(msg)
        return TaskRead.model_validate(task, from_attributes=True)

    async def get_tasks_for_flow(self, flow_id: str | UUID) -> list[TaskRead]:
        """Get all tasks associated with a flow.

        Args:
            flow_id: Flow identifier (string or UUID)

        Returns:
            list[TaskRead]: List of task instances associated with the flow.
        """
        async with self.db.with_session() as session:
            tasks = (await session.exec(select(Task).where(Task.author_id == flow_id))).all()
        return [TaskRead.model_validate(task, from_attributes=True) for task in tasks]

    async def delete_task(self, task_id: UUID | str) -> None:
        """Delete a task by ID.

        Args:
            task_id: Task identifier (string or UUID)

        Raises:
            ValueError: If the task is not found.
        """
        if isinstance(task_id, str):
            task_id = UUID(task_id)
        async with self.db.with_session() as session:
            task = (await session.exec(select(Task).where(Task.id == task_id))).first()
            if not task:
                msg = f"Task with id {task_id} not found"
                raise ValueError(msg)
            await session.delete(task)
            await session.commit()
