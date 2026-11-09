"""Send a plain-text Telegram message as the connected bot."""

from lfx.io import BoolInput, MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data

from lfx_telegram._base import TelegramActionComponent, connection_input
from lfx_telegram._validation import message_payload


class TelegramNotifyComponent(TelegramActionComponent):
    display_name = "Telegram: Send Notification"
    description = "Use Telegram Send Message with Silent Notification enabled for new flows."
    name = "TelegramNotify"
    legacy = True
    replacement = ["telegram.TelegramSendMessageComponent"]
    capability_id = "telegram.bot.notify"
    inputs = [
        connection_input(capabilities=[capability_id]),
        MessageTextInput(name="chat_id", display_name="Chat ID", required=True),
        MultilineInput(name="text", display_name="Text", required=True),
        MessageTextInput(name="thread_id", display_name="Thread ID", advanced=True),
        BoolInput(name="silent", display_name="Silent Notification", value=True, advanced=True),
    ]
    outputs = [Output(display_name="Sent Message", name="message", method="build_message")]

    async def build_message(self) -> Data:
        return await self.send(
            message_payload(chat_id=self.chat_id, text=self.text, thread_id=self.thread_id, silent=self.silent)
        )
