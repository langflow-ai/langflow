"""Slack: Post Message (as app) -- Web API ``chat.postMessage`` with a bot token."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.io import BoolInput, DataInput, MultilineInput, Output, StrInput

from lfx_slack._base import BOT_IDENTITY, SlackBaseComponent, bot_connection_input
from lfx_slack._chat import API_METHOD, message_result, post_message_payload

if TYPE_CHECKING:
    from lfx.schema.data import Data

    from lfx_slack._client import SlackClient

CAPABILITY_ID = "slack.bot.post"


class SlackPostAsAppComponent(SlackBaseComponent):
    display_name = "Slack: Post Message (as app)"
    description = "Post a Slack message attributed to the app's bot user."
    name = "SlackPostAsApp"

    capability_id = CAPABILITY_ID
    slack_identity = BOT_IDENTITY

    inputs = [
        bot_connection_input(capability=CAPABILITY_ID, required_scopes=["chat:write"]),
        StrInput(
            name="channel",
            display_name="Channel",
            required=True,
            info="Conversation ID or channel name the bot has been added to.",
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
        BoolInput(
            name="reply_broadcast",
            display_name="Also send to channel",
            value=False,
            info="Broadcast a threaded reply back to the channel.",
            advanced=True,
        ),
        DataInput(
            name="blocks",
            display_name="Blocks",
            is_list=True,
            info="Optional Block Kit blocks, as Data objects.",
            advanced=True,
        ),
        DataInput(
            name="attachments",
            display_name="Attachments",
            is_list=True,
            info="Optional legacy attachments, as Data objects.",
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
        """Post the message as the bot and return its channel, timestamp, and body."""
        payload = post_message_payload(
            channel=self.channel,
            text=self.text,
            thread_ts=self.thread_ts,
            reply_broadcast=self.reply_broadcast,
            blocks=self.blocks,
            attachments=self.attachments,
            unfurl_links=self.unfurl_links,
        )

        async def call(client: SlackClient) -> dict:
            return await client.call(API_METHOD, **payload)

        body = await self.run_action(call)
        self.status = f"Posted to {body.get('channel')}"
        return message_result(body)
