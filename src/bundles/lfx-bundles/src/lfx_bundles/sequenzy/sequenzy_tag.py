"""Add a tag to, or remove a tag from, a Sequenzy subscriber."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data

from lfx_bundles.sequenzy.sequenzy_common import (
    DOCUMENTATION_URL,
    SequenzyAPIError,
    api_key_input,
    call_sequenzy,
    error_data,
    text_value,
    timeout_input,
)

ADD_TAG = "Add Tag"
REMOVE_TAG = "Remove Tag"
_PATHS = {ADD_TAG: "/subscribers/tags", REMOVE_TAG: "/subscribers/tags/remove"}


class SequenzyTagSubscriberComponent(Component):
    """Tag or untag a subscriber. Adding a tag can start automations that listen for it."""

    display_name = "Sequenzy Tag Subscriber"
    description = "Add a tag to, or remove a tag from, a Sequenzy subscriber. Tags can start automations."
    documentation = f"{DOCUMENTATION_URL}/api-reference/subscribers/tags/add"
    icon = "Sequenzy"
    name = "SequenzyTagSubscriber"

    inputs = [
        api_key_input(),
        DropdownInput(
            name="action",
            display_name="Action",
            options=[ADD_TAG, REMOVE_TAG],
            value=ADD_TAG,
        ),
        MessageTextInput(
            name="email",
            display_name="Email",
            info="The subscriber's email address. Adding a tag creates the subscriber if needed.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="tag",
            display_name="Tag",
            info="The tag name, such as premium.",
            required=True,
            tool_mode=True,
        ),
        timeout_input(),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="update_tag"),
    ]

    def update_tag(self) -> Data:
        email = text_value(self.email)
        tag = text_value(self.tag)
        if not email or not tag:
            return error_data(self, "Enter the subscriber's email address and a tag.")
        action = self.action if self.action in _PATHS else ADD_TAG
        try:
            body = call_sequenzy(self, "POST", _PATHS[action], json_body={"email": email, "tag": tag})
        except SequenzyAPIError as exc:
            return error_data(self, str(exc))
        verb = "Added tag" if action == ADD_TAG else "Removed tag"
        data = Data(text=f"{verb} {tag} for {email}.", data=body)
        self.status = data
        return data
