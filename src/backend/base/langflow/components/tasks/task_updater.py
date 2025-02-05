"""Component for updating and deleting tasks."""

from uuid import UUID

from langflow.custom import Component
from langflow.io import DataInput, DropdownInput, MessageTextInput, MultilineInput, Output
from langflow.schema import Data
from langflow.services.database.models.task.model import TaskUpdate
from langflow.services.deps import get_task_orchestration_service


class TaskUpdaterComponent(Component):
    display_name = "Task Updater"
    description = "Updates or deletes existing tasks."
    icon = "edit"
    name = "TaskUpdater"

    inputs = [
        MessageTextInput(
            name="task_id",
            display_name="Task ID",
            info="The UUID of the task to update.",
            tool_mode=True,
        ),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=["Update", "Delete"],
            value="Update",
            info="Whether to update or delete the task.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="title",
            display_name="New Title",
            info="New task title (for updates).",
            advanced=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="description",
            display_name="New Description",
            info="New task description (for updates).",
            advanced=True,
            tool_mode=True,
        ),
        DataInput(
            name="attachments",
            display_name="Attachments",
            info="List of attachment references.",
            advanced=True,
            is_list=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="author_id",
            display_name="New Author ID",
            info="UUID of the new author flow.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="assignee_id",
            display_name="New Assignee ID",
            info="UUID of the new assignee flow.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="category",
            display_name="New Category",
            info="New task category.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="state",
            display_name="New State",
            info="New task state.",
            advanced=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="task_status",
            display_name="New Status",
            options=["pending", "processing", "failed", "completed"],
            info="New task status.",
            advanced=True,
            tool_mode=True,
        ),
        DataInput(
            name="result",
            display_name="Result",
            info="Task result data.",
            advanced=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Updated Task",
            name="updated_task",
            method="process_task",
            info="The updated or deleted task information.",
        )
    ]

    async def process_task(self) -> Data:
        """Update or delete a task based on the operation selected."""
        if not self.task_id:
            msg = "Task ID is required"
            raise ValueError(msg)

        try:
            task_id = UUID(self.task_id)
        except ValueError as exc:
            msg = "Invalid Task ID format - must be a valid UUID"
            raise ValueError(msg) from exc

        service = get_task_orchestration_service()

        if self.operation == "Delete":
            result = await service.delete_task(task_id)
            self.status = {"success": True, "message": f"Task {task_id} deleted successfully"}
            return result

        # Update operation
        task_data = TaskUpdate(
            title=self.title if self.title else None,
            description=self.description if self.description else None,
            attachments=self.attachments if hasattr(self, "attachments") else None,
            author_id=UUID(self.author_id) if self.author_id else None,
            assignee_id=UUID(self.assignee_id) if self.assignee_id else None,
            category=self.category if self.category else None,
            status=self.task_status if self.task_status else None,
            state=self.state if self.state else None,
            result=self.result if self.result is not None else None,
        )

        result = await service.update_task(task_data)
        self.status = result
        return result
