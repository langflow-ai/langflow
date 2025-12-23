import json
from pathlib import Path
from typing import Any

import httpx

from lfx.io import BoolInput, DropdownInput, MultilineInput
from lfx.log.logger import logger

REPLY_MARKUP_TYPE_NONE = "None"
REPLY_MARKUP_TYPE_INLINE = "Inline Keyboard"
REPLY_MARKUP_TYPE_REPLY = "Reply Keyboard"
REPLY_MARKUP_TYPE_FORCE_REPLY = "Force Reply"
REPLY_MARKUP_TYPE_REMOVE = "Reply Keyboard Remove"

REPLY_MARKUP_TYPE_OPTIONS = [
    REPLY_MARKUP_TYPE_NONE,
    REPLY_MARKUP_TYPE_INLINE,
    REPLY_MARKUP_TYPE_REPLY,
    REPLY_MARKUP_TYPE_FORCE_REPLY,
    REPLY_MARKUP_TYPE_REMOVE,
]


def reply_markup_inputs(*, advanced: bool = True) -> list[Any]:
    return [
        DropdownInput(
            name="reply_markup_type",
            display_name="Reply Markup",
            options=REPLY_MARKUP_TYPE_OPTIONS,
            value=REPLY_MARKUP_TYPE_NONE,
            required=False,
            advanced=advanced,
            info=(
                "Выберите тип разметки интерфейса для сообщения. "
                "Inline Keyboard — кнопки под сообщением; Reply Keyboard — кастомная клавиатура; "
                "Force Reply — принудительный ответ; Reply Keyboard Remove — убрать клавиатуру."
            ),
        ),
        MultilineInput(
            name="reply_markup_json",
            display_name="Reply Markup JSON",
            required=False,
            advanced=advanced,
            info=(
                "JSON-структура клавиатуры. "
                "Для Inline Keyboard ожидается массив рядов кнопок: [[{text, callback_data|url, ...}], ...]. "
                'Для Reply Keyboard — массив рядов кнопок: [[{text, ...}] или ["text"]].'
            ),
        ),
        BoolInput(
            name="reply_markup_selective",
            display_name="Selective",
            value=False,
            required=False,
            advanced=advanced,
            info=(
                "Если включено, клавиатура/force reply будет показана только упомянутым пользователям "
                "или отправителю исходного сообщения (в зависимости от контекста)."
            ),
        ),
        BoolInput(
            name="reply_keyboard_resize",
            display_name="Resize Keyboard",
            value=True,
            required=False,
            advanced=advanced,
            info="Только для Reply Keyboard: запросить Telegram уменьшить высоту клавиатуры.",
        ),
        BoolInput(
            name="reply_keyboard_one_time",
            display_name="One Time Keyboard",
            value=False,
            required=False,
            advanced=advanced,
            info="Только для Reply Keyboard: скрыть клавиатуру после нажатия кнопки.",
        ),
    ]


def _parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        msg = f"Некорректный JSON: {e.msg}"
        raise ValueError(msg) from e


