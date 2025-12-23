# ruff: noqa: RUF001, RUF002
import asyncio
import re
from pathlib import Path

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

MAX_CONNECTIONS_LIMIT = 100


def _generate_secret_token(flow_id: str | None = None, node_id: str | None = None) -> str:
    """Генерирует secret token для Telegram webhook в стиле n8n.

    В n8n secret token генерируется как: {workflow_id}_{node_id}
    и очищается от недопустимых символов (только A-Z, a-z, 0-9, _, -).

    Args:
        flow_id: ID потока (workflow). Если None, используется пустая строка.
        node_id: ID узла (node). Если None, используется пустая строка.

    Returns:
        Сгенерированный secret token, очищенный от недопустимых символов.
    """
    flow_id = flow_id or ""
    node_id = node_id or ""

    secret_token = f"{flow_id}_{node_id}"
    return re.sub(r"[^a-zA-Z0-9_\-]+", "", secret_token)


class TelegramSetWebhook(Component):
    """Компонент для установки webhook URL для Telegram Bot API.

    Используйте для настройки Telegram для отправки обновлений в ваш Langflow поток.
    Webhook URL должен указывать на: https://your-langflow-server/api/v1/webhook/{flow_id}
    После установки webhook используйте компонент TelegramWebhook в вашем потоке для приема обновлений.
    """

    display_name = "Telegram Установить Webhook"
    description = (
        "Устанавливает webhook URL для приема входящих обновлений через исходящий webhook. "
        "Telegram будет отправлять POST запросы на этот URL при каждом обновлении для бота. "
        "Настройте один раз, затем используйте компонент TelegramWebhook "
        "в вашем потоке для обработки входящих сообщений."
    )
    documentation: str = "https://core.telegram.org/bots/api#setwebhook"
    icon = "Webhook"
    name = "TelegramSetWebhook"

    inputs = [
        SecretStrInput(
            name="bot_token",
            display_name="Токен бота",
            required=True,
            password=True,
            info="Токен вашего Telegram бота, полученный от @BotFather",
        ),
        MultilineInput(
            name="url",
            display_name="Webhook URL",
            value="BACKEND_URL",
            required=True,
            info=(
                "HTTPS URL для отправки обновлений от Telegram. Формат: "
                "https://your-langflow-server/api/v1/webhook/{flow_id}. "
                "Где взять URL: 1) Скопируйте из поля 'Endpoint' компонента TelegramWebhook в вашем потоке, "
                "2) Или найдите Flow ID в URL потока (после /flow/) и подставьте в формат выше, "
                "3) Или откройте API Access pane потока и скопируйте URL из вкладки 'Webhook curl'. "
                "Используйте пустую строку для удаления webhook. URL должен быть HTTPS с валидным SSL сертификатом."
            ),
            tool_mode=True,
            copy_field=True,
            input_types=[],
        ),
        BoolInput(
            name="auto_generate_secret",
            display_name="Автоматически генерировать secret token",
            value=False,
            info=(
                "Если включено, secret token будет автоматически сгенерирован "
                "на основе flow_id и node_id (в стиле n8n). "
                "Если выключено, используйте поле 'Секретный токен' для ручной настройки."
            ),
            advanced=True,
        ),
        MessageTextInput(
            name="secret_token",
            display_name="Секретный токен",
            required=False,
            info=(
                "Секретный токен, который будет отправляться в заголовке 'X-Telegram-Bot-Api-Secret-Token' "
                "в каждом webhook запросе. 1-256 символов. Используется только если "
                "'Автоматически генерировать secret token' выключено."
            ),
            advanced=True,
        ),
        StrInput(
            name="certificate",
            display_name="Путь к файлу сертификата",
            required=False,
            info="Путь к файлу публичного ключа сертификата (формат PEM). Только для самоподписанных сертификатов.",
            advanced=True,
        ),
        IntInput(
            name="max_connections",
            display_name="Максимум соединений",
            required=False,
            value=40,
            info=(
                "Максимально допустимое количество одновременных HTTPS соединений к webhook для доставки обновлений, "
                "1-100. По умолчанию 40."
            ),
            advanced=True,
        ),
        StrInput(
            name="allowed_updates",
            display_name="Разрешенные обновления",
            required=False,
            info=(
                "Список типов обновлений, на которые подписан бот, разделенных запятыми. "
                "По умолчанию все типы обновлений."
            ),
            advanced=True,
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
        """Устанавливает webhook URL для Telegram Bot API."""
        if not self.bot_token:
            msg = "Требуется токен бота"
            raise ValueError(msg)
        if not self.url:
            msg = "Требуется Webhook URL. Используйте пустую строку для удаления webhook."
            raise ValueError(msg)

        url = f"https://api.telegram.org/bot{self.bot_token}/setWebhook"

        payload = {
            "url": self.url,
        }

        # Генерация secret token
        secret_token_to_use = None
        if self.auto_generate_secret:
            # Пытаемся получить flow_id и node_id из контекста
            flow_id = None
            node_id = None

            try:
                if hasattr(self, "graph") and self.graph:
                    flow_id = getattr(self.graph, "flow_id", None)
                if hasattr(self, "_id"):
                    node_id = self._id
                elif hasattr(self, "__config") and "_id" in self.__config:
                    node_id = self.__config["_id"]
            except (AttributeError, TypeError, KeyError) as e:
                await logger.adebug(f"Не удалось определить flow_id/node_id для secret token: {e}")

            secret_token_to_use = _generate_secret_token(flow_id, node_id)
            if secret_token_to_use:
                payload["secret_token"] = secret_token_to_use
                await logger.ainfo(f"Автоматически сгенерирован secret token: {secret_token_to_use[:10]}...")
        elif self.secret_token:
            secret_token_to_use = self.secret_token
            payload["secret_token"] = secret_token_to_use

        if self.max_connections:
            max_conn = int(self.max_connections)
            if max_conn < 1 or max_conn > MAX_CONNECTIONS_LIMIT:
                msg = "Максимум соединений должен быть между 1 и 100"
                raise ValueError(msg)
            payload["max_connections"] = max_conn

        if self.allowed_updates:
            allowed_list = [update.strip() for update in self.allowed_updates.split(",") if update.strip()]
            if allowed_list:
                payload["allowed_updates"] = allowed_list

        if self.drop_pending_updates:
            payload["drop_pending_updates"] = True

        files = None
        if self.certificate:
            try:
                cert_path = Path(self.certificate)
                if not cert_path.exists():
                    msg = f"Файл сертификата не найден: {self.certificate}"
                    raise ValueError(msg)
                cert_content = await asyncio.to_thread(cert_path.read_bytes)
                files = {"certificate": ("certificate.pem", cert_content, "application/x-pem-file")}
            except FileNotFoundError:
                msg = f"Файл сертификата не найден: {self.certificate}"
                raise ValueError(msg) from None
            except Exception as e:
                msg = f"Ошибка чтения файла сертификата: {e}"
                raise ValueError(msg) from e

        try:
            async with httpx.AsyncClient() as client:
                if files:
                    response = await client.post(
                        url,
                        data=payload,
                        files=files,
                        timeout=30.0,
                    )
                else:
                    response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                response_data = response.json()

                if not response_data.get("ok"):
                    error_description = response_data.get("description", "Неизвестная ошибка")
                    await logger.aerror(f"Ошибка Telegram API: {error_description}")
                    self.status = f"Ошибка Telegram API: {error_description}"
                    raise ValueError(self.status)

                result = response_data.get("result", {})
                description = response_data.get("description", "")
                await logger.ainfo(f"Webhook {'установлен' if self.url else 'удален'} успешно: {description}")

                return Data(
                    value={"ok": True, "description": description, "result": result},
                    data={"response": response_data},
                )

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
