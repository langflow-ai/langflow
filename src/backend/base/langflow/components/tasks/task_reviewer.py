"""Component for reviewing tasks."""

from datetime import datetime, timezone
from uuid import UUID

from langflow.custom import Component
from langflow.io import MessageTextInput, MultilineInput, Output
from langflow.schema import Data
from langflow.services.database.models.task.model import ReviewBase, TaskUpdate
from langflow.services.deps import get_task_orchestration_service


class TaskReviewerComponent(Component):
    display_name = "Task Reviewer"
    description = "Reviews tasks and adds feedback."
    icon = "check-square"
    name = "TaskReviewer"

    inputs = [
        MessageTextInput(
            name="task_id",
            display_name="Task ID",
            info="The UUID of the task to review.",
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="comment",
            display_name="Review Comment",
            info="Feedback or comments about the task.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="reviewer_id",
            display_name="Reviewer ID",
            info="UUID of the reviewer (defaults to the current flow ID if not provided).",
            advanced=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Reviewed Task",
            name="reviewed_task",
            method="review_task",
            info="The task with added review information.",
        )
    ]

    async def review_task(self) -> Data:
        """Review a task by adding feedback and updating its status."""
        # Validate task ID
        task_id: UUID | str | None = self.task_id
        if not task_id:
            msg = "Task ID is required"
            raise ValueError(msg)

        try:
            if isinstance(task_id, str):
                task_id = UUID(task_id)
        except ValueError as exc:
            msg = "Invalid Task ID format - must be a valid UUID"
            raise ValueError(msg) from exc

        # Validate review comment
        if not hasattr(self, "comment") or not self.comment:
            msg = "Review comment is required"
            raise ValueError(msg)

        # Get reviewer ID (use flow ID from context if not provided)
        reviewer_id = None
        if hasattr(self, "reviewer_id") and self.reviewer_id:
            try:
                reviewer_id = UUID(self.reviewer_id)
            except ValueError as exc:
                msg = "Invalid Reviewer ID format - must be a valid UUID"
                raise ValueError(msg) from exc
        elif "flow_id" in self.ctx:
            reviewer_id = UUID(self.ctx["flow_id"])
        else:
            msg = "Reviewer ID is required"
            raise ValueError(msg)

        # Get task orchestration service
        service = get_task_orchestration_service()

        # Get the current task to check its status
        current_task = await service.get_task(task_id)

        # Ensure the task is in completed status before reviewing
        if current_task.status != "completed":
            msg = "Cannot add a review to a task that is not completed."
            raise ValueError(msg)

        # Create the review object using ReviewBase model
        review = ReviewBase(
            comment=self.comment,
            reviewer_id=str(reviewer_id),
            reviewed_at=datetime.now(timezone.utc).isoformat(),
        )

        # Create task update with just the review
        # The service will handle adding it to the review history
        task_data = TaskUpdate(
            id=task_id,
            review=review,
            # No need to set status - the service will automatically set it to "pending"
        )

        # Update the task
        result = await service.update_task(task_data)

        # Set status for UI feedback
        self.status = {"success": True, "message": f"Task {task_id} reviewed successfully"}

        return result
