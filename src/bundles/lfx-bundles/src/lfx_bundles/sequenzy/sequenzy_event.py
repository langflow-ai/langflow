"""Trigger a custom event for a Sequenzy subscriber."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

from lfx_bundles.sequenzy.sequenzy_common import (
    DOCUMENTATION_URL,
    SequenzyAPIError,
    api_key_input,
    call_sequenzy,
    error_data,
    parse_json_object,
    text_value,
    timeout_input,
)


class SequenzyTriggerEventComponent(Component):
    """Record an event, such as purchase.completed, which can start automations."""

    display_name = "Sequenzy Trigger Event"
    description = "Trigger a custom event for a Sequenzy subscriber to start automations and segment by behavior."
    documentation = f"{DOCUMENTATION_URL}/api-reference/subscribers/events/trigger"
    icon = "Sequenzy"
    name = "SequenzyTriggerEvent"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="email",
            display_name="Email",
            info="The subscriber's email address. The subscriber is created if needed.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="event",
            display_name="Event Name",
            info="The event name, such as purchase.completed.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="properties",
            display_name="Event Properties",
            info='A JSON object of event properties, such as {"amount": 9900, "currency": "USD"}.',
            tool_mode=True,
        ),
        MessageTextInput(
            name="event_id",
            display_name="Event ID",
            info="Optional idempotency key. Sending the same ID again does not record a second event.",
            advanced=True,
        ),
        timeout_input(),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="trigger_event"),
    ]

    def trigger_event(self) -> Data:
        email = text_value(self.email)
        event = text_value(self.event)
        if not email or not event:
            return error_data(self, "Enter the subscriber's email address and an event name.")
        payload: dict[str, object] = {"email": email, "event": event}
        event_id = text_value(self.event_id)
        if event_id:
            payload["eventId"] = event_id
        try:
            properties = parse_json_object(self.properties, "Event Properties")
            if properties:
                payload["properties"] = properties
            body = call_sequenzy(self, "POST", "/subscribers/events", json_body=payload)
        except SequenzyAPIError as exc:
            return error_data(self, str(exc))
        data = Data(text=f"Triggered {event} for {email}.", data=body)
        self.status = data
        return data
