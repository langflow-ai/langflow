"""Validate the bounded Telegram target and message inputs."""

from __future__ import annotations

import re
from typing import Any

from lfx.integrations.errors import InvalidRequestError

MAX_MESSAGE_UNITS = 4096
MAX_TELEGRAM_ID = (1 << 52) - 1


def numeric_id(value: Any, *, positive: bool = False) -> int:
    """Accept exact numeric identifiers without float rounding or coercion."""
    if type(value) is int:
        result = value
    elif isinstance(value, str) and re.fullmatch(r"-?[1-9][0-9]{0,15}", value):
        result = int(value)
    else:
        msg = "Use a numeric Telegram ID."
        raise InvalidRequestError(msg, provider="telegram")
    if result == 0 or abs(result) > MAX_TELEGRAM_ID or (positive and result < 0):
        msg = "The Telegram ID is outside the supported range."
        raise InvalidRequestError(msg, provider="telegram")
    return result


def message_payload(
    *, chat_id: Any, text: Any, thread_id: Any = None, reply_id: Any = None, silent: bool = False
) -> dict[str, Any]:
    """Build one plain-text send without an arbitrary API destination."""
    if (
        not isinstance(text, str)
        or not text.strip()
        or len(text.encode("utf-16-le", errors="surrogatepass")) // 2 > MAX_MESSAGE_UNITS
    ):
        msg = "Telegram messages need 1 to 4096 UTF-16 characters."
        raise InvalidRequestError(msg, provider="telegram")
    if type(silent) is not bool:
        msg = "The notification setting must be a boolean."
        raise InvalidRequestError(msg, provider="telegram")
    payload: dict[str, Any] = {"chat_id": numeric_id(chat_id), "text": text, "disable_notification": silent}
    if thread_id is not None and thread_id != "":
        payload["message_thread_id"] = numeric_id(thread_id, positive=True)
    if reply_id is not None and reply_id != "":
        payload["reply_parameters"] = {
            "message_id": numeric_id(reply_id, positive=True),
            "allow_sending_without_reply": False,
        }
    return payload
