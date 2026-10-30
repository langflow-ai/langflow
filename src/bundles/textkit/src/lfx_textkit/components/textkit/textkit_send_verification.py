from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output

from .textkit_common import DOCUMENTATION_URL, TextKitError, error_data, textkit_request


class TextKitSendVerificationComponent(Component):
    """Text a one-time verification code through TextKit."""

    display_name = "TextKit Send Verification"
    description = "Text a one-time code to a phone number."
    documentation = DOCUMENTATION_URL
    icon = "MessagesSquare"

    inputs = [
        SecretStrInput(
            name="textkit_api_key",
            display_name="TextKit API Key",
            required=True,
            info="Your TextKit API key (ssms_sk_...).",
        ),
        MessageTextInput(
            name="phone_number",
            display_name="Phone Number",
            required=True,
            info="The number to text the code to, in E.164 format.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="app_name",
            display_name="App Name",
            required=False,
            advanced=True,
            info="Your product name, shown in the message.",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.
        Output(display_name="Verification", name="verification", method="textkit_send_verification"),
    ]

    async def textkit_send_verification(self) -> Data:
        """Send the code and return the verification."""
        payload = {"channel": "sms", "phone": (self.phone_number or "").strip()}
        app_name = (self.app_name or "").strip()
        if app_name:
            payload["app_name"] = app_name
        try:
            verification = await textkit_request(self.textkit_api_key, "POST", "/verify", json_body=payload)
        except TextKitError as e:
            result = error_data(str(e))
        else:
            result = Data(
                text=f"Verification {verification.get('id')} is {verification.get('status')}.", data=verification
            )
        self.status = result
        return result
