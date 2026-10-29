"""Fail closed on Telegram filters before a receiver is enabled."""

from __future__ import annotations

import re
from typing import Any

from lfx.integrations.errors import InvalidRequestError
from lfx.integrations.models import ConnectionRef
from lfx_telegram._validation import numeric_id

MAX_FILTERS = 100
_FIELDS = {"connection", "allowed_chats", "allowed_senders", "session_scope", "delivery_mode", "commands"}


def _ids(raw: Any, *, positive: bool = False) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_FILTERS:
        msg = "Telegram filters must be lists of at most 100 numeric IDs."
        raise ValueError(msg)
    try:
        result = [str(numeric_id(value, positive=positive)) for value in raw]
    except InvalidRequestError:
        msg = "Telegram filters require numeric IDs in the supported range."
        raise ValueError(msg) from None
    if len(set(result)) != len(result):
        msg = "Telegram filter IDs must be unique."
        raise ValueError(msg)
    return result


def normalize_config(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    if kind not in {"telegram.message", "telegram.command"} or set(raw) - _FIELDS:
        msg = "Unsupported Telegram trigger configuration."
        raise ValueError(msg)
    connection = raw.get("connection")
    if connection is not None and connection != "":
        ref = ConnectionRef.parse(connection)
        if ref.provider != "telegram":
            msg = "Choose a Telegram connection for this trigger."
            raise ValueError(msg)
        connection = ref.to_handle()
    chats = _ids(raw.get("allowed_chats"))
    senders = _ids(raw.get("allowed_senders"), positive=True)
    mode = raw.get("delivery_mode")
    mode = "auto" if mode is None or mode == "" else mode
    scope = raw.get("session_scope")
    scope = "thread" if scope is None or scope == "" else scope
    if (
        not isinstance(mode, str)
        or mode not in {"auto", "push", "poll"}
        or not isinstance(scope, str)
        or scope not in {"chat", "sender", "thread"}
    ):
        msg = "Unsupported Telegram delivery or session setting."
        raise ValueError(msg)
    config = {
        "connection": connection,
        "allowed_chats": chats,
        "allowed_senders": senders,
        "session_scope": scope,
        "delivery_mode": mode,
    }
    if kind == "telegram.command":
        commands = raw.get("commands")
        commands = [] if commands is None else commands
        if (
            not isinstance(commands, list)
            or len(commands) > MAX_FILTERS
            or any(
                not isinstance(command, str) or not re.fullmatch(r"[a-z0-9_]{1,32}", command) for command in commands
            )
            or len(set(commands)) != len(commands)
        ):
            msg = "Telegram command filters need unique command names without a slash."
            raise ValueError(msg)
        config["commands"] = commands
    elif raw.get("commands"):
        msg = "Command filters require a Telegram command trigger."
        raise ValueError(msg)
    return config
