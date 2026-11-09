"""Configurable WhatsApp component."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import BoolInput, Output, StrInput
from lfx.schema.message import Message

from lfx_whatsapp._components import connection_input

if TYPE_CHECKING:
    from lfx.schema.data import Data


class WhatsAppOnEventTriggerComponent(BaseTriggerComponent):
    display_name = "WhatsApp: On Message or Status"
    description = (
        "Receive text and delivery statuses for one phone. This trigger owns the app's WABA-wide callback override."
    )
    name = "WhatsAppOnEventTrigger"
    provider = "whatsapp"
    trigger_kind = "whatsapp.event"
    capability_ids = ("whatsapp.trigger.event.webhook",)
    icon = "WhatsApp"
    needs_connection = True
    config_fields: ClassVar[tuple[str, ...]] = (
        "connection",
        "allowed_senders",
        "receive_messages",
        "receive_statuses",
        "delivery_mode",
    )
    inputs = [
        connection_input(capability_ids[0], required=False),
        StrInput(
            name="allowed_senders",
            display_name="Allowed Sender Numbers",
            is_list=True,
            value=[],
            info="Optional digits-only sender allowlist. Empty accepts all senders for this business phone.",
        ),
        BoolInput(name="receive_messages", display_name="Receive Text Messages", value=True),
        BoolInput(
            name="receive_statuses",
            display_name="Receive Delivery Statuses",
            value=False,
            info="Opt in for delivery tracking. Route status events separately before using Reply to Message.",
        ),
        StrInput(name="delivery_mode", display_name="Delivery", value="push", show=False),
    ]
    outputs = [
        Output(display_name="Event", name="trigger_event", method="build_event"),
        Output(display_name="Message", name="message", method="build_message"),
    ]

    def trigger_config(self) -> dict:
        return {name: getattr(self, name, None) for name in self.config_fields}

    def build_event(self) -> Data:
        result = super().build_event()
        payload = result.data.get("payload", {})
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        if isinstance(data, dict) and data.get("provider") == "whatsapp":
            if data.get("event") == "message":
                self.status = "Message received"
            elif data.get("event") == "status" and data.get("status") in {
                "sent",
                "delivered",
                "read",
                "failed",
                "deleted",
            }:
                self.status = f"Status {data['status']}"
        return result

    def build_message(self) -> Message:
        payload = self.build_event().data.get("payload", {})
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        return Message(text=data.get("text", ""), session_id=data.get("session_key", ""))
