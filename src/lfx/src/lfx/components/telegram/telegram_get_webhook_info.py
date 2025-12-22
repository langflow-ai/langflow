# ruff: noqa: RUF001, RUF002
import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data


class TelegramGetWebhookInfo(Component):
    """Компонент для получения текущей информации о webhook из Telegram Bot API.

    Используйте для проверки конфигурации webhook, проверки URL и просмотра количества ожидающих обновлений.
    Полезно для отладки проблем с webhook.
    """

    display_name = "Telegram Получить Информацию о Webhook"
    description = "Возвращает текущий статус и информацию о webhook. Показывает webhook URL, количество ожидающих обновлений и последнюю ошибку. Если webhook не установлен, возвращает пустой объект WebhookInfo."
    documentation: str = "https://core.telegram.org/bots/api#getwebhookinfo"
    icon = "Info"
    name = "TelegramGetWebhookInfo"

    inputs = [
        SecretStrInput(
            name="bot_token",
            display_name="Токен бота",
            required=True,
            password=True,
            info="Токен вашего Telegram бота, полученный от @BotFather",
        ),
    ]

    outputs = [
        Output(display_name="Информация о Webhook", name="webhook_info", method="build_output"),
    ]

    async def build_output(self) -> Data:
        """Получает информацию о webhook из Telegram Bot API."""
        if not self.bot_token:
            msg = "Требуется токен бота"
            raise ValueError(msg)

        url = f"https://api.telegram.org/bot{self.bot_token}/getWebhookInfo"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, timeout=10.0)
                response.raise_for_status()
                response_data = response.json()

                if not response_data.get("ok"):
                    error_description = response_data.get("description", "Неизвестная ошибка")
                    await logger.aerror(f"Ошибка Telegram API: {error_description}")
                    self.status = f"Ошибка Telegram API: {error_description}"
                    raise ValueError(self.status)

                webhook_info = response_data.get("result", {})
                webhook_url = webhook_info.get("url", "")
                status = webhook_url or "Not set"
                await logger.ainfo(f"Получена информация о webhook. URL: {status}")

                return Data(value=webhook_info, data={"response": response_data})

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
