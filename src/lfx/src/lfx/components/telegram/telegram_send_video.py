import json

from lfx.components.telegram.telegram_utils import (
    build_reply_markup,
    dumps_reply_markup_for_multipart,
    make_telegram_request,
    open_file_for_telegram,
    reply_markup_inputs,
)
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, FileInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data


class TelegramSendVideo(Component):
    display_name = "Telegram Отправить Видео"
    description = "Отправляет видео в указанный Telegram чат используя Bot API."
    documentation: str = "https://core.telegram.org/bots/api#sendvideo"
    icon = "Video"
    name = "TelegramSendVideo"

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
        FileInput(
            name="video_file",
            display_name="Видео (файл)",
            required=False,
            file_types=["mp4", "mov", "mkv", "webm"],
            info="Загрузите файл видео для отправки. Если заполнено, имеет приоритет над полем 'Видео (URL или file_id)'.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="video",
            display_name="Видео (URL или file_id)",
            required=False,
            info="file_id существующего файла в Telegram или HTTP URL видео.",
            tool_mode=True,
        ),
        FileInput(
            name="thumbnail_file",
            display_name="Thumbnail (файл)",
            required=False,
            file_types=["jpg", "jpeg"],
            info="Миниатюра для видео. Используется только при отправке видео из файла.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="caption",
            display_name="Подпись",
            required=False,
            info="Подпись к видео (до 1024 символов).",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="parse_mode",
            display_name="Режим парсинга",
            required=False,
            info="Режим парсинга подписи: HTML, Markdown или MarkdownV2.",
            advanced=True,
        ),
        IntInput(
            name="duration",
            display_name="Длительность (сек.)",
            required=False,
            info="Длительность видео в секундах.",
            advanced=True,
        ),
        IntInput(
            name="width",
            display_name="Ширина",
            required=False,
            info="Ширина видео.",
            advanced=True,
        ),
        IntInput(
            name="height",
            display_name="Высота",
            required=False,
            info="Высота видео.",
            advanced=True,
        ),
        BoolInput(
            name="disable_notification",
            display_name="Отключить уведомление",
            value=False,
            info="Отправить сообщение тихо.",
            advanced=True,
        ),
        IntInput(
            name="reply_to_message_id",
            display_name="ID сообщения для ответа",
            required=False,
            info="Если сообщение является ответом, ID исходного сообщения.",
            advanced=True,
        ),
        IntInput(
            name="message_thread_id",
            display_name="ID треда (topic)",
            required=False,
            info="ID треда форума (topic) для supergroup, если применимо.",
            advanced=True,
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
        if not self.video_file and not self.video:
            msg = "Требуется видео: загрузите файл или укажите URL/file_id"
            raise ValueError(msg)
        if self.thumbnail_file and not self.video_file:
            msg = "Thumbnail поддерживается только при отправке видео из файла."
            raise ValueError(msg)

        reply_markup = build_reply_markup(
            reply_markup_type=self.reply_markup_type,
            reply_markup_json=self.reply_markup_json,
            selective=bool(self.reply_markup_selective),
            reply_keyboard_resize=bool(self.reply_keyboard_resize),
            reply_keyboard_one_time=bool(self.reply_keyboard_one_time),
        )

        if self.video_file:
            video_tuple = open_file_for_telegram(self.video_file)
            thumbnail_tuple = None
            try:
                if self.thumbnail_file:
                    thumbnail_tuple = open_file_for_telegram(self.thumbnail_file)

                data_payload: dict[str, str | int] = {"chat_id": self.chat_id}
                if self.caption:
                    data_payload["caption"] = self.caption
                if self.parse_mode:
                    data_payload["parse_mode"] = self.parse_mode
                if self.duration:
                    data_payload["duration"] = int(self.duration)
                if self.width:
                    data_payload["width"] = int(self.width)
                if self.height:
                    data_payload["height"] = int(self.height)
                if self.disable_notification:
                    data_payload["disable_notification"] = "true"
                if self.reply_to_message_id:
                    data_payload["reply_to_message_id"] = int(self.reply_to_message_id)
                if self.message_thread_id:
                    data_payload["message_thread_id"] = int(self.message_thread_id)

                rm = dumps_reply_markup_for_multipart(reply_markup)
                if rm:
                    data_payload["reply_markup"] = rm

                files = {"video": video_tuple}
                if thumbnail_tuple:
                    files["thumbnail"] = thumbnail_tuple

                response_data = await make_telegram_request(
                    bot_token=self.bot_token,
                    method="sendVideo",
                    data_payload=data_payload,
                    files=files,
                    timeout=180.0,
                )
            finally:
                video_tuple[1].close()
                if thumbnail_tuple is not None:
                    thumbnail_tuple[1].close()
        else:
            json_payload: dict[str, object] = {"chat_id": self.chat_id, "video": self.video}
            if self.caption:
                json_payload["caption"] = self.caption
            if self.parse_mode:
                json_payload["parse_mode"] = self.parse_mode
            if self.duration:
                json_payload["duration"] = int(self.duration)
            if self.width:
                json_payload["width"] = int(self.width)
            if self.height:
                json_payload["height"] = int(self.height)
            if self.disable_notification:
                json_payload["disable_notification"] = True
            if self.reply_to_message_id:
                json_payload["reply_to_message_id"] = int(self.reply_to_message_id)
            if self.message_thread_id:
                json_payload["message_thread_id"] = int(self.message_thread_id)
            if reply_markup:
                json_payload["reply_markup"] = reply_markup

            response_data = await make_telegram_request(
                bot_token=self.bot_token,
                method="sendVideo",
                json_payload=json_payload,
                timeout=180.0,
            )

        result = response_data.get("result", {})
        self.status = json.dumps(result, ensure_ascii=False)
        return Data(value=result, data={"response": response_data})
