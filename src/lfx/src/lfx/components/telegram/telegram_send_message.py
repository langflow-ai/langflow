# ruff: noqa: RUF001
import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data


class TelegramSendMessage(Component):
    """Компонент для отправки сообщений через Telegram Bot API.

    Обычно используется в webhook-потоках для отправки ответов пользователям.
    Подключите chat_id из выхода chat_info компонента TelegramWebhook.
    """

    display_name = "Telegram Отправить Сообщение"
    description = "Отправляет текстовое сообщение в указанный Telegram чат используя Bot API. Используйте с TelegramWebhook для ответа на входящие сообщения."
    documentation: str = "https://core.telegram.org/bots/api#sendmessage"
    icon = "Send"
    name = "TelegramSendMessage"

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
            info="Уникальный идентификатор целевого чата или username канала (в формате @channelusername). Можно подключить из выхода chat_info компонента TelegramWebhook (chat_info.id).",
            tool_mode=True,
        ),
        MessageTextInput(
            name="text",
            display_name="Текст сообщения",
            required=True,
            info="Текст сообщения для отправки, 1-4096 символов после парсинга сущностей",
            tool_mode=True,
        ),
        MessageTextInput(
            name="parse_mode",
            display_name="Режим парсинга",
            required=False,
            info="Режим парсинга сущностей в тексте сообщения. Может быть 'HTML', 'Markdown' или 'MarkdownV2'",
            advanced=True,
        ),
        BoolInput(
            name="disable_web_page_preview",
            display_name="Отключить превью ссылок",
            value=False,
            info="Отключает превью ссылок в этом сообщении",
            advanced=True,
        ),
        BoolInput(
            name="disable_notification",
            display_name="Отключить уведомление",
            value=False,
            info="Отправляет сообщение тихо. Пользователи получат уведомление без звука",
            advanced=True,
        ),
        IntInput(
            name="reply_to_message_id",
            display_name="ID сообщения для ответа",
            required=False,
            info="Если сообщение является ответом, ID исходного сообщения",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Ответ", name="response", method="build_output"),
    ]

    async def build_output(self) -> Data:
        """Отправляет сообщение через Telegram Bot API."""
        if not self.bot_token:
            msg = "Требуется токен бота"
            raise ValueError(msg)
        if not self.chat_id:
            msg = "Требуется ID чата"
            raise ValueError(msg)
        if not self.text:
            msg = "Требуется текст сообщения"
            raise ValueError(msg)

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": self.text,
        }

        if self.parse_mode:
            payload["parse_mode"] = self.parse_mode

        if self.disable_web_page_preview:
            payload["disable_web_page_preview"] = True

        if self.disable_notification:
            payload["disable_notification"] = True

        if self.reply_to_message_id:
            payload["reply_to_message_id"] = int(self.reply_to_message_id)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                response_data = response.json()

                if not response_data.get("ok"):
                    error_description = response_data.get("description", "Неизвестная ошибка")
                    await logger.aerror(f"Ошибка Telegram API: {error_description}")
                    self.status = f"Ошибка Telegram API: {error_description}"
                    raise ValueError(self.status)

                result = response_data.get("result", {})
                await logger.ainfo(f"Сообщение успешно отправлено в чат {self.chat_id}")

                return Data(value=result, data={"response": response_data})

        except httpx.HTTPStatusError as e:
            error_msg = f"Произошла HTTP ошибка: {e.response.status_code}"
            if e.response.text:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("description", error_msg)
                except Exception:  # noqa: BLE001
                    error_msg = f"{error_msg} - {e.response.text}"
            await logger.aerror(error_msg)
            self.status = error_msg
            raise ValueError(self.status) from e

        except httpx.RequestError as e:
            error_msg = f"Запрос не выполнен: {e}"
            await logger.aerror(error_msg)
            self.status = error_msg
            raise ValueError(self.status) from e

        except Exception as e:
            error_msg = f"Неожиданная ошибка: {e!s}"
            await logger.aerror(error_msg)
            self.status = error_msg
            raise ValueError(self.status) from e
