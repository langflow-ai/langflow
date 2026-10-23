"""Reply with the bot and channel from a Discord message trigger."""

from lfx.integrations.errors import InvalidRequestError
from lfx.io import DataInput, MultilineInput, Output
from lfx.schema.data import Data

from lfx_discord._base import DiscordActionComponent, connection_input
from lfx_discord._client import snowflake


class DiscordReplyComponent(DiscordActionComponent):
    display_name = "Discord: Reply to Message"
    description = "Reply to a message event in its original guild channel or thread."
    name = "DiscordReply"
    capability_id = "discord.bot.reply"
    inputs = [
        connection_input(capability_id),
        DataInput(name="event", display_name="Trigger Event", required=True),
        MultilineInput(name="text", display_name="Text", required=True),
    ]
    outputs = [Output(display_name="Sent Message", name="message", method="build_message")]

    async def build_message(self) -> Data:
        event = self.event.data if isinstance(self.event, Data) else self.event
        if isinstance(event, dict) and isinstance(event.get("payload"), dict):
            event = event["payload"]
        if isinstance(event, dict):
            event = event.get("data", event)
        if not isinstance(event, dict) or event.get("provider") != "discord":
            msg = "Choose a Discord message trigger event."
            raise InvalidRequestError(msg, provider="discord")
        return await self.send(
            guild_id=event.get("guild_id"),
            channel_id=event.get("channel_id"),
            text=self.text,
            message_id=event.get("message_id"),
            expected_bot=snowflake(event.get("bot_id")),
        )
