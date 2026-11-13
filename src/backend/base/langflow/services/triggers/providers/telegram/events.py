"""Normalize new text messages into bounded, credential-free flow events."""

from __future__ import annotations

import re
from typing import Any

from lfx_telegram._client import redact
from lfx_telegram._validation import MAX_TELEGRAM_ID

MAX_MESSAGE_TEXT = 16384
MAX_COMMAND_ENTITY_UNITS = 66


def _identifier(value: Any, *, positive: bool = False) -> bool:
    return type(value) is int and value != 0 and abs(value) <= MAX_TELEGRAM_ID and (not positive or value > 0)


def normalize(update: Any, *, kind: str, config: dict, bot_id: str, bot_username: str) -> dict | None:
    """Read only messages and commands whose target filters match this receiver."""
    if (
        not isinstance(update, dict)
        or type(update.get("update_id")) is not int
        or not 0 <= update["update_id"] <= MAX_TELEGRAM_ID
    ):
        return None
    message = update.get("message")
    if not isinstance(message, dict) or not _identifier(message.get("message_id"), positive=True):
        return None
    chat = message.get("chat")
    sender = message.get("from")
    if not isinstance(chat, dict) or not _identifier(chat.get("id")):
        return None
    if str(chat["id"]) not in config.get("allowed_chats", []):
        return None
    if chat.get("type") not in {"private", "group", "supergroup"}:
        return None
    if (
        not isinstance(sender, dict)
        or not _identifier(sender.get("id"), positive=True)
        or sender.get("is_bot") is not False
    ):
        return None
    sender_id = str(sender["id"])
    senders = config.get("allowed_senders") or []
    if senders and sender_id not in senders:
        return None
    text = message.get("text")
    if not isinstance(text, str) or len(text) > MAX_MESSAGE_TEXT:
        return None
    thread = message.get("message_thread_id")
    if thread is not None and not _identifier(thread, positive=True):
        return None
    # Ordinary supergroup replies also have message_thread_id. Only topic
    # messages may reuse it as sendMessage's forum destination.
    if message.get("is_topic_message") is not True or chat.get("type") not in {"supergroup", "private"}:
        thread = None
    command = None
    arguments = None
    entities = message.get("entities")
    for entity in entities if isinstance(entities, list) else []:
        if not isinstance(entity, dict) or entity.get("type") != "bot_command" or entity.get("offset") != 0:
            continue
        length = entity.get("length")
        if type(length) is not int or not 1 < length <= MAX_COMMAND_ENTITY_UNITS:
            continue
        encoded = text.encode("utf-16-le", errors="surrogatepass")
        try:
            token = encoded[: length * 2].decode("utf-16-le")
        except UnicodeDecodeError:
            continue
        match = re.fullmatch(r"/([a-z0-9_]{1,32})(?:@([A-Za-z0-9_]{5,32}))?", token)
        if match is None:
            continue
        if match[2] is not None and match[2].casefold() != bot_username.casefold():
            return None
        command = match[1]
        arguments = encoded[length * 2 :].decode("utf-16-le", errors="replace").strip()
        break
    if kind == "telegram.command":
        if command is None or (config.get("commands") and command not in config["commands"]):
            return None
    elif kind != "telegram.message":
        return None
    scope = config.get("session_scope", "thread")
    session = f"telegram:{bot_id}:{chat['id']}"
    if scope == "sender":
        session += f":sender:{sender_id}"
    elif scope == "thread":
        session += f":thread:{thread or 0}"
    return redact(
        {
            "provider": "telegram",
            "bot_id": bot_id,
            "update_id": update["update_id"],
            "message_id": message["message_id"],
            "chat_id": str(chat["id"]),
            "chat_type": chat["type"],
            "sender_id": sender_id,
            "thread_id": str(thread) if thread is not None else None,
            "session_key": session,
            "text": text,
            "command": command,
            "arguments": arguments,
        }
    )


def canonical(event: dict) -> dict:
    return {
        "provider": "telegram",
        "resource": f"bot:{event['bot_id']}",
        "id": str(event["update_id"]),
        "version": "1",
        "deleted": False,
        "data": event,
        "session_key": event["session_key"],
    }
