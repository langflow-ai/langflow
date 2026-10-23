"""Telegram trigger declarations have no transport or credential material."""

from __future__ import annotations

from typing import ClassVar

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import DropdownInput, Output, StrInput
from lfx.schema.message import Message

from lfx_telegram._base import connection_input


def trigger_inputs(event: str) -> list:
    return [
        connection_input(
            capabilities=[f"telegram.trigger.{event}.webhook", f"telegram.trigger.{event}.poll"], required=False
        ),
        StrInput(
            name="allowed_chats",
            display_name="Allowed Chat IDs",
            is_list=True,
            value=[],
            required=True,
            info="An explicit list of numeric chat IDs this flow may receive. Empty lists cannot be armed.",
        ),
        StrInput(
            name="allowed_senders",
            display_name="Allowed Sender IDs",
            is_list=True,
            value=[],
            advanced=True,
            info="Optional numeric user IDs. Anonymous messages fail this filter.",
        ),
        DropdownInput(
            name="session_scope",
            display_name="Conversation Session",
            options=["thread", "sender", "chat"],
            value="thread",
            advanced=True,
        ),
        DropdownInput(
            name="delivery_mode",
            display_name="Delivery",
            options=["auto", "push", "poll"],
            value="auto",
            advanced=True,
            info="Polling refuses a bot that already has a webhook. Transport changes retain pending updates.",
        ),
    ]


class TelegramTriggerComponent(BaseTriggerComponent):
    """Hand the server-verified event to the downstream flow."""

    provider = "telegram"
    icon = "Send"
    needs_connection = True
    config_fields: ClassVar[tuple[str, ...]] = (
        "connection",
        "allowed_chats",
        "allowed_senders",
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
        payload = event.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        payload = payload.get("data", payload.get("delivery", payload))
        return Message(text=payload.get("text") or "", session_id=payload.get("session_key") or "")
