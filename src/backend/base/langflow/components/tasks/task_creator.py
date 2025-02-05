"""Component for creating new tasks in the system."""

from uuid import UUID

from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, MultilineInput, Output
from langflow.schema import Data
from langflow.services.database.models.task.model import TaskCreate
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
            name="description",
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
            name="cron_expression",
            display_name="Cron Expression",
            info="Optional cron expression for scheduled tasks.",
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

        task_data = TaskCreate(
            title=self.title,
            description=self.description,
            attachments=[],  # Default empty list
            author_id=UUID(self.author_id),
            assignee_id=UUID(self.assignee_id),
            category=self.category,
            state=self.state,
            status=self.task_status,
            cron_expression=self.cron_expression if self.cron_expression else None,
        )

        result = await service.create_task(task_data)
        self.status = result
        return result
