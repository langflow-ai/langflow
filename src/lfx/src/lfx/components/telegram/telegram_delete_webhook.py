import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data


class TelegramDeleteWebhook(Component):
    """Компонент для удаления webhook интеграции из Telegram Bot API.

    Используйте для прекращения приема обновлений через webhook.
    После удаления Telegram перестанет отправлять обновления на ваш webhook URL.
    """

    display_name = "Telegram Удалить Webhook"
    description = "Удаляет webhook интеграцию. После удаления Telegram перестанет отправлять обновления на ваш webhook URL. Возвращает True при успехе."
    documentation: str = "https://core.telegram.org/bots/api#deletewebhook"
    icon = "Trash2"
    name = "TelegramDeleteWebhook"

    inputs = [
        SecretStrInput(
            name="bot_token",
            display_name="Токен бота",
            required=True,
            password=True,
            info="Токен вашего Telegram бота, полученный от @BotFather",
        ),
        BoolInput(
            name="drop_pending_updates",
            display_name="Удалить ожидающие обновления",
            value=False,
            info="Установите True для удаления всех ожидающих обновлений",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Ответ", name="response", method="build_output"),
    ]

    async def build_output(self) -> Data:
        """Удаляет webhook из Telegram Bot API."""
        if not self.bot_token:
            msg = "Требуется токен бота"
            raise ValueError(msg)

        url = f"https://api.telegram.org/bot{self.bot_token}/deleteWebhook"

        payload = {}
        if self.drop_pending_updates:
            payload["drop_pending_updates"] = True

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                response.raise_for_status()
                response_data = response.json()

                if not response_data.get("ok"):
                    error_description = response_data.get("description", "Неизвестная ошибка")
                    await logger.aerror(f"Ошибка Telegram API: {error_description}")
                    self.status = f"Ошибка Telegram API: {error_description}"
                    raise ValueError(self.status)

                result = response_data.get("result", False)
                await logger.ainfo("Webhook успешно удален")

                return Data(value={"ok": True, "result": result}, data={"response": response_data})

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
