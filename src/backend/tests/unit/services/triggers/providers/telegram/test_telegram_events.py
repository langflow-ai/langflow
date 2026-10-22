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
