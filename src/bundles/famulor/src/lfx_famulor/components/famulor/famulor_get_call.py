from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.template.field.base import Output

from lfx_famulor.components.famulor._client import (
    api_key_input,
    call_text,
    error_message,
    guard,
    request_json,
    require_uuid,
    unwrap_data,
)


class FamulorGetCallComponent(Component):
    """Read one Famulor call, including status, summary, and transcript."""

    display_name = "Famulor Get Call"
    description = "Get the status, summary, and transcript of a Famulor call."
    documentation = "https://docs.famulor.io/api-reference/calls/get-a-call"
    icon = "Famulor"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="call_id",
            display_name="Call ID",
            required=True,
            info="UUID of the call returned by Famulor Make Call.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Call", name="call", method="famulor_get_call"),
        Output(display_name="Message", name="message", method="famulor_get_call_message", tool_mode=False),
    ]

    def _load_call(self) -> Data:
        call_id = require_uuid(self.call_id, "Call ID")
        payload = request_json("GET", f"/calls/{call_id}", self.famulor_api_key)
        call, _meta = unwrap_data(payload)
        if not isinstance(call, dict):
            msg = "Famulor API returned an unexpected response (expected a call object)."
            raise TypeError(msg)
        return Data(text=call_text(call), data=call)

    def famulor_get_call(self) -> Data:
        """Fetch the call and return its record, summary, and transcript."""
        result = guard(self._load_call)
        self.status = result
        return result

    def famulor_get_call_message(self) -> Message:
        """Fetch the call and return the summary and transcript as text."""
        return error_message(self.famulor_get_call())
