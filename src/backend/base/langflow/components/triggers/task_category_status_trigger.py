import json
from datetime import datetime, timezone
from typing import Any, ClassVar

from loguru import logger

from langflow.base.triggers import BaseTriggerComponent
from langflow.io import MessageTextInput
from langflow.schema.data import Data
from langflow.services.deps import get_task_orchestration_service
from langflow.services.triggers.base_trigger import BaseTrigger


class TaskCategoryStatusTrigger(BaseTrigger):
    """Task category and status trigger implementation.

    Checks if there are any tasks with the specified category and status.
    """

    event_type: ClassVar[str] = "task_category_status_updated"

    def __init__(self, task_category: str, task_status: str, poll_interval: int = 300):
        self.task_category = task_category
        self.task_status = task_status
        self.poll_interval = poll_interval

    @classmethod
    def from_component_data(cls, component_data: dict[str, Any]):
        task_category = component_data.get("task_category", "")
        task_status = component_data.get("task_status", "")
        poll_interval = component_data.get("poll_interval", 300)
        return cls(task_category=task_category, task_status=task_status, poll_interval=poll_interval)

    def initial_state(self) -> str:
        """Return the initial state for this trigger.

        The state stores the last checked time and the last seen task IDs.
        """
        now = datetime.now(timezone.utc)
        state = {
            "last_checked": now.isoformat(),
            "last_seen_task_ids": [],
            "task_category": self.task_category,
            "task_status": self.task_status,
            "poll_interval": self.poll_interval,
        }
        return json.dumps(state)

    @classmethod
    async def check_events(cls, subscription: Any) -> list[dict[str, Any]]:
        """Check if there are any tasks with the specified category and status.

        If new tasks are found with the matching category and status, events are generated.
        """
        events = []
        try:
            state = json.loads(subscription.state)
            last_checked_str = state.get("last_checked")
            task_category = state.get("task_category", "")
            task_status = state.get("task_status", "")
            last_seen_task_ids = state.get("last_seen_task_ids", [])

            if not task_category or not task_status:
                logger.warning("Task category or status not found in state")
                return []

            last_checked = datetime.fromisoformat(last_checked_str) if last_checked_str else datetime.now(timezone.utc)

            now = datetime.now(timezone.utc)

            # Get the task orchestration service
            get_task_orchestration_service()

            # Use database session to get tasks
            from langflow.services.database.utils import session_scope

            async with session_scope() as session:
                # Query tasks from the database with matching category and status
                from sqlmodel import select

                from langflow.schema.models.task import Task

                query = select(Task).where(
                    Task.category == task_category, Task.status == task_status, Task.updated_at > last_checked
                )
                result = await session.exec(query)
                tasks = result.all()

                # Generate events for new tasks
                for task in tasks:
                    # Skip tasks we've already seen
                    task_id = str(task.id)
                    if task_id in last_seen_task_ids:
                        continue

                    # Add task ID to last seen list
                    last_seen_task_ids.append(task_id)

                    # Create the input value similar to TaskOrchestrationService
                    input_value = f"""You are a task processing agent. Your job is to complete the following task:

Task Title: {task.title}
Task Description: {task.description}
Task Author: {task.author_id}
Task Attachments: {task.attachments}
Your ID: {task.assignee_id}

Please process this task according to the description and provide a complete response.
Focus on addressing all requirements in the task description."""

                    # Convert task to dict for the event
                    task_dict = task.model_dump()

                    events.append(
                        {
                            "trigger_data": {
                                "task": task_dict,
                                "input_value": input_value,
                            }
                        }
                    )

            # Update state with new last checked time and last seen task IDs
            state["last_checked"] = now.isoformat()
            state["last_seen_task_ids"] = last_seen_task_ids[-100:]  # Keep only the last 100 task IDs
            subscription.state = json.dumps(state)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error checking task category status events: {e}")
            return []
        return events


class TaskCategoryStatusTriggerComponent(BaseTriggerComponent):
    """Component that monitors tasks with specific category and status."""

    display_name = "Task Category Status Monitor"
    description = "Triggers a flow when a task with the specified category and status is found."
    icon = "task"

    inputs = [
        *BaseTriggerComponent._base_inputs,
        MessageTextInput(
            name="task_category",
            display_name="Task Category",
            info="The category of tasks to monitor.",
            required=True,
        ),
        MessageTextInput(
            name="task_status",
            display_name="Task Status",
            info="The status of tasks to monitor (pending, processing, completed, failed).",
            required=True,
        ),
        MessageTextInput(
            name="poll_interval",
            display_name="Poll Interval",
            info="How often (in seconds) to check for matching tasks.",
            value="300",
            required=False,
        ),
    ]

    def get_trigger_info(self) -> Data:
        """Get information about this task category status trigger for the flow editor.

        Returns:
            Data: A data object containing trigger configuration and parameters.
        """
        trigger_info = {
            "type": "task_category_status",
            "task_category": self.task_category,
            "task_status": self.task_status,
            "poll_interval": getattr(self, "poll_interval", 300),
        }

        # If testing mode is enabled and mock data is provided, include it
        if hasattr(self, "trigger_content") and self.trigger_content:
            trigger_info.update(
                {
                    "trigger_data": self.trigger_content,
                }
            )

        return Data(data=trigger_info)

    def get_trigger_instance(self):
        """Get the trigger instance for this component."""
        return TaskCategoryStatusTrigger(
            task_category=self.task_category,
            task_status=self.task_status,
            poll_interval=int(getattr(self, "poll_interval", 300)),
        )
