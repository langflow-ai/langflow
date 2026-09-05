"""Slack: Add Reaction (as app) -- Web API ``reactions.add``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.io import Output, StrInput
from lfx.schema.data import Data

from lfx_slack._base import BOT_IDENTITY, SlackBaseComponent, bot_connection_input

if TYPE_CHECKING:
    from lfx_slack._client import SlackClient

CAPABILITY_ID = "slack.bot.add_reaction"
API_METHOD = "reactions_add"


class SlackAddReactionComponent(SlackBaseComponent):
    display_name = "Slack: Add Reaction (as app)"
    description = "Add an emoji reaction to a Slack message as the app's bot user."
    name = "SlackAddReaction"

    capability_id = CAPABILITY_ID
    slack_identity = BOT_IDENTITY

    inputs = [
        bot_connection_input(capability=CAPABILITY_ID, required_scopes=["reactions:write"]),
        StrInput(
            name="channel",
            display_name="Channel ID",
            required=True,
            info="Conversation ID holding the message, for example C0SLACKDEMO.",
        ),
        StrInput(
            name="timestamp",
            display_name="Message timestamp",
            required=True,
            info="Timestamp of the message to react to, for example 1700000000.000100.",
        ),
        # The matrix names this input ``name``; ``Component.name`` is the
        # registry-name override, so an input called ``name`` would be shadowed
        # by the class attribute and silently read back the component's own
        # name. The Web API parameter is still sent as ``name``.
        StrInput(
            name="emoji_name",
            display_name="Emoji name",
            required=True,
            info="Emoji name without colons, for example 'thumbsup'.",
        ),
    ]

    outputs = [Output(display_name="Result", name="result", method="build_result")]

    async def build_result(self) -> Data:
        """Add the reaction and report the acknowledgement."""
        channel = (self.channel or "").strip()
        timestamp = (self.timestamp or "").strip()
        emoji = (self.emoji_name or "").strip().strip(":")
        for label, value in (("Channel ID", channel), ("Message timestamp", timestamp), ("Emoji name", emoji)):
            if not value:
                msg = f"{label} is required."
                raise ValueError(msg)

        async def call(client: SlackClient) -> dict:
            return await client.call(API_METHOD, channel=channel, timestamp=timestamp, name=emoji)

        body = await self.run_action(call)
        self.status = f"Reacted :{emoji}:"
        return Data(data={"ok": bool(body.get("ok", False)), "channel": channel, "timestamp": timestamp, "name": emoji})
