import json

from lfx.components.telegram.telegram_utils import make_telegram_request
from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data


class TelegramDeleteMessage(Component):
    display_name = "Telegram Удалить Сообщение"
    description = "Удаляет сообщение из указанного Telegram чата используя Bot API."
    documentation: str = "https://core.telegram.org/bots/api#deletemessage"
    icon = "Trash2"
    name = "TelegramDeleteMessage"

    inputs = [
        SecretStrInput(
            name="bot_token",
            display_name="Токен бота",
            required=True,
            password=True,
            info="Токен вашего Telegram бота, полученный от @BotFather",
        ),
        MessageTextInput(
            name="chat_id",
            display_name="ID чата",
            required=True,
            info="Уникальный идентификатор целевого чата или username канала (в формате @channelusername).",
            tool_mode=True,
        ),
        IntInput(
            name="message_id",
            display_name="ID сообщения",
            required=True,
            info="Уникальный идентификатор сообщения для удаления.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Ответ", name="response", method="build_output"),
    ]

    async def build_output(self) -> Data:
        if not self.bot_token:
            msg = "Требуется токен бота"
            raise ValueError(msg)
        if not self.chat_id:
            msg = "Требуется ID чата"
            raise ValueError(msg)
        if not self.message_id:
            msg = "Требуется ID сообщения"
            raise ValueError(msg)

        payload = {"chat_id": self.chat_id, "message_id": int(self.message_id)}
        response_data = await make_telegram_request(
            bot_token=self.bot_token,
            method="deleteMessage",
            json_payload=payload,
            timeout=30.0,
        )

        result = response_data.get("result", False)
        self.status = json.dumps({"result": result}, ensure_ascii=False)
        return Data(value={"result": result}, data={"response": response_data})
