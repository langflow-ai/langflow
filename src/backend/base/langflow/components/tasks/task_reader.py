"""Component for reading and querying tasks."""

from uuid import UUID

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
from langflow.services.deps import get_task_orchestration_service


class TaskReaderComponent(Component):
    display_name = "Task Reader"
    description = "Reads task information from the system."
    icon = "eye"
    name = "TaskReader"

    inputs = [
        MessageTextInput(
            name="task_id",
            display_name="Task ID",
            info="The UUID of the task to read.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Task",
            name="task",
            method="get_task",
        )
    ]

    async def get_task(self) -> Data:
        """Retrieve task information by ID."""
        if not self.task_id:
            msg = "Task ID is required"
            raise ValueError(msg)

        try:
            task_id = UUID(self.task_id)
        except ValueError as exc:
            msg = "Invalid Task ID format - must be a valid UUID"
            raise ValueError(msg) from exc

        service = get_task_orchestration_service()
        result = await service.get_task(task_id)
        self.status = result
        return result
