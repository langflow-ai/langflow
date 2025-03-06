from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, ClassVar

from croniter import croniter
from loguru import logger

from langflow.base.triggers import BaseTriggerComponent
from langflow.io import MessageTextInput
from langflow.schema.data import Data
from langflow.services.triggers.base_trigger import BaseTrigger


class ScheduleTrigger(BaseTrigger):
    """Schedule trigger implementation."""

    event_type: ClassVar[str] = "schedule_triggered"

    def __init__(self, cron_expression: str, description: str = ""):
        self.cron_expression = cron_expression
        self.description = description

        # Validate the cron expression
        try:
            croniter(self.cron_expression)
        except ValueError as e:
            msg = f"Invalid cron expression: {e}"
            raise ValueError(msg) from e

    @classmethod
    def from_component_data(cls, component_data: dict[str, Any]):
        """Create a ScheduleTrigger from component data."""
        cron_expression = component_data.get("cron_expression", "* * * * *")
        description = component_data.get("description", "")

        return cls(cron_expression=cron_expression, description=description)

    def initial_state(self) -> str:
        """Return the initial state for this trigger."""
        now = datetime.now(timezone.utc)
        return json.dumps(
            {
                "last_checked": now.isoformat(),
                "last_triggered": None,
                "cron_expression": self.cron_expression,
                "description": self.description,
            }
        )

    @classmethod
    async def check_events(cls, subscription) -> list[dict[str, Any]]:
        """Check if the schedule should trigger based on the cron expression."""
        events = []
        try:
            state = json.loads(subscription.state)
            last_checked_str = state.get("last_checked")
            cron_expression = state.get("cron_expression")

            # Parse last_checked to a datetime and ensure it's timezone-aware
            if last_checked_str:
                last_checked = datetime.fromisoformat(last_checked_str)
                if last_checked.tzinfo is None:
                    last_checked = last_checked.replace(tzinfo=timezone.utc)
            else:
                last_checked = datetime.now(timezone.utc)

            now = datetime.now(timezone.utc)

            # Check if we need to trigger based on the cron expression
            cron = croniter(cron_expression, last_checked)
            next_execution = cron.get_next(datetime)
            # Ensure next_execution is timezone-aware; assume UTC if not
            if next_execution.tzinfo is None:
                next_execution = next_execution.replace(tzinfo=timezone.utc)

            # If the next execution time is before now, we need to trigger
            if next_execution <= now:
                # Generate an event
                events.append(
                    {
                        "trigger_data": {
                            "scheduled_time": now.isoformat(),
                            "cron_expression": cron_expression,
                            "description": state.get("description", ""),
                        }
                    }
                )

                # Update the last triggered time
                state["last_triggered"] = now.isoformat()

            # Update the last checked timestamp
            state["last_checked"] = now.isoformat()
            subscription.state = json.dumps(state)
        except ValueError as e:
            logger.error(f"Error parsing schedule subscription state: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON in schedule subscription state: {e}")
            return []
        except (KeyError, TypeError) as e:
            logger.error(f"Error accessing data in schedule subscription state: {e}")
            return []
        except Exception as e:  # noqa: BLE001
            # Keep this as a fallback for unexpected errors
            logger.error(f"Unexpected error checking schedule events: {e}")
            return []
        else:
            return events


class ScheduleTriggerComponent(BaseTriggerComponent):
    """Component that triggers flows based on a schedule."""

    display_name = "Schedule Trigger"
    description = "Triggers a flow based on a schedule defined by a cron expression."
    icon = "clock"

    inputs = [
        *BaseTriggerComponent._base_inputs,
        MessageTextInput(
            name="cron_expression",
            display_name="Cron Expression",
            info="Cron expression for the schedule (e.g., '0 * * * *' for hourly)",
            required=True,
        ),
        MessageTextInput(
            name="description",
            display_name="Description",
            info="Description of this scheduled trigger",
            required=False,
        ),
    ]

    def get_trigger_info(self) -> Data:
        """Get information about this trigger for the flow editor.

        Returns:
            Dict with trigger configuration and parameters.
        """
        trigger_info = {
            "type": "schedule",
            "cron_expression": self.cron_expression,
            "description": getattr(self, "description", ""),
        }

        # If testing mode is enabled and mock data is provided, include it
        if hasattr(self, "is_testing") and self.is_testing and hasattr(self, "mock_data") and self.mock_data:
            # Add mock data to trigger info
            trigger_info.update(
                {
                    "trigger_data": self.mock_data,
                    "scheduled_time": self.mock_data.get("scheduled_time", datetime.now(timezone.utc).isoformat()),
                    "cron_expression": self.mock_data.get("cron_expression", self.cron_expression),
                    "timestamp": self.mock_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                }
            )

        return Data(data=trigger_info)

    def get_trigger_instance(self):
        """Get the trigger instance for this component."""
        return ScheduleTrigger(
            cron_expression=self.cron_expression,
            description=getattr(self, "description", ""),
        )
