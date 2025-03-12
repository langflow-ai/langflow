"""LangFlow Task Orchestration Service Documentation.

This module provides task orchestration functionality for LangFlow,
handling task lifecycle management and notifications using database persistence.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from loguru import logger
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.graph.graph.state_model import create_output_state_model_from_graph
from langflow.serialization.serialization import serialize
from langflow.services.base import Service
from langflow.services.database.models.actor.model import Actor
from langflow.services.database.models.task.model import Task, TaskCreate, TaskRead, TaskUpdate
from langflow.services.deps import get_chat_service, get_task_service, session_scope

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

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
    """Task orchestration service using database persistence with actual task processing."""

    name = "task_orchestration_service"

    def __init__(
        self,
        settings_service: SettingsService,
        event_bus_service: EventBusService,
    ):
        """Initialize task orchestration service with database persistence."""
        self.settings_service = settings_service
        self.event_bus_service = event_bus_service
        # Store references to running processing tasks
        self._processing_tasks: dict[UUID, asyncio.Task[Any]] = {}
        self.task_service = get_task_service()
        self.chat_service = get_chat_service()

    async def start(self):
        """Start the task orchestration service."""
        logger.info("Task orchestration service started (database persistence mode)")

    async def stop(self):
        """Stop the service and cancel any running tasks."""
        for task in self._processing_tasks.values():
            if not task.done():
                task.cancel()
        self._processing_tasks.clear()
        logger.info("Task orchestration service stopped")

    async def create_task(self, task_create: TaskCreate, session: AsyncSession) -> TaskRead:
        """Create a new task, publish a TaskCreated event, and automatically start processing the task.

        Args:
            task_create: Task creation data
            session: Database session

        Returns:
            Created task instance
        """
        # Create a new Task instance
        task = Task(
            id=uuid4(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            **task_create.model_dump(
                exclude={"user_author_id", "flow_author_id", "user_assignee_id", "flow_assignee_id"}
            ),
        )

        # Add to database
        session.add(task)
        await session.commit()
        await session.refresh(task)

        # Convert to TaskRead model
        task_read = TaskRead.model_validate(task)

        # Publish TaskCreated event
        await self.event_bus_service.publish("TaskCreated", task_read.model_dump())

        # Automatically start processing the task
        await self.start_task_processing(task.id, session)

        return task_read

    async def start_task_processing(self, task_id: UUID, session: AsyncSession) -> None:
        """Start processing a task and publish a TaskProcessingStarted event.

        This method schedules the task for processing by creating a background task.
        The actual processing begins asynchronously in the _process_task method.

        Args:
            task_id: Task identifier
            session: Database session
        """
        # Check if task exists
        task = await session.get(Task, task_id)
        if not task:
            msg = f"Task with id {task_id} not found"
            raise ValueError(msg)

        # Publish TaskProcessingStarted event
        task_read = TaskRead.model_validate(task)
        await self.event_bus_service.publish("TaskProcessingStarted", task_read.model_dump())

        # Create a background task for processing
        processing_task = asyncio.create_task(self._process_task(task_id))
        self._processing_tasks[task_id] = processing_task

    async def update_task(self, task_id: UUID | str, task_update: TaskUpdate, session: AsyncSession) -> TaskRead:
        """Update an existing task and publish a TaskUpdated event.

        Args:
            task_id: Task identifier
            task_update: Task update data
            session: Database session

        Returns:
            Updated task instance
        """
        if isinstance(task_id, str):
            task_id = UUID(task_id)

        # Get the task from the database
        task = await session.get(Task, task_id)
        if not task:
            msg = f"Task with id {task_id} not found"
            raise ValueError(msg)

        # Update task fields
        update_data = task_update.model_dump(
            exclude_unset=True, exclude={"user_author_id", "flow_author_id", "user_assignee_id", "flow_assignee_id"}
        )

        # Make sure the result field is JSON serializable
        if "result" in update_data and update_data["result"] is not None:
            update_data["result"] = serialize(update_data["result"])

        for key, value in update_data.items():
            setattr(task, key, value)

        # Update the updated_at timestamp
        task.updated_at = datetime.now(timezone.utc)

        # Save changes to database
        await session.commit()
        await session.refresh(task)

        # If status is changing to processing, start processing the task
        if task_update.status == "processing" and task_id not in self._processing_tasks:
            # Create a background task for processing
            processing_task = asyncio.create_task(self._process_task(task_id))
            self._processing_tasks[task_id] = processing_task

        # Convert to TaskRead model
        task_read = TaskRead.model_validate(task)

        # Publish TaskUpdated event
        await self.event_bus_service.publish("TaskUpdated", task_read.model_dump())

        return task_read

    async def get_task(self, task_id: UUID | str, session: AsyncSession) -> TaskRead:
        """Retrieve a task by ID.

        Args:
            task_id: Task identifier
            session: Database session

        Returns:
            Task instance
        """
        if isinstance(task_id, str):
            task_id = UUID(task_id)

        # Get the task from the database
        task = await session.get(Task, task_id)
        if not task:
            msg = f"Task with id {task_id} not found"
            raise ValueError(msg)

        return TaskRead.model_validate(task)

    async def get_tasks_for_flow(self, flow_id: str | UUID, session: AsyncSession) -> list[TaskRead]:
        """Get all tasks associated with a flow.

        Args:
            flow_id: Flow identifier
            session: Database session

        Returns:
            List of task instances
        """
        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)

        # Query tasks from the database
        query = select(Task).where(Task.assignee_id == flow_id)
        result = await session.exec(query)
        tasks = result.all()

        return [TaskRead.model_validate(task) for task in tasks]

    async def delete_task(self, task_id: UUID | str, session: AsyncSession) -> None:
        """Delete a task by ID.

        Args:
            task_id: Task identifier
            session: Database session
        """
        if isinstance(task_id, str):
            task_id = UUID(task_id)

        # Get the task from the database
        task = await session.get(Task, task_id)
        if not task:
            msg = f"Task with id {task_id} not found"
            raise ValueError(msg)

        # Cancel any running processing task
        if task_id in self._processing_tasks:
            processing_task = self._processing_tasks[task_id]
            if not processing_task.done():
                processing_task.cancel()
            del self._processing_tasks[task_id]

        # Delete the task from the database
        await session.delete(task)
        await session.commit()

    async def _process_task(self, task_id: UUID):
        """Process a task asynchronously using the graph processor.

        This implementation processes the task by:
        1. Updating the task status to "processing" (which publishes a TaskUpdated event)
        2. Building and preparing the graph
        3. Creating an output state model to track output states
        4. Running the graph asynchronously
        5. Collecting results and output states

        Args:
            task_id: Task identifier
        """
        # Get initial task data in its own session scope
        flow_data = None
        user_id = None
        task_title = None
        task_description = None
        task_attachments = None
        task_author_id = None
        task_assignee_id = None
        author_name = "Unknown"

        try:
            # Step 1: Fetch all required information in a short-lived session
            async with session_scope() as session:
                logger.info(f"Starting to process task {task_id}")

                # Update task to processing
                await self.update_task(task_id, TaskUpdate(status="processing"), session)

                # Get the task data
                task = await session.get(Task, task_id)
                if not task:
                    msg = f"Task with id {task_id} not found"
                    raise ValueError(msg)

                # Store task data to use outside this session
                task_title = task.title
                task_description = task.description
                task_attachments = task.attachments
                task_author_id = task.author_id
                task_assignee_id = task.assignee_id

                # Get the assignee actor
                assignee_actor = await session.get(Actor, task_assignee_id)
                if not assignee_actor:
                    msg = f"Actor with id {task_assignee_id} not found"
                    raise ValueError(msg)

                # Get the flow entity from the actor
                flow = await assignee_actor.get_entity(session)
                if not flow or assignee_actor.entity_type != "flow":
                    msg = f"Flow entity not found for actor {task_assignee_id}"
                    raise ValueError(msg)

                # Store flow data to use outside this session
                flow_data = flow.data
                flow_id = flow.id
                user_id = flow.user_id

                # Get the author actor for additional context
                author_actor = await session.get(Actor, task_author_id)
                if author_actor:
                    author_name = await author_actor.get_name(session) or "Unknown"

            # Step 2: Process the task with the collected data
            if not flow_data:
                logger.error(f"Task {task_id} has no flow_data")
                msg = "No flow data provided for task processing"
                raise ValueError(msg)

            input_value = f"""You are a task processing agent. Your job is to complete the following task:

