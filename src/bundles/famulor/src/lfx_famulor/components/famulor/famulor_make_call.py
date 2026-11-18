from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, NestedDictInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.template.field.base import Output

from lfx_famulor.components.famulor._client import (
    api_key_input,
    call_text,
    error_message,
    guard,
    normalize_variables,
    optional_uuid,
    request_json,
    require_e164,
    require_uuid,
    unwrap_data,
)


class FamulorMakeCallComponent(Component):
    """Start an outbound Famulor AI call."""

    display_name = "Famulor Make Call"
    description = "Start an outbound AI phone call with a Famulor assistant."
    documentation = "https://docs.famulor.io/api-reference/calls/start-an-outbound-call"
    icon = "Famulor"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="assistant_id",
            display_name="Assistant ID",
            required=True,
            info="UUID of the active assistant that places the call.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="phone_number",
            display_name="Phone Number",
            required=True,
            info="Destination in E.164 format, for example +4930123456.",
            tool_mode=True,
        ),
        NestedDictInput(
            name="call_variables",
            display_name="Variables",
            value={},
            required=False,
            info="Optional per-call values. Each entry must be a string, number, or boolean.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="phone_number_id",
            display_name="Caller ID",
            required=False,
            advanced=True,
            info="Optional phone-number UUID to use as the caller ID. Leave empty to use the assistant's number.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Call", name="call", method="famulor_make_call"),
        Output(display_name="Message", name="message", method="famulor_make_call_message", tool_mode=False),
    ]

    def _create_call(self) -> Data:
        body: dict = {
            "assistant_id": require_uuid(self.assistant_id, "Assistant ID"),
            "to_number": require_e164(self.phone_number),
        }
        variables = normalize_variables(self.call_variables)
        if variables:
            body["variables"] = variables
        caller_id = optional_uuid(self.phone_number_id, "Caller ID")
        if caller_id:
            body["phone_number_id"] = caller_id
        payload = request_json("POST", "/calls", self.famulor_api_key, json_body=body)
        call, _meta = unwrap_data(payload)
        if not isinstance(call, dict):
            msg = "Famulor API returned an unexpected response (expected a call object)."
            raise TypeError(msg)
        return Data(text=call_text(call), data=call)

    def famulor_make_call(self) -> Data:
        """Place the call and return the created call record."""
        result = guard(self._create_call)
        self.status = result
        return result

    def famulor_make_call_message(self) -> Message:
        """Place the call and return a short status message."""
        return error_message(self.famulor_make_call())
