"""LangFlow Task Orchestration Service Documentation.

This module provides a simplified task orchestration functionality for LangFlow,
handling task lifecycle management and notifications using in-memory storage.
"""

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from loguru import logger
from pydantic import BaseModel

from langflow.services.base import Service
from langflow.services.database.models.task.model import TaskCreate, TaskRead, TaskUpdate

if TYPE_CHECKING:
    from langflow.services.event_bus.service import EventBusService
    from langflow.services.settings.service import SettingsService


class TaskNotification(BaseModel):
    """Represents a notification about task state changes."""

    task_id: str
    flow_id: str
    event_type: str
    category: str
    state: str
    status: str
    flow_data: dict[str, Any] | None = None
    input_request: dict[str, Any] | None = None


class TaskOrchestrationService(Service):
    """Simplified task orchestration service using in-memory storage."""

    name = "task_orchestration_service"

    def __init__(
        self,
        settings_service: "SettingsService",
        event_bus_service: "EventBusService",
    ):
        """Initialize task orchestration service with in-memory storage."""
        self.settings_service = settings_service
        self.event_bus_service = event_bus_service
        self._tasks: dict[UUID, dict[str, Any]] = {}  # In-memory task storage
        self._processing_tasks: dict[UUID, asyncio.Task[Any]] = {}

    async def start(self):
        """Start the task orchestration service."""
        logger.info("Task orchestration service started (in-memory mode)")

    async def stop(self):
        """Stop the service and cancel any running tasks."""
        for task in self._processing_tasks.values():
            if not task.done():
                task.cancel()
        self._processing_tasks.clear()
        logger.info("Task orchestration service stopped")

    async def create_task(self, task_create: TaskCreate) -> TaskRead:
        """Create a new task and publish a TaskCreated event.

        Args:
            task_create: Task creation data

        Returns:
            Created task instance
        """
        task_id = uuid4()
        task_data = {
            "id": task_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            **task_create.model_dump(),
        }

        self._tasks[task_id] = task_data
        task_read = TaskRead.model_validate(task_data)

        # Publish TaskCreated event
        await self.event_bus_service.publish("TaskCreated", task_read.model_dump())

        return task_read

    async def start_task_processing(self, task_id: UUID) -> None:
        """Start processing a task.

        Args:
            task_id: Task identifier
        """
        if task_id not in self._tasks:
            msg = f"Task with id {task_id} not found"
            raise ValueError(msg)

        # Create a background task for processing
        processing_task = asyncio.create_task(self._process_task(task_id))
        self._processing_tasks[task_id] = processing_task

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

        if task_id not in self._tasks:
            msg = f"Task with id {task_id} not found"
            raise ValueError(msg)

        task_data = self._tasks[task_id]
        task_data.update(task_update.model_dump(exclude_unset=True))
        task_data["updated_at"] = datetime.now(timezone.utc)

        task_read = TaskRead.model_validate(task_data)
        await self.event_bus_service.publish("TaskUpdated", task_read.model_dump())
        return task_read

    async def get_task(self, task_id: UUID | str) -> TaskRead:
        """Retrieve a task by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task instance
        """
        if isinstance(task_id, str):
            task_id = UUID(task_id)

        if task_id not in self._tasks:
            msg = f"Task with id {task_id} not found"
            raise ValueError(msg)

        return TaskRead.model_validate(self._tasks[task_id])

    async def get_tasks_for_flow(self, flow_id: str | UUID) -> list[TaskRead]:
        """Get all tasks associated with a flow.

        Args:
            flow_id: Flow identifier

        Returns:
            List of task instances
        """
        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)

        return [
            TaskRead.model_validate(task_data)
            for task_data in self._tasks.values()
            if task_data.get("author_id") == flow_id
        ]

    async def delete_task(self, task_id: UUID | str) -> None:
        """Delete a task by ID.

        Args:
            task_id: Task identifier
        """
        if isinstance(task_id, str):
            task_id = UUID(task_id)

        if task_id not in self._tasks:
            msg = f"Task with id {task_id} not found"
            raise ValueError(msg)

        # Cancel any running processing task
        if task_id in self._processing_tasks:
            task = self._processing_tasks[task_id]
            if not task.done():
                task.cancel()
            del self._processing_tasks[task_id]

        del self._tasks[task_id]

    async def _process_task(self, task_id: UUID):
        """Process a task asynchronously.

        This is a simplified version that simulates task processing.
        In a real implementation, this would handle the actual task execution.

        Args:
            task_id: Task identifier
        """
        try:
            # Update task to processing
            await self.update_task(task_id, TaskUpdate(status="processing"))

            # Simulate some work
            await asyncio.sleep(2)

            # Get the task data
            task_data = self._tasks[task_id]

            try:
                # Here you would actually process the task
                # For now, we just simulate success
                result = {"message": "Task completed successfully"}

                # Update task as completed
                await self.update_task(
                    task_id,
                    TaskUpdate(
                        status="completed",
                        result=result,
                    ),
                )

                # Publish completion event
                await self.event_bus_service.publish(
                    "TaskCompleted",
                    {
                        "task_id": str(task_id),
                        "flow_id": str(task_data.get("flow_id")),
                        "result": result,
                    },
                )

            except ValueError as e:
                # Handle any processing errors
                error_result = {"error": str(e)}
                await self.update_task(
                    task_id,
                    TaskUpdate(
                        status="failed",
                        result=error_result,
                    ),
                )

                # Publish failure event
                await self.event_bus_service.publish(
                    "TaskFailed",
                    {
                        "task_id": str(task_id),
                        "flow_id": str(task_data.get("flow_id")),
                        "error": str(e),
                    },
                )

        except asyncio.CancelledError:
            # Handle task cancellation
            await self.update_task(task_id, TaskUpdate(status="cancelled"))
            raise
        except ValueError as e:
            logger.error(f"Error processing task {task_id}: {e}")
            # Ensure task is marked as failed
            try:
                await self.update_task(
                    task_id,
                    TaskUpdate(
                        status="failed",
                        result={"error": f"Error processing task: {e!s}"},
                    ),
                )
            except ValueError as update_error:
                logger.error(f"Error updating failed task {task_id}: {update_error}")
