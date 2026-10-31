from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, MultilineInput, SecretStrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output

from .textkit_common import DOCUMENTATION_URL, TextKitError, error_data, textkit_request


class TextKitSendMessageComponent(Component):
    """Send an SMS through TextKit."""

    display_name = "TextKit Send Text"
    description = "Send an SMS from your TextKit number."
    documentation = DOCUMENTATION_URL
    icon = "MessagesSquare"

    inputs = [
        SecretStrInput(
            name="textkit_api_key",
            display_name="TextKit API Key",
            required=True,
            info="Your TextKit API key (tk_sk_...). A test key simulates sends.",
        ),
        MessageTextInput(
            name="to_number",
            display_name="To",
            required=True,
            info="The recipient's number in E.164 format, for example +15551234567.",
            tool_mode=True,
        ),
        MultilineInput(
            name="message_body",
            display_name="Message",
            required=True,
            info="The text to send.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="from_number",
            display_name="From",
            required=False,
            advanced=True,
            info="One of your numbers, or a sender pool id. Optional when the account has exactly one number.",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.
        Output(display_name="Message", name="message", method="textkit_send_text"),
    ]

    async def textkit_send_text(self) -> Data:
        """Send the text and return the created message."""
        payload = {"to": (self.to_number or "").strip(), "body": self.message_body or ""}
        from_number = (self.from_number or "").strip()
        if from_number:
            payload["from"] = from_number
        try:
            message = await textkit_request(self.textkit_api_key, "POST", "/messages", json_body=payload)
        except TextKitError as e:
            result = error_data(str(e))
        else:
            result = Data(text=f"Message {message.get('id')} is {message.get('status')}.", data=message)
        self.status = result
        return result
