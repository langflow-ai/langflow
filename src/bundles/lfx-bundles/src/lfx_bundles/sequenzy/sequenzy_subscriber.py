"""Add, update and look up Sequenzy subscribers."""

from __future__ import annotations

from urllib.parse import quote

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data

from lfx_bundles.sequenzy.sequenzy_common import (
    DOCUMENTATION_URL,
    SequenzyAPIError,
    api_key_input,
    call_sequenzy,
    error_data,
    parse_json_object,
    parse_list,
    text_value,
    timeout_input,
)

DUPLICATE_STRATEGIES = ["overwrite", "merge", "skip"]


class SequenzyAddSubscriberComponent(Component):
    """Create a subscriber, or update one that already exists."""

    display_name = "Sequenzy Add Subscriber"
    description = "Create or update a Sequenzy subscriber with a name, tags and custom attributes."
    documentation = f"{DOCUMENTATION_URL}/api-reference/subscribers/create"
    icon = "Sequenzy"
    name = "SequenzyAddSubscriber"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="email",
            display_name="Email",
            info="The subscriber's email address.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(name="first_name", display_name="First Name", tool_mode=True),
        MessageTextInput(name="last_name", display_name="Last Name", tool_mode=True),
        MessageTextInput(
            name="tags",
            display_name="Tags",
            info="Comma-separated tags to add, such as newsletter, trial.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="custom_attributes",
            display_name="Custom Attributes",
            info='A JSON object of custom attributes, such as {"plan": "pro"}.',
            tool_mode=True,
            advanced=True,
        ),
        DropdownInput(
            name="duplicate_strategy",
            display_name="If Subscriber Exists",
            info=(
                "overwrite: replace fields with the values sent. merge: only fill in missing fields. "
                "skip: leave the existing subscriber unchanged."
            ),
            options=DUPLICATE_STRATEGIES,
            value="overwrite",
            advanced=True,
        ),
        timeout_input(),
    ]

    outputs = [
        Output(display_name="Subscriber", name="subscriber", method="add_subscriber"),
    ]

    def add_subscriber(self) -> Data:
        email = text_value(self.email)
        if not email:
            return error_data(self, "Enter the subscriber's email address.")
        payload: dict[str, object] = {"email": email, "duplicateStrategy": self.duplicate_strategy or "overwrite"}
        for field, key in (("first_name", "firstName"), ("last_name", "lastName")):
            value = text_value(getattr(self, field, None))
            if value:
                payload[key] = value
        try:
            tags = parse_list(self.tags)
            if tags:
                payload["tags"] = tags
            attributes = parse_json_object(self.custom_attributes, "Custom Attributes")
            if attributes:
                payload["customAttributes"] = attributes
            body = call_sequenzy(self, "POST", "/subscribers", json_body=payload)
        except SequenzyAPIError as exc:
            return error_data(self, str(exc))
        subscriber = body.get("subscriber") if isinstance(body.get("subscriber"), dict) else {}
        data = Data(text=f"Saved subscriber {subscriber.get('email') or email}.", data=body)
        self.status = data
        return data


class SequenzyGetSubscriberComponent(Component):
    """Look up one subscriber by email address."""

    display_name = "Sequenzy Get Subscriber"
    description = "Get a Sequenzy subscriber's status, tags, lists and custom attributes by email."
    documentation = f"{DOCUMENTATION_URL}/api-reference/subscribers/get"
    icon = "Sequenzy"
    name = "SequenzyGetSubscriber"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="email",
            display_name="Email",
            info="The subscriber's email address.",
            required=True,
            tool_mode=True,
        ),
        timeout_input(),
    ]

    outputs = [
        Output(display_name="Subscriber", name="subscriber", method="get_subscriber"),
    ]

    def get_subscriber(self) -> Data:
        email = text_value(self.email)
        if not email:
            return error_data(self, "Enter the subscriber's email address.")
        try:
            body = call_sequenzy(self, "GET", f"/subscribers/{quote(email, safe='@')}")
        except SequenzyAPIError as exc:
            return error_data(self, str(exc))
        subscriber = body.get("subscriber")
        if not isinstance(subscriber, dict):
            return error_data(self, "Sequenzy API returned a subscriber response without a subscriber.")
        data = Data(text=f"Subscriber {subscriber.get('email') or email}", data=subscriber)
        self.status = data
        return data
