"""Send a plain-text Telegram message as the connected bot."""

from lfx.io import BoolInput, MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data

from lfx_telegram._base import TelegramActionComponent, connection_input
from lfx_telegram._validation import message_payload


class TelegramSendMessageComponent(TelegramActionComponent):
    display_name = "Telegram: Send Message"
    description = "Send one plain-text message to a chat your bot can access."
    name = "TelegramSendMessage"
    capability_id = "telegram.bot.send"
    inputs = [
        connection_input(capabilities=[capability_id]),
        MessageTextInput(name="chat_id", display_name="Chat ID", required=True, tool_mode=True),
        MultilineInput(name="text", display_name="Text", required=True, tool_mode=True),
        MessageTextInput(name="thread_id", display_name="Thread ID", advanced=True, tool_mode=True),
        BoolInput(name="silent", display_name="Silent Notification", value=False, advanced=True, tool_mode=True),
    ]
    outputs = [Output(display_name="Sent Message", name="message", method="build_message")]

    async def build_message(self) -> Data:
        return await self.send(
            message_payload(chat_id=self.chat_id, text=self.text, thread_id=self.thread_id, silent=self.silent)
        )
