"""LangFlow Task Orchestration Service Documentation.

This module provides a simplified task orchestration functionality for LangFlow,
handling task lifecycle management and notifications using in-memory storage.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from loguru import logger
from pydantic import BaseModel

from langflow.graph.graph.state_model import create_output_state_model_from_graph
from langflow.services.base import Service
from langflow.services.database.models.task.model import TaskCreate, TaskRead, TaskUpdate
from langflow.services.deps import get_chat_service, get_task_service

if TYPE_CHECKING:
    from langflow.api.v1.schemas import InputValueRequest
    from langflow.events.event_manager import EventManager
    from langflow.graph import Graph
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
    """Task orchestration service using in-memory storage with actual task processing."""

    name = "task_orchestration_service"

    def __init__(
        self,
        settings_service: SettingsService,
        event_bus_service: EventBusService,
    ):
        """Initialize task orchestration service with in-memory storage."""
        self.settings_service = settings_service
        self.event_bus_service = event_bus_service
        self._tasks: dict[UUID, dict[str, Any]] = {}  # In-memory task storage
        self._processing_tasks: dict[UUID, asyncio.Task[Any]] = {}
        self.task_service = get_task_service()
        self.chat_service = get_chat_service()

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
        """Process a task asynchronously using the graph processor.

        This implementation processes the task by:
        1. Building and preparing the graph
        2. Creating an output state model to track output states
        3. Running the graph asynchronously
        4. Collecting results and output states

        Args:
            task_id: Task identifier
        """
        from langflow.api.utils import build_graph_from_data

        try:
            # Update task to processing
            await self.update_task(task_id, TaskUpdate(status="processing"))

            # Get the task data
            task_data = self._tasks[task_id]
            flow_data = task_data.get("flow_data")
            input_request = task_data.get("input_request", {})

            if not flow_data:
                msg = "No flow data provided for task processing"
                raise ValueError(msg)

            try:
                # Build the graph
                graph = await build_graph_from_data(
                    flow_id=str(task_id),
                    payload=flow_data,
                    user_id=str(task_data.get("author_id")),
                    flow_name=task_data.get("title", "Untitled Flow"),
                )

                # Create input value request and set it in the graph
                input_request.get("input_value", "")

                # Prepare the graph for processing
                graph.prepare()

                # Create output state model for tracking
                output_state_model = create_output_state_model_from_graph(graph)()

                # Process the graph
                results = []
                async for result in graph.async_start():
                    if hasattr(result, "vertex") and result.vertex.is_output:
                        # Get the output state for this vertex
                        vertex_state = getattr(output_state_model, result.vertex.id, None)
                        results.append(
                            {
                                "id": result.vertex.id,
                                "type": result.vertex.vertex_type,
                                "value": result.vertex.built_object,
                                "output_state": vertex_state.model_dump() if vertex_state else None,
                            }
                        )

                if not results:
                    # If no explicit outputs, get the output state model
                    results = [{"output_state": output_state_model.model_dump(), "type": "output_state"}]

                # Update task as completed
                await self.update_task(
                    task_id,
                    TaskUpdate(
                        status="completed",
                        result={"outputs": results},
                    ),
                )

                # Publish completion event
                await self.event_bus_service.publish(
                    "TaskCompleted",
                    {
                        "task_id": str(task_id),
                        "flow_id": str(task_data.get("flow_id")),
                        "result": results,
                    },
                )

            except Exception as e:  # noqa: BLE001
                logger.error(f"Error processing graph: {e!s}")
                error_result = {"error": str(e)}

                # Update task as failed
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
            logger.info(f"Task {task_id} was cancelled")
            await self.update_task(task_id, TaskUpdate(status="cancelled"))
            raise

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error in task processing: {e!s}")
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

    async def _build_vertex(
        self,
        vertex_id: str,
        graph: Graph,
        event_manager: EventManager,
        inputs: InputValueRequest,
    ) -> None:
        """Build a single vertex and handle its downstream effects.

        Args:
            vertex_id: The ID of the vertex to build
            graph: The graph instance
            event_manager: Event manager for this task
            inputs: Input values for the vertex
        """
        try:
            # Build the vertex
            vertex_build_result = await graph.build_vertex(
                vertex_id=vertex_id,
                user_id=str(graph.user_id),
                inputs_dict=inputs.model_dump(),
                get_cache=self.chat_service.get_cache,
                set_cache=self.chat_service.set_cache,
                event_manager=event_manager,
            )

            if vertex_build_result.valid:
                # Get next vertices to process
                async with self.chat_service.async_cache_locks[str(graph.id)]:
                    next_vertices = await graph.get_next_runnable_vertices(
                        self.chat_service.async_cache_locks[str(graph.id)],
                        vertex=graph.get_vertex(vertex_id),
                        cache=False,
                    )

                # Process next vertices
                if next_vertices:
                    tasks = []
                    for next_vertex_id in next_vertices:
                        task = asyncio.create_task(
                            self._build_vertex(
                                vertex_id=next_vertex_id,
                                graph=graph,
                                event_manager=event_manager,
                                inputs=inputs,
                            )
                        )
                        tasks.append(task)
                    await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"Error building vertex {vertex_id}: {e!s}")
            raise