Task Title: {task_title}
Task Description: {task_description}
Task Author: {author_name} (ID: {task_author_id})
Task Attachments: {task_attachments}
Your ID: {task_assignee_id}

Please process this task according to the description and provide a complete response.
Focus on addressing all requirements in the task description."""

            input_value_request = {"input_value": input_value, "session": str(task_id)}

            from langflow.api.utils import build_graph_from_data

            # Build the graph outside the session scope
            logger.debug(f"Building graph for task {task_id}")
            graph = await build_graph_from_data(
                flow_id=str(task_id),
                payload=flow_data,
                user_id=str(user_id),
                flow_name=task_title or "Untitled Flow",
            )

            # Set session_id from input_request if available
            if input_value_request and "session" in input_value_request:
                session_id = input_value_request.get("session")
                if session_id:
                    logger.debug(f"Setting session_id {session_id} for task {task_id}")
                    graph.session_id = session_id

                    # Also set session_id on all Agent components in the graph
                    for vertex in graph.vertices:
                        if "Agent" in vertex.vertex_type:
                            logger.debug(f"Setting session_id on Agent component {vertex.id}")
                            if hasattr(vertex, "set") and callable(vertex.set):
                                # Set session_id, sender and sender_name
                                sender = input_value_request.get("sender", "Machine")
                                sender_name = input_value_request.get("sender_name", "Agent")
                                vertex.set(session_id=session_id, sender=sender, sender_name=sender_name)
                else:
                    logger.warning(f"Empty session_id provided for task {task_id}")
            else:
                # Use the task_id as fallback
                logger.debug(f"No session_id in input_request, using task_id for task {task_id}")
                graph.session_id = str(task_id)

            # Create input value request and set it in the graph
            input_value = input_value_request.get("input_value", "")
            logger.debug(f"Input value for task {task_id}: {input_value}")

            # Prepare the graph for processing
            logger.debug(f"Preparing graph for task {task_id}")
            graph.prepare()

            # Create output state model for tracking
            output_state_model = create_output_state_model_from_graph(graph)()

            # Process the graph
            logger.info(f"Starting graph execution for task {task_id}")
            results = []

            # Run the graph and collect results
            async for result in graph.async_start(inputs=input_value_request, attachments=task_attachments):
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
                logger.debug(f"No explicit outputs for task {task_id}, using output state model")
                # If no explicit outputs, get the output state model
                results = [{"output_state": output_state_model.model_dump(), "type": "output_state"}]

            logger.info(f"Task {task_id} completed successfully with {len(results)} results")

            # Update task status in a new session
            async with session_scope() as session:
                # Make sure results are serializable
                serializable_results = serialize({"outputs": results})

                # Update the task with results
                await self.update_task(
                    task_id,
                    TaskUpdate(
                        status="completed",
                        result=serializable_results,
                    ),
                    session,
                )

                # Publish completion event
                await self.event_bus_service.publish(
                    "TaskCompleted",
                    {
                        "task_id": str(task_id),
                        "flow_id": str(flow_id),
                        "result": serialize(results),
                    },
                )

        except asyncio.CancelledError:
            logger.info(f"Task {task_id} was cancelled")
            async with session_scope() as session:
                await self.update_task(task_id, TaskUpdate(status="cancelled"), session)
            raise

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error in task processing {task_id}: {e!s}")
            error_message = str(e)

            try:
                async with session_scope() as session:
                    await self.update_task(
                        task_id,
                        TaskUpdate(
                            status="failed",
                            result={"error": f"Error processing task: {error_message}"},
                        ),
                        session,
                    )

                    # If we have flow_id, publish failure event
                    if "flow_id" in locals() and flow_id is not None:
                        await self.event_bus_service.publish(
                            "TaskFailed",
                            {
                                "task_id": str(task_id),
                                "flow_id": str(flow_id),
                                "error": error_message,
                            },
                        )
            except Exception as update_error:  # noqa: BLE001
                logger.error(f"Error updating failed task {task_id}: {update_error}")

    async def _build_vertex(
        self,
        vertex_id: str,
        graph: Graph,
        event_manager: EventManager,
        inputs: InputValueRequest | dict,
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
                inputs_dict=inputs,
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
