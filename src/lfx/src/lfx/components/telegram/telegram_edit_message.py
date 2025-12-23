import json

from lfx.components.telegram.telegram_utils import (
    REPLY_MARKUP_TYPE_INLINE,
    REPLY_MARKUP_TYPE_NONE,
    build_reply_markup,
    make_telegram_request,
    reply_markup_inputs,
)
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data


class TelegramEditMessage(Component):
    display_name = "Telegram Редактировать Текст Сообщения"
    description = "Редактирует текст существующего сообщения в Telegram чате используя Bot API."
    documentation: str = "https://core.telegram.org/bots/api#editmessagetext"
    icon = "Edit"
    name = "TelegramEditMessage"

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
            info="Уникальный идентификатор сообщения для редактирования.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="text",
            display_name="Текст",
            required=True,
            info="Новый текст сообщения.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="parse_mode",
            display_name="Режим парсинга",
            required=False,
            info="Режим парсинга сущностей в тексте: HTML, Markdown или MarkdownV2.",
            advanced=True,
        ),
        BoolInput(
            name="disable_web_page_preview",
            display_name="Отключить превью ссылок",
            value=False,
            required=False,
            advanced=True,
            info="Если включено, предпросмотр ссылок будет отключён через link_preview_options.is_disabled.",
        ),
        *reply_markup_inputs(advanced=True),
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
        if not self.text:
            msg = "Требуется текст"
            raise ValueError(msg)

        reply_markup = build_reply_markup(
            reply_markup_type=self.reply_markup_type,
            reply_markup_json=self.reply_markup_json,
            selective=bool(self.reply_markup_selective),
            reply_keyboard_resize=bool(self.reply_keyboard_resize),
            reply_keyboard_one_time=bool(self.reply_keyboard_one_time),
            allowed_types={REPLY_MARKUP_TYPE_NONE, REPLY_MARKUP_TYPE_INLINE},
        )

        payload: dict[str, object] = {
            "chat_id": self.chat_id,
            "message_id": int(self.message_id),
            "text": self.text,
        }

        if self.parse_mode:
            payload["parse_mode"] = self.parse_mode

        if self.disable_web_page_preview:
            payload["link_preview_options"] = {"is_disabled": True}

        if reply_markup:
            payload["reply_markup"] = reply_markup

        response_data = await make_telegram_request(
            bot_token=self.bot_token,
            method="editMessageText",
            json_payload=payload,
            timeout=60.0,
        )

        result = response_data.get("result", {})
        self.status = json.dumps(result, ensure_ascii=False)
        return Data(value=result, data={"response": response_data})
