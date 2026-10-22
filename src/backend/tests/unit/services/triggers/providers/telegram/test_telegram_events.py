"""Strict target filtering and Telegram message correlation."""

from copy import deepcopy

import pytest
from langflow.services.triggers.providers.telegram.config import normalize_config
from langflow.services.triggers.providers.telegram.events import canonical, normalize

from .telegram_test_support import TOKEN

CONFIG = {"allowed_chats": ["-1001234"], "allowed_senders": [], "session_scope": "thread"}
UPDATE = {
    "update_id": 9,
    "message": {
        "message_id": 7,
        "chat": {"id": -1001234, "type": "supergroup"},
        "from": {"id": 42, "is_bot": False},
        "text": "/help@example_bot details",
        "message_thread_id": 4,
        "is_topic_message": True,
        "entities": [{"type": "bot_command", "offset": 0, "length": 17}],
    },
}


def event(update=None, kind="telegram.message", config=None):
    return normalize(
        update or UPDATE, kind=kind, config=config or CONFIG, bot_id="123456789", bot_username="example_bot"
    )


def test_command_target_and_session_correlation():
    result = event(kind="telegram.command")
    assert result["command"] == "help"
    assert result["arguments"] == "details"
    assert result["session_key"] == "telegram:123456789:-1001234:thread:4"
    assert canonical(result)["id"] == "9"
    assert event(config={**CONFIG, "session_scope": "sender"})["session_key"].endswith(":sender:42")
    assert event(config={**CONFIG, "session_scope": "chat"})["session_key"] == "telegram:123456789:-1001234"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("chat", {"id": -99, "type": "supergroup"}),
        ("from", {"id": 42, "is_bot": True}),
        ("from", {}),
        ("message_id", True),
        ("text", None),
        ("message_thread_id", -1),
    ],
)
def test_unrelated_or_invalid_messages_never_fire(field, value):
    update = deepcopy(UPDATE)
    update["message"][field] = value
    assert event(update) is None


def test_other_bot_command_and_sender_filters_never_fire():
    update = deepcopy(UPDATE)
    update["message"]["text"] = "/help@another_bot details"
    assert event(update, kind="telegram.command") is None
    assert event(config={**CONFIG, "allowed_senders": ["99"]}) is None
    assert event(kind="telegram.command", config={**CONFIG, "commands": ["start"]}) is None


def test_plain_text_is_not_a_command_without_entity():
    update = deepcopy(UPDATE)
    update["message"]["entities"] = []
    assert event(update, kind="telegram.command") is None
    assert event(update) is not None


def test_unknown_update_fields_and_bot_tokens_do_not_enter_payload():
    update = deepcopy(UPDATE)
    update["message"]["text"] = f"token {TOKEN}"
    update["message"]["token"] = TOKEN
    update["private_key"] = "private"  # pragma: allowlist secret - synthetic ignored field
    result = event(update)
    assert TOKEN not in str(result)
    assert "private_key" not in str(result)
    assert result["text"].endswith("[redacted bot token]")


@pytest.mark.parametrize(
    "raw",
    [
        {"allowed_chats": [True]},
        {"allowed_chats": ["1", "1"]},
        {"allowed_chats": "1"},
        {"allowed_senders": ["-1"]},
        {"session_scope": "invalid"},
        {"delivery_mode": "socket"},
        {"connection": "slack/bot"},
        {"commands": ["/help"]},
    ],
)
def test_invalid_configuration_is_rejected(raw):
    with pytest.raises(ValueError, match=r"Telegram|Unsupported|Choose"):
        normalize_config("telegram.command", raw)


def test_configuration_remains_credential_free_and_manual_builds_allow_empty_chats():
    config = normalize_config("telegram.message", {"connection": "telegram/bot", "allowed_chats": [-1001234]})
    assert config["allowed_chats"] == ["-1001234"]
    assert normalize_config("telegram.message", {})["allowed_chats"] == []


@pytest.mark.parametrize(
    ("chat_type", "topic", "expected_thread"),
    [("supergroup", False, None), ("supergroup", True, "4"), ("private", False, None), ("private", True, "4")],
)
async def test_only_forum_topics_become_reply_destinations(monkeypatch, chat_type, topic, expected_thread):
    from lfx.schema.data import Data
    from lfx_telegram import TelegramReplyComponent

    from .telegram_test_support import BOT, BotTransport, Resolver, component

    update = deepcopy(UPDATE)
    update["message"]["chat"]["type"] = chat_type
    if topic:
        update["message"]["is_topic_message"] = True
    else:
        update["message"].pop("is_topic_message", None)
        update["message"]["reply_to_message"] = {"message_id": 4}
    if chat_type == "private":
        update["message"]["chat"]["id"] = 42
    config = {**CONFIG, "allowed_chats": [str(update["message"]["chat"]["id"])]}
    normalized = event(update, config=config)
    assert normalized["thread_id"] == expected_thread
    assert normalized["session_key"].endswith(f":thread:{expected_thread or 0}")

    resolver = Resolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    transport = BotTransport([BOT, {"message_id": 8, "text": "reply"}]).install(monkeypatch)
    reply = component(TelegramReplyComponent, event=Data(data=canonical(normalized)), text="reply")
    await reply.build_message()
    method, payload = transport.calls[-1]
    assert method == "sendMessage"
    assert payload["chat_id"] == update["message"]["chat"]["id"]
    assert payload["reply_parameters"] == {"message_id": 7, "allow_sending_without_reply": False}
    if expected_thread is None:
        assert "message_thread_id" not in payload
    else:
        assert payload["message_thread_id"] == int(expected_thread)
