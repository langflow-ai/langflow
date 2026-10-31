from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output

from .textkit_common import DOCUMENTATION_URL, TextKitError, error_data, textkit_request


class TextKitCheckVerificationComponent(Component):
    """Check a one-time verification code through TextKit."""

    display_name = "TextKit Check Verification"
    description = "Check the one-time code a user entered."
    documentation = DOCUMENTATION_URL
    icon = "MessagesSquare"

    inputs = [
        SecretStrInput(
            name="textkit_api_key",
            display_name="TextKit API Key",
            required=True,
            info="Your TextKit API key (tk_sk_...).",
        ),
        MessageTextInput(
            name="phone_number",
            display_name="Phone Number",
            required=True,
            info="The number the code was texted to, in E.164 format.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="verification_code",
            display_name="Code",
            required=True,
            info="The code the user entered.",
            tool_mode=True,
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.
        Output(display_name="Result", name="result", method="textkit_check_verification"),
    ]

    async def textkit_check_verification(self) -> Data:
        """Check the code. A wrong code is a normal result with ``verified`` false, not an error."""
        payload = {"phone": (self.phone_number or "").strip(), "code": (self.verification_code or "").strip()}
        try:
            check = await textkit_request(self.textkit_api_key, "POST", "/verify/check", json_body=payload)
        except TextKitError as e:
            result = error_data(str(e))
        else:
            result = Data(text="Verified." if check.get("verified") else "Not verified.", data=check)
        self.status = result
        return result
