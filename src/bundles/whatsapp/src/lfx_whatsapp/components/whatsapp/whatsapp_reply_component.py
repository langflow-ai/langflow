"""Configurable WhatsApp component."""

from __future__ import annotations

import re

from lfx.io import DataInput, MultilineInput, Output
from lfx.schema.data import Data

from lfx_whatsapp._client import identifier
from lfx_whatsapp._components import WhatsAppActionComponent, connection_input, recipient, text_body
from lfx_whatsapp._messages import INVALID_INBOUND_EVENT_MESSAGE, INVALID_MESSAGE_ID_MESSAGE


class WhatsAppReplyComponent(WhatsAppActionComponent):
    display_name = "WhatsApp: Reply to Message"
    description = "Reply to a normalized inbound text event using its sender and message context."
    name = "WhatsAppReply"
    capability_id = "whatsapp.message.reply"
    inputs = [
        connection_input(capability_id),
        DataInput(name="event", display_name="Inbound Event", required=True, tool_mode=True),
        MultilineInput(name="text", display_name="Reply", required=True, tool_mode=True),
    ]
    outputs = [Output(display_name="Accepted Message", name="message", method="build_message")]

    async def build_message(self) -> Data:
        event = self.event.data if isinstance(self.event, Data) else self.event
        if isinstance(event, dict) and isinstance(event.get("payload"), dict):
            event = event["payload"]
        if isinstance(event, dict) and isinstance(event.get("data"), dict):
            event = event["data"]
        if (
            not isinstance(event, dict)
            or event.get("provider") != "whatsapp"
            or event.get("event") not in {"message", "status"}
        ):
            raise ValueError(INVALID_INBOUND_EVENT_MESSAGE)
        message_id = event.get("message_id")
        if not isinstance(message_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:+/=-]{1,512}", message_id):
            raise ValueError(INVALID_MESSAGE_ID_MESSAGE)
        phone = identifier(event.get("phone_id"))
        waba = identifier(event.get("waba_id"))
        sender = recipient(event.get("sender"))
        if event.get("event") == "status":
            if event.get("status") not in {"sent", "delivered", "read", "failed", "deleted"}:
                raise ValueError(INVALID_INBOUND_EVENT_MESSAGE)
            self.status = "Skipped delivery status. Reply only sends messages for inbound text events."
            if self._vertex is not None:
                self.stop("message")
            return Data(
                data={
                    "provider": "whatsapp",
                    "event": "status",
                    "status": event["status"],
                    "skipped": True,
                    "accepted": False,
                    "reason": "delivery_status",
                }
            )
        return await self.send(
            {
                "messaging_product": "whatsapp",
                "to": sender,
                "type": "text",
                "context": {"message_id": message_id},
                "text": text_body(self.text),
            },
            expected_phone=phone,
            expected_waba=waba,
        )
