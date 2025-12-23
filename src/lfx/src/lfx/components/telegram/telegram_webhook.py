# ruff: noqa: RUF001
import json

from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output, SecretStrInput, StrInput
from lfx.log.logger import logger
from lfx.schema.data import Data


class TelegramWebhook(Component):
    """Компонент для приема и парсинга обновлений от Telegram через webhook."""

    display_name = "Telegram Webhook"
    description = (
        "Принимает и парсит входящие обновления от Telegram Bot API через webhook. "
        "Используйте как входную точку в вашем потоке."
    )
    documentation: str = "https://core.telegram.org/bots/api#update"
    icon = "Webhook"
    name = "TelegramWebhook"

    inputs = [
        SecretStrInput(
            name="bot_token",
            display_name="Токен бота",
            required=True,
            password=True,
            info="Токен вашего Telegram бота, полученный от @BotFather. Используется для валидации.",
        ),
        MultilineInput(
            name="data",
            display_name="Данные",
            info=(
                "Получает данные webhook от Telegram через HTTP POST. "
                "Автоматически заполняется при использовании с webhook endpoint Langflow."
            ),
            input_types=["Data"],
            advanced=True,
        ),
        MultilineInput(
            name="curl",
            display_name="cURL",
            value="CURL_WEBHOOK",
            advanced=True,
            input_types=[],
        ),
        MultilineInput(
            name="endpoint",
            display_name="Endpoint",
            value="BACKEND_URL",
            advanced=False,
            copy_field=True,
            input_types=[],
        ),
        StrInput(
            name="chat_ids",
            display_name="ID чатов (фильтр)",
            required=False,
            info="Список ID чатов через запятую для фильтрации.",
            advanced=True,
        ),
        StrInput(
            name="user_ids",
            display_name="ID пользователей (фильтр)",
            required=False,
            info="Список ID пользователей через запятую для фильтрации.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Данные обновления", name="update_data", method="build_update_data"),
        Output(display_name="Токен бота", name="bot_token_output", method="build_bot_token"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cached_update: dict | None = None

    def _parse_telegram_update(self) -> dict:
        """Парсит входящее обновление Telegram из данных webhook."""
        if self._cached_update is not None:
            return self._cached_update

        if not self.data:
            self.status = "Данные не предоставлены."
            return {}

        raw_data = self.data
        update = {}

        try:
            payload = raw_data.data if hasattr(raw_data, "data") else raw_data

            if isinstance(payload, dict):
                update = payload
            elif isinstance(payload, str):
                safe_payload = payload.replace('"\n"', '"\\n"') or "{}"
                update = json.loads(safe_payload)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error(f"Ошибка парсинга Telegram update: {e}")
            self.status = f"Ошибка парсинга: {e}"
            return {}

        self._cached_update = update
        return update

    def _should_process_update(self, update: dict) -> bool:
        """Проверяет фильтры chat_ids и user_ids."""
        message = (
            update.get("message")
            or update.get("edited_message")
            or update.get("channel_post")
            or update.get("edited_channel_post")
        )
        if not message:
            return True

        if self.chat_ids:
            ids = [i.strip() for i in self.chat_ids.split(",") if i.strip()]
            if ids and str(message.get("chat", {}).get("id", "")) not in ids:
                return False

        if self.user_ids:
            ids = [i.strip() for i in self.user_ids.split(",") if i.strip()]
            if ids and str(message.get("from", {}).get("id", "")) not in ids:
                return False

        return True

    def build_update_data(self) -> Data:
        """Возвращает полный объект обновления Telegram."""
        update = self._parse_telegram_update()
        if not update:
            return Data(data={})

        if not self._should_process_update(update):
            self.status = "Отфильтровано"
            return Data(data={"filtered": True, "update": update})

        data = Data(data=update)
        # Convert to readable JSON string for status display
        self.status = json.dumps(update, indent=2, ensure_ascii=False)
        logger.info(f"Получено обновление Telegram ID: {update.get('update_id')}")
        return data

    def build_bot_token(self) -> Data:
        """Возвращает токен бота."""
        if not self.bot_token:
            return Data(data={})

        data = Data(data={"bot_token": self.bot_token})
        self.status = f"Токен бота: {self.bot_token[:10]}..."
        return data
