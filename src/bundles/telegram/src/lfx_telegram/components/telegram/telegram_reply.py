"""Reply using the target and bot identity of a Telegram trigger event."""

from lfx.integrations.errors import InvalidRequestError
from lfx.io import DataInput, MultilineInput, Output
from lfx.schema.data import Data

from lfx_telegram._base import TelegramActionComponent, connection_input
from lfx_telegram._validation import message_payload, numeric_id


class TelegramReplyComponent(TelegramActionComponent):
    display_name = "Telegram: Reply to Message"
    description = "Reply to a trigger event using the same bot, chat, and topic."
    name = "TelegramReply"
    capability_id = "telegram.bot.reply"
    inputs = [
        connection_input(capabilities=[capability_id]),
        DataInput(name="event", display_name="Trigger Event", required=True),
        MultilineInput(name="text", display_name="Text", required=True),
    ]
    outputs = [Output(display_name="Sent Message", name="message", method="build_message")]

    async def build_message(self) -> Data:
        event = self.event.data if isinstance(self.event, Data) else self.event
        if isinstance(event, dict) and isinstance(event.get("payload"), dict):
            event = event["payload"]
        if isinstance(event, dict):
            event = event.get("data", event.get("delivery", event))
        if not isinstance(event, dict) or event.get("provider") != "telegram":
            msg = "Choose a Telegram trigger event to reply to."
            raise InvalidRequestError(msg, provider="telegram")
        bot_id = str(numeric_id(event.get("bot_id"), positive=True))
        payload = message_payload(
            chat_id=event.get("chat_id"),
            text=self.text,
            thread_id=event.get("thread_id"),
            reply_id=event.get("message_id"),
        )
        return await self.send(payload, expected_bot_id=bot_id)