def build_reply_markup(
    *,
    reply_markup_type: str | None,
    reply_markup_json: str | None,
    selective: bool = False,
    reply_keyboard_resize: bool = True,
    reply_keyboard_one_time: bool = False,
    allowed_types: set[str] | None = None,
) -> dict[str, Any] | None:
    if not reply_markup_type or reply_markup_type == REPLY_MARKUP_TYPE_NONE:
        return None

    if allowed_types is not None and reply_markup_type not in allowed_types:
        msg = f"Reply Markup '{reply_markup_type}' не поддерживается для этой операции."
        raise ValueError(msg)

    if reply_markup_type == REPLY_MARKUP_TYPE_INLINE:
        if not reply_markup_json:
            msg = "Для Inline Keyboard требуется заполнить Reply Markup JSON."
            raise ValueError(msg)
        inline_keyboard = _parse_json(reply_markup_json)
        if not isinstance(inline_keyboard, list):
            msg = "Inline Keyboard JSON должен быть массивом рядов кнопок."
            raise ValueError(msg)
        return {"inline_keyboard": inline_keyboard}

    if reply_markup_type == REPLY_MARKUP_TYPE_REPLY:
        if not reply_markup_json:
            msg = "Для Reply Keyboard требуется заполнить Reply Markup JSON."
            raise ValueError(msg)
        keyboard = _parse_json(reply_markup_json)
        if not isinstance(keyboard, list):
            msg = "Reply Keyboard JSON должен быть массивом рядов кнопок."
            raise ValueError(msg)
        normalized_rows: list[list[dict[str, Any]]] = []
        for row in keyboard:
            if not isinstance(row, list):
                msg = "Каждый ряд Reply Keyboard должен быть массивом кнопок."
                raise ValueError(msg)
            norm_row: list[dict[str, Any]] = []
            for btn in row:
                if isinstance(btn, str):
                    norm_row.append({"text": btn})
                elif isinstance(btn, dict):
                    norm_row.append(btn)
                else:
                    msg = "Кнопка Reply Keyboard должна быть строкой или объектом."
                    raise ValueError(msg)
            normalized_rows.append(norm_row)

        reply_markup: dict[str, Any] = {
            "keyboard": normalized_rows,
            "resize_keyboard": bool(reply_keyboard_resize),
            "one_time_keyboard": bool(reply_keyboard_one_time),
        }
        if selective:
            reply_markup["selective"] = True
        return reply_markup

    if reply_markup_type == REPLY_MARKUP_TYPE_FORCE_REPLY:
        reply_markup = {"force_reply": True}
        if selective:
            reply_markup["selective"] = True
        return reply_markup

    if reply_markup_type == REPLY_MARKUP_TYPE_REMOVE:
        reply_markup = {"remove_keyboard": True}
        if selective:
            reply_markup["selective"] = True
        return reply_markup

    msg = f"Неизвестный Reply Markup: {reply_markup_type}"
    raise ValueError(msg)


async def make_telegram_request(
    *,
    bot_token: str,
    method: str,
    json_payload: dict[str, Any] | None = None,
    data_payload: dict[str, Any] | None = None,
    files: dict[str, tuple[str, Any, str]] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"

    try:
        async with httpx.AsyncClient() as client:
            if files is not None:
                response = await client.post(url, data=data_payload or {}, files=files, timeout=timeout)
            else:
                response = await client.post(url, json=json_payload or {}, timeout=timeout)

            response.raise_for_status()
            response_data = response.json()

            if not response_data.get("ok"):
                error_description = response_data.get("description", "Неизвестная ошибка")
                await logger.aerror(f"Ошибка Telegram API: {error_description}")
                msg = f"Ошибка Telegram API: {error_description}"
                raise ValueError(msg)

            return response_data

    except httpx.HTTPStatusError as e:
        error_msg = f"Произошла HTTP ошибка: {e.response.status_code}"
        if e.response.text:
            try:
                error_data = e.response.json()
                error_msg = error_data.get("description", error_msg)
            except Exception:  # noqa: BLE001
                error_msg = f"{error_msg} - {e.response.text}"
        await logger.aerror(error_msg)
        raise ValueError(error_msg) from e

    except httpx.RequestError as e:
        error_msg = f"Запрос не выполнен: {e}"
        await logger.aerror(error_msg)
        raise ValueError(error_msg) from e

    except Exception as e:
        error_msg = f"Неожиданная ошибка: {e!s}"
        await logger.aerror(error_msg)
        raise ValueError(error_msg) from e


def open_file_for_telegram(file_path: str) -> tuple[str, Any, str]:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        msg = f"Файл не найден: {file_path}"
        raise ValueError(msg)
    return (path.name, path.open("rb"), "application/octet-stream")


def dumps_reply_markup_for_multipart(reply_markup: dict[str, Any] | None) -> str | None:
    if reply_markup is None:
        return None
    return json.dumps(reply_markup, ensure_ascii=False)
