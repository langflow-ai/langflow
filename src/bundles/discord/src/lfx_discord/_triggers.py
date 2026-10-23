"""Discord trigger declarations contain no transport credentials."""

from typing import ClassVar

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import DropdownInput, Output, StrInput
from lfx.schema.message import Message

from lfx_discord._base import connection_input


class DiscordTriggerComponent(BaseTriggerComponent):
    provider = "discord"
    icon = "MessageCircle"
    needs_connection = True
    config_fields: ClassVar[tuple[str, ...]] = (
        "connection",
        "guild_id",
        "channel_ids",
        "session_scope",
        "delivery_mode",
    )
    outputs = [
        Output(display_name="Event", name="trigger_event", method="build_event"),
        Output(display_name="Message", name="message", method="build_message"),
    ]

    def trigger_config(self) -> dict:
        return {name: getattr(self, name, None) for name in self.config_fields}

    def build_message(self) -> Message:
        event, _problem = self._firing_event()
        data = event.get("payload", {})
        data = data.get("data", data) if isinstance(data, dict) else {}
        return Message(text=data.get("text") or "", session_id=data.get("session_key") or "")


def trigger_inputs(event: str):
    return [
        connection_input(f"discord.trigger.{event}.gateway", required=False),
        StrInput(name="guild_id", display_name="Guild ID", required=True),
        StrInput(
            name="channel_ids",
            display_name="Channel or Thread IDs",
            required=True,
            is_list=True,
            value=[],
            info="Explicit IDs only. Child threads need their own IDs.",
        ),
        DropdownInput(
            name="session_scope",
            display_name="Conversation Session",
            options=["channel", "sender"],
            value="channel",
            advanced=True,
        ),
        DropdownInput(name="delivery_mode", display_name="Delivery", options=["auto"], value="auto", advanced=True),
    ]
