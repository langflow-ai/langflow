from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, ClassVar

from loguru import logger

from langflow.base.triggers import BaseTriggerComponent
from langflow.io import IntInput, MessageTextInput
from langflow.schema.data import Data
from langflow.services.triggers.base_trigger import BaseTrigger


class GmailTrigger(BaseTrigger):
    """Gmail trigger implementation."""

    event_type: ClassVar[str] = "gmail_message_received"

    def __init__(self, email_address: str, query: str = "is:unread", poll_interval: int = 300):
        self.email_address = email_address
        self.query = query
        self.poll_interval = poll_interval

    @classmethod
    def from_component_data(cls, component_data: dict[str, Any]):
        """Create a GmailTrigger from component data."""
        email_address = component_data.get("email_address", "")
        query = component_data.get("query", "is:unread")
        poll_interval = component_data.get("poll_interval", 300)

        return cls(email_address=email_address, query=query, poll_interval=poll_interval)

    def initial_state(self) -> str:
        """Return the initial state for this trigger."""
        now = datetime.now(timezone.utc)
        return json.dumps(
            {
                "last_checked": now.isoformat(),
                "email_address": self.email_address,
                "query": self.query,
                "poll_interval": self.poll_interval,
            }
        )

    @classmethod
    async def check_events(cls, subscription) -> list[dict[str, Any]]:
        """Check for new emails in the Gmail inbox."""
        # This would normally query the Gmail API, but for now, we'll return an empty list
        # In a real implementation, this would check for new emails since the last check
        # and return a list of events for each new email

        # For demo purposes, you could use a library like aiogmail to connect to Gmail

        # For now, we just return an empty list
        try:
            state = json.loads(subscription.state)
            state["last_checked"] = datetime.now(timezone.utc).isoformat()
            subscription.state = json.dumps(state)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error checking Gmail events: {e}")
        return []


class GmailInboxTriggerComponent(BaseTriggerComponent):
    """Component that triggers flows based on new emails in a Gmail inbox."""

    display_name = "Gmail Inbox Trigger"
    description = "Triggers a flow when new emails arrive in a Gmail inbox."
    icon = "email"

    inputs = [
        *BaseTriggerComponent._base_inputs,
        MessageTextInput(
            name="email_address",
            display_name="Email Address",
            info="Gmail email address to check for new emails",
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Gmail search query to filter emails (e.g., is:unread, from:example@gmail.com)",
            value="is:unread",
            required=False,
        ),
        IntInput(
            name="poll_interval",
            display_name="Poll Interval",
            info="How often to check for new emails (in seconds)",
            value=300,
            required=False,
        ),
    ]

    def get_trigger_info(self) -> Data:
        """Get information about this trigger for the flow editor.

        Returns:
            Dict with trigger configuration and parameters.
        """
        trigger_info = {
            "type": "gmail_inbox",
            "email_address": self.email_address,
            "query": self.query,
            "poll_interval": self.poll_interval,
        }

        # If testing mode is enabled and mock data is provided, include it
        if hasattr(self, "is_testing") and self.is_testing and hasattr(self, "mock_data") and self.mock_data:
            # Add mock data to trigger info
            trigger_info.update(
                {
                    "trigger_data": self.mock_data,
                    "from": self.mock_data.get("from", "mock@example.com"),
                    "subject": self.mock_data.get("subject", "Mock Email Subject"),
                    "body": self.mock_data.get("body", "This is a mock email body for testing"),
                    "timestamp": self.mock_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                }
            )

        return Data(data=trigger_info)

    def get_trigger_instance(self):
        """Get the trigger instance for this component."""
        return GmailTrigger(email_address=self.email_address, query=self.query, poll_interval=self.poll_interval)
