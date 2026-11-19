"""Polling acknowledgement follows the persisted source cursor."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.triggers.providers.telegram.polling import _offset, collect
from langflow.services.triggers.source_errors import SourceConfigurationError

from .telegram_test_support import BOT, BotTransport, lease
from .test_telegram_events import CONFIG, UPDATE


def trigger(state=None, mechanism="telegram.get_updates"):
    return SimpleNamespace(
        kind="telegram.message",
        config={**CONFIG, "mechanism_id": mechanism},
        provider_state=state or {"bot_id": "123456789"},
        connection_id=uuid4(),
    )


async def test_first_page_does_not_confirm_uncommitted_updates(monkeypatch):
    transport = BotTransport([BOT, {"url": ""}, [UPDATE]]).install(monkeypatch)
    source = trigger()
    result = await collect(source, lease())
    assert result.cursor["offset"] == 10
    assert result.previous_cursor == {"bot_id": "123456789"}
    assert source.provider_state == result.previous_cursor
    assert transport.calls[-1] == ("getUpdates", {"limit": 100, "timeout": 20, "allowed_updates": ["message"]})
    assert result.items[0]["data"]["chat_id"] == "-1001234"
    assert result.baseline is False


async def test_next_round_confirms_only_persisted_offset_and_clears_after_empty_page(monkeypatch):
    transport = BotTransport([BOT, {"url": ""}, []]).install(monkeypatch)
    source = trigger({"bot_id": "123456789", "offset": 10, "last_fetch_at": datetime.now(timezone.utc).isoformat()})
    result = await collect(source, lease())
    assert transport.calls[-1][1]["offset"] == 10
    assert result.cursor["offset"] is None


async def test_existing_webhook_is_never_removed_for_polling(monkeypatch):
    transport = BotTransport([BOT, {"url": "https://other.invalid/hook"}]).install(monkeypatch)
    with pytest.raises(SourceConfigurationError):
        await collect(trigger(), lease())
    assert [method for method, _ in transport.calls] == ["getMe", "getWebhookInfo"]


async def test_webhook_trigger_never_uses_get_updates(monkeypatch):
    transport = BotTransport([]).install(monkeypatch)
    with pytest.raises(SourceConfigurationError):
        await collect(trigger(mechanism="telegram.webhook"), lease())
    assert transport.calls == []


@pytest.mark.parametrize(
    "updates",
    [[{"update_id": True}], [{"update_id": 4}, {"update_id": 3}], [{"update_id": 4}, {"update_id": 4}], "bad"],
)
async def test_invalid_pages_do_not_advance_cursor(monkeypatch, updates):
    BotTransport([BOT, {"url": ""}, updates]).install(monkeypatch)
    source = trigger()
    with pytest.raises(SourceConfigurationError):
        await collect(source, lease())
    assert source.provider_state == {"bot_id": "123456789"}


def test_stale_offset_is_not_sent_after_a_week():
    now = datetime.now(timezone.utc)
    assert _offset({"offset": 999, "last_fetch_at": (now - timedelta(days=8)).isoformat()}, now) is None
    assert _offset({"offset": True, "last_fetch_at": now.isoformat()}, now) is None


async def test_failed_commit_replays_without_confirming_new_offset(monkeypatch):
    transport = BotTransport([BOT, {"url": ""}, [UPDATE], BOT, {"url": ""}, [UPDATE]]).install(monkeypatch)
    source = trigger()
    first = await collect(source, lease())
    # The caller rolls back rather than applying first.cursor.
    second = await collect(source, lease())
    requests = [payload for method, payload in transport.calls if method == "getUpdates"]
    assert len(requests) == 2
    assert all("offset" not in payload for payload in requests)
    assert first.items == second.items
    assert source.provider_state == {"bot_id": "123456789"}
