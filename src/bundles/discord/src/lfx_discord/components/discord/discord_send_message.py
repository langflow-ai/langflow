"""Send a text message through a saved bot connection."""

from lfx.io import MultilineInput, Output, StrInput
from lfx.schema.data import Data

from lfx_discord._base import DiscordActionComponent, connection_input


class DiscordSendMessageComponent(DiscordActionComponent):
    display_name = "Discord: Send Message"
    description = "Send text to an accessible guild text channel or thread."
    name = "DiscordSendMessage"
    capability_id = "discord.bot.send"
    inputs = [
        connection_input(capability_id),
        StrInput(name="guild_id", display_name="Guild ID", required=True),
        StrInput(name="channel_id", display_name="Channel or Thread ID", required=True),
        MultilineInput(name="text", display_name="Text", required=True),
    ]
    outputs = [Output(display_name="Sent Message", name="message", method="build_message")]

    async def build_message(self) -> Data:
        return await self.send(guild_id=self.guild_id, channel_id=self.channel_id, text=self.text)
