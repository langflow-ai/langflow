"""Configurable WhatsApp component."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.io import MultilineInput, Output, StrInput

from lfx_whatsapp._components import WhatsAppActionComponent, connection_input, recipient, text_body

if TYPE_CHECKING:
    from lfx.schema.data import Data


class WhatsAppSendTextComponent(WhatsAppActionComponent):
    display_name = "WhatsApp Send Text"
    description = (
        "Send plain text during an eligible customer service conversation. Meta enforces eligibility and limits."
    )
    name = "WhatsAppSendText"
    capability_id = "whatsapp.message.send"
    inputs = [
        connection_input(capability_id),
        StrInput(name="to", display_name="Recipient", required=True),
        MultilineInput(name="text", display_name="Text", required=True),
    ]
    outputs = [Output(display_name="Accepted Message", name="message", method="build_message")]

    async def build_message(self) -> Data:
        return await self.send(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient(self.to),
                "type": "text",
                "text": text_body(self.text),
            }
        )
