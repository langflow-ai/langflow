"""Configurable WhatsApp component."""

from __future__ import annotations

import re

from lfx.io import DataInput, MultilineInput, Output
from lfx.schema.data import Data

from lfx_whatsapp._client import identifier
from lfx_whatsapp._components import WhatsAppActionComponent, connection_input, recipient, text_body


class WhatsAppReplyComponent(WhatsAppActionComponent):
    display_name = "WhatsApp Reply to Message"
    description = "Reply to a normalized inbound text event using its sender and message context."
    name = "WhatsAppReply"
    capability_id = "whatsapp.message.reply"
    inputs = [
        connection_input(capability_id),
        DataInput(name="event", display_name="Inbound Event", required=True),
        MultilineInput(name="text", display_name="Reply", required=True),
    ]
    outputs = [Output(display_name="Accepted Message", name="message", method="build_message")]

    async def build_message(self) -> Data:
        event = self.event.data if isinstance(self.event, Data) else self.event
        if isinstance(event, dict) and isinstance(event.get("payload"), dict):
            event = event["payload"]
        if isinstance(event, dict) and isinstance(event.get("data"), dict):
            event = event["data"]
        if not isinstance(event, dict) or event.get("provider") != "whatsapp" or event.get("event") != "message":
            msg = "Use a WhatsApp inbound message event."
            raise ValueError(msg)
        message_id = event.get("message_id")
        if not isinstance(message_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:+/=-]{1,512}", message_id):
            msg = "The inbound event has no valid message ID."
            raise ValueError(msg)
        return await self.send(
            {
                "messaging_product": "whatsapp",
                "to": recipient(event.get("sender")),
                "type": "text",
                "context": {"message_id": message_id},
                "text": text_body(self.text),
            },
            expected_phone=identifier(event.get("phone_id")),
            expected_waba=identifier(event.get("waba_id")),
        )
