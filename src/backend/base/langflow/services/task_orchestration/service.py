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
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from diskcache import Cache, Deque
from loguru import logger
from pydantic import BaseModel, field_validator
from sqlmodel import select

from langflow.services.base import Service
from langflow.services.database.models.subscription.model import Subscription
from langflow.services.database.models.task.model import Task, TaskCreate, TaskRead, TaskUpdate
from langflow.services.database.service import DatabaseService

if TYPE_CHECKING:
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


async def log_stream(stream: asyncio.StreamReader, log_func: Callable) -> None:
    """Asynchronously read and log stream output.

    Args:
        stream: Stream to read from
        log_func: Logging function to use
    """
    while True:
        line = await stream.readline()
        if not line:
            break
        log_func(line.decode().rstrip())


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
    """Core task orchestration service handling task lifecycle and processing.

    Attributes:
        name: Service name identifier
        cache: Disk-based cache for task data
        notification_queue: Queue for task notifications
        db: Database service instance
        external_celery: Flag indicating external Celery usage
    """

    name = "task_orchestration_service"

    def __init__(
        self,
        settings_service: "SettingsService",
        db_service: "DatabaseService",
    ):
        """Initialize task orchestration service.

        Args:
            settings_service: Application settings service
            db_service: Database service instance
        """
        cache_dir = Path(settings_service.settings.config_dir) / "task_orchestrator"
        self.cache = Cache(cache_dir)
        self.notification_queue = Deque(directory=f"{cache_dir}/notifications")
        self.db: DatabaseService = db_service
        add_tasks_to_database_url(self.db.database_url)
        self.external_celery = settings_service.settings.external_celery
        self._celery_worker_proc = None
        self._celery_worker_proc_stdout = None
        self._celery_worker_proc_stderr = None

    async def start(self):
        """Start the task orchestration service.

        If using internal Celery, spawns worker process and sets up logging.
        For external Celery, verifies worker availability.
        """
        if not self.external_celery:
            python_executable = sys.executable
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

            self._celery_worker_proc_stdout = asyncio.create_task(
                log_stream(self._celery_worker_proc.stdout, logger.info)
            )
            self._celery_worker_proc_stderr = asyncio.create_task(
                log_stream(self._celery_worker_proc.stderr, logger.error)
            )

            await asyncio.sleep(10)
            if self._celery_worker_proc.returncode is not None and self._celery_worker_proc.returncode != 0:
                msg = f"Celery worker failed to start with return code {self._celery_worker_proc.returncode}"
                raise RuntimeError(msg)
        else:
            from langflow.core.celery_app import celery_app

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
        """Create a new task.

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
        await self._notify(task_read, "task_created")
        self._schedule_task(task_read)
        return task_read

    async def update_task(self, task_id: UUID | str, task_update: TaskUpdate) -> TaskRead:
        """Update an existing task.

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
                if key == "status":
                    setattr(task, key, value)
                else:
                    setattr(task, key, value)

                await session.commit()
                await session.refresh(task)
        task_read = TaskRead.model_validate(task, from_attributes=True)
        await self._notify(task_read, "task_updated")
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

    async def _notify(self, task: TaskRead, event_type: str) -> None:
        """Send notifications about task events.

        Args:
            task (TaskRead): The task that triggered the notification
            event_type (str): The type of event (e.g., "task_created", "task_updated")
        """
        self._add_notification(task, event_type, task.assignee_id)

        # Notify subscribers
        subscriptions = await get_subscriptions(self.db, task)
        for subscription in subscriptions:
            self._add_notification(task, event_type, subscription.flow_id)

    def _add_notification(self, task: TaskRead, event_type: str, flow_id: str) -> None:
        """Add a notification to the queue.

        Args:
            task: Task that triggered the notification
            event_type: The type of event (e.g., "task_created", "task_updated")
            flow_id: The ID of the flow to notify
        """
        notification = TaskNotification(
            task_id=task.id,
            event_type=event_type,
            flow_id=flow_id,
            category=task.category,
            state=task.state,
            status=task.status,
            input_request=task.input_request,
        )
        self.notification_queue.append(notification.model_dump())

    def get_notifications(self) -> list[TaskNotification]:
        """Get all notifications from the queue.

        Returns:
            list[TaskNotification]: List of notifications.
        """
        notifications = []
        while self.notification_queue:
            notifications.append(TaskNotification(**self.notification_queue.popleft()))
        return notifications

    async def subscribe_flow(
        self, flow_id: str, event_type: str, category: str | None = None, state: str | None = None
    ) -> None:
        """Subscribe a flow to task events.

        Args:
            flow_id (str): The ID of the flow to subscribe
            event_type (str): The type of event to subscribe to
            category (str | None, optional): Filter by task category. Defaults to None.
            state (str | None, optional): Filter by task state. Defaults to None.
        """
        subscription = Subscription(flow_id=UUID(flow_id), event_type=event_type, category=category, state=state)
        async with self.db.with_session() as session:
            session.add(subscription)
            await session.commit()
            await session.refresh(subscription)

    async def unsubscribe_flow(
        self, flow_id: str, event_type: str, category: str | None = None, state: str | None = None
    ) -> None:
        """Unsubscribe a flow from task events.

        Args:
            flow_id (str): The ID of the flow to unsubscribe
            event_type (str): The type of event to unsubscribe from
            category (str | None, optional): Filter by task category. Defaults to None.
            state (str | None, optional): Filter by task state. Defaults to None.
        """
        async with self.db.with_session() as session:
            query = select(Subscription).where(
                Subscription.flow_id == UUID(flow_id),
                Subscription.event_type == event_type,
                Subscription.category == category,
                Subscription.state == state,
            )
            result = await session.exec(query)
            subscription = result.first()
            if subscription:
                await session.delete(subscription)
                await session.commit()

    def _schedule_task(self, task: TaskRead) -> None:
        """Schedule a task using Celery.

        Args:
            task (TaskRead): The task to schedule.
        """
        # Using Celery to schedule the task instead of APScheduler
        from langflow.services.task.consumer import consume_task_celery

        consume_task_celery.delay(task.id)

    async def _process_task_logic(self, task: TaskRead) -> dict:
        """Process the task: transition from pending -> processing -> completed (or failed).

        This function encapsulates all business logic required to process a task.
        It returns the result of the task processing.

        Args:
            task (TaskRead): The task to process

        Raises:
            ValueError: If the task is not in pending status
            Exception: If any error occurs during task processing

        Returns:
            dict: The result of the task processing
        """
        if task.status != "pending":
            msg = f"Task {task.id} is not in pending status: {task.status}"
            raise ValueError(msg)

        # Update task status to "processing"
        await self.update_task(task.id, TaskUpdate(status="processing", state=task.state))

        try:
            # Perform task processing logic here
            result = self._process_task(task)

            # Update task with result and set status to "completed"
            await self.update_task(task.id, TaskUpdate(status="completed", state=task.state, result=result))
        except Exception as e:
            # If an error occurs, update task status to "failed"
            error_result = {"error": str(e)}
            await self.update_task(task.id, TaskUpdate(status="failed", state=task.state, result=error_result))
            raise
        return result

    async def consume_task(self, task_id: str | UUID) -> None:
        """Retrieve the task and process it by delegating to the core business logic.

        Args:
            task_id (str | UUID): The ID of the task to process
        """
        task = await self.get_task(str(task_id))
        await self._process_task_logic(task)

    def _process_task(self, task: TaskRead) -> dict:
        """Implement task processing logic based on task category.

        This is a placeholder implementation that should be overridden
        with actual task processing logic.

        Args:
            task (TaskRead): The task to process

        Returns:
            dict: The result of processing the task
        """
        logger.info(f"Processing task {task.id}")
        return {"result": "Task processed successfully"}
