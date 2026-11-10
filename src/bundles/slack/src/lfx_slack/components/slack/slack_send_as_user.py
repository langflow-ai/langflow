"""Slack: Send Message (as user) -- Web API ``chat.postMessage`` with a user token."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.io import BoolInput, DataInput, MultilineInput, Output, StrInput

from lfx_slack._base import USER_IDENTITY, SlackBaseComponent, user_connection_input
from lfx_slack._chat import API_METHOD, message_result, post_message_payload

if TYPE_CHECKING:
    from lfx.schema.data import Data

    from lfx_slack._client import SlackClient

CAPABILITY_ID = "slack.user.send"


class SlackSendAsUserComponent(SlackBaseComponent):
    display_name = "Slack: Send Message (as user)"
    description = "Post a Slack message attributed to the connected user."
    name = "SlackSendAsUser"

    capability_id = CAPABILITY_ID
    slack_identity = USER_IDENTITY

    inputs = [
        user_connection_input(capability=CAPABILITY_ID, required_scopes=["chat:write"]),
        StrInput(
            name="channel",
            display_name="Channel",
            required=True,
            info="Conversation ID or channel name the connected user can post to.",
        ),
        MultilineInput(
            name="text",
            display_name="Text",
            required=True,
            info="Message body. Slack truncates above 40,000 characters.",
        ),
        StrInput(
            name="thread_ts",
            display_name="Thread timestamp",
            info="Reply inside this thread instead of posting to the channel.",
            advanced=True,
        ),
        DataInput(
            name="blocks",
            display_name="Blocks",
            is_list=True,
            info="Optional Block Kit blocks, as Data objects.",
            advanced=True,
        ),
        BoolInput(
            name="unfurl_links",
            display_name="Unfurl links",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Message", name="message", method="build_message")]

    async def build_message(self) -> Data:
        """Post the message and return its channel, timestamp, and body."""
        payload = post_message_payload(
            channel=self.channel,
            text=self.text,
            thread_ts=self.thread_ts,
            blocks=self.blocks,
            unfurl_links=self.unfurl_links,
        )

        async def call(client: SlackClient) -> dict:
            return await client.call(API_METHOD, **payload)

        body = await self.run_action(call)
        self.status = f"Sent to {body.get('channel')}"
        return message_result(body)
