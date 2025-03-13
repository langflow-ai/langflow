import json
from typing import ClassVar

from langflow.base.triggers import BaseTriggerComponent
from langflow.io import MessageTextInput
from langflow.schema.data import Data
from langflow.services.triggers.discord_trigger import DiscordTrigger


class DiscordMessageTriggerComponent(BaseTriggerComponent):
    """Trigger component for Discord messages."""

    display_name: ClassVar[str] = "Discord Message Trigger"
    description: ClassVar[str] = "Triggers when a specific Discord user sends a message."
    icon: ClassVar[str] = "discord"

    inputs = [
        *BaseTriggerComponent._base_inputs,
        MessageTextInput(
            name="discord_user_id",
            display_name="Discord User ID",
            info=(
                "The Discord user ID to listen for messages from. Use '*' to listen for messages from any user. "
                "To get a Discord user ID, enable Developer Mode in Discord settings, "
                "then right-click on a user and select 'Copy ID'."
            ),
            value="*",
            required=True,
        ),
        MessageTextInput(
            name="discord_username",
            display_name="Discord Username",
            info="A friendly name to identify this Discord user (for display purposes only).",
            value="Any Discord User",
            required=False,
        ),
    ]

    def get_trigger_info(self) -> Data:
        """Get information about this Discord message trigger for the flow editor.

        Returns:
            Data: A data object containing trigger configuration and parameters.
        """
        trigger_info = {
            "type": "discord_message",
        }

        # If testing mode is enabled and mock data is provided, include it
        if isinstance(self.trigger_content, str):
            trigger_content = json.loads(self.trigger_content)
        else:
            trigger_content = self.trigger_content
        if hasattr(self, "trigger_content") and self.trigger_content:
            trigger_data = trigger_content[0].get("trigger_data")
            trigger_info.update(
                {
                    "trigger_data": trigger_data,
                }
            )
            self.update_ctx({"discord_trigger_data": trigger_data})

        return Data(data=trigger_info)

    def get_trigger_instance(self) -> DiscordTrigger:
        """Return a Discord trigger instance."""
        return DiscordTrigger(
            discord_user_id=getattr(self, "discord_user_id", "*"),
            discord_username=getattr(self, "discord_username", "Any Discord User"),
        )
