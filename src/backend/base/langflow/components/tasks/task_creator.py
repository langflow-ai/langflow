"""Component for creating new tasks in the system."""

import asyncio
import json
from uuid import UUID

from langflow.custom import Component
from langflow.io import BoolInput, DropdownInput, IntInput, MessageTextInput, MultilineInput, Output
from langflow.schema import Data
from langflow.services.database.models.task.model import TaskCreate, TaskRead
from langflow.services.deps import get_task_orchestration_service


class TaskCreatorComponent(Component):
    display_name = "Task Creator"
    description = "Creates new tasks in the system."
    icon = "plus-square"
    name = "TaskCreator"

    inputs = [
        MessageTextInput(
            name="title",
            display_name="Title",
            info="Task title.",
            tool_mode=True,
        ),
        MultilineInput(
            name="task_description",
            display_name="Description",
            info="Task description.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="author_id",
            display_name="Author ID",
            info="UUID of the author flow.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="assignee_id",
            display_name="Assignee ID",
            info="UUID of the assignee flow.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="category",
            display_name="Category",
            info="Task category.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="state",
            display_name="State",
            info="Task state.",
            tool_mode=True,
        ),
        DropdownInput(
            name="task_status",
            display_name="Status",
            options=["pending", "processing", "failed", "completed"],
            value="pending",
            info="Task status.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="attachments",
            display_name="Attachments",
            info=(
                "List of content strings to attach to the task (e.g., blog text for content creation tasks)."
                " Provide as comma-separated values or JSON array."
            ),
            is_list=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="cron_expression",
            display_name="Cron Expression",
            info="Optional cron expression for scheduled tasks.",
            advanced=True,
            tool_mode=True,
        ),
        BoolInput(
            name="wait_for_completion",
            display_name="Wait for Completion",
            info="Wait until the task reaches 'completed' status before returning.",
            value=False,
            tool_mode=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="Maximum time to wait for task completion in seconds. Default is 300 (5 minutes).",
            value=300,
            advanced=True,
            tool_mode=True,
        ),
        IntInput(
            name="polling_interval",
            display_name="Polling Interval (seconds)",
            info="Time between status checks in seconds. Default is 5 seconds.",
            value=5,
            advanced=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Task",
            name="task",
            method="create_task",
        )
    ]

    async def create_task(self) -> Data:
        """Create a new task with the provided information."""
        service = get_task_orchestration_service()

        # Process attachments
        attachments = self._process_attachments()

        task_data = TaskCreate(
            title=self.title,
            description=self.task_description,
            attachments=attachments,
            author_id=UUID(self.author_id),
            assignee_id=UUID(self.assignee_id),
            category=self.category,
            state=self.state,
            status=self.task_status,
            cron_expression=self.cron_expression if self.cron_expression else None,
        )

        result = await service.create_task(task_data)
        # If wait_for_completion is enabled, wait for the task to complete
        if self.wait_for_completion:
            result = await self._wait_for_task_completion(result.id)

        self.status = result

        return result

    def _process_attachments(self) -> list[str]:
        """Process and validate the attachments input."""
        if not self.attachments:
            return []

        # If attachments is already a list, use it directly
        if isinstance(self.attachments, list):
            return [str(item) for item in self.attachments]

        # If it's a string, try to parse it as JSON
        if isinstance(self.attachments, str):
            try:
                # Try to parse as JSON
                parsed = json.loads(self.attachments)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                # If not valid JSON, split by comma
                return [item.strip() for item in self.attachments.split(",") if item.strip()]

        # If we couldn't process it properly, return empty list
        return []

    async def _wait_for_task_completion(self, task_id: UUID) -> TaskRead:
        """Wait for a task to reach 'completed' status or timeout."""
        service = get_task_orchestration_service()
        timeout = self.timeout
        polling_interval = self.polling_interval

        start_time = asyncio.get_event_loop().time()

        while True:
            # Check if we've exceeded the timeout
            elapsed_time = asyncio.get_event_loop().time() - start_time
            if elapsed_time > timeout:
                msg = f"Task {task_id} did not complete within {timeout} seconds"
                raise TimeoutError(msg)

            # Get the current task status
            task = await service.get_task(task_id)

            # Check if the task has completed
            if task.status == "completed":
                return task

            # Check if the task has failed
            if task.status == "failed":
                msg = f"Task {task_id} failed: {task.result}"
                raise RuntimeError(msg)

            # Wait before checking again
            await asyncio.sleep(polling_interval)
