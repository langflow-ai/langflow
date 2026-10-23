"""Actual Gateway frames exercise durable emission and resume sequencing."""

import asyncio
import json
from uuid import uuid4

import pytest
from langflow.services.triggers.listeners.adapters import ListenerContext, ListenerTrigger
from langflow.services.triggers.providers.discord.config import normalize_config
from langflow.services.triggers.providers.discord.events import normalize
from langflow.services.triggers.providers.discord.gateway import DiscordGatewayAdapter, gateway_url
from lfx.integrations.errors import ConnectionNotAuthorizedError, ProviderUnavailableError, RateLimitedError

from .support import APP, BOT, CHANNEL, GATEWAY, TOKEN, BotTransport, Resolver

CONFIG = {
    "connection": "discord/bot",
    "guild_id": "222",
    "channel_ids": ["333"],
    "session_scope": "channel",
    "delivery_mode": "auto",
    "mechanism_id": "discord.gateway",
}
MESSAGE = {
    "id": "444",
    "guild_id": "222",
    "channel_id": "333",
    "type": 0,
    "author": {"id": "777"},
    "content": "hello",
    "mentions": [{"id": BOT["id"]}],
    "token": "must-not-persist",
}
READY = {
    "user": BOT,
    "application": {"id": BOT["id"]},
    "session_id": "synthetic-session",
    "resume_gateway_url": "wss://gateway.discord.gg/",
}


def snapshot(kind="discord.message", state=None):
    return ListenerTrigger(
        id=uuid4(),
        flow_id=uuid4(),
        user_id=uuid4(),
        kind=kind,
        provider="discord",
        mechanism_id="discord.gateway",
        config=dict(CONFIG),
        provider_state=state or {"bot_id": BOT["id"]},
    )


class Socket:
    def __init__(self, frames):
        self.frames = asyncio.Queue()
        for item in frames:
            self.frames.put_nowait(json.dumps(item))
        self.sent = []
        self.closed = []

    async def recv(self):
        return await self.frames.get()

    async def send(self, data):
        self.sent.append(json.loads(data))

    async def close(self, code=1000):
        self.closed.append(code)


async def execute(monkeypatch, frames, *, trigger=None, responses=None, emit_error=False):
    trigger = trigger or snapshot()
    transport = BotTransport(responses or [BOT, APP, CHANNEL, GATEWAY]).install(monkeypatch)
    socket = Socket([{"op": 10, "d": {"heartbeat_interval": 45000}}, *frames])
    dialed = []

    async def connect(url, **kwargs):
        dialed.append((url, kwargs))
        return socket

    monkeypatch.setattr("langflow.services.triggers.providers.discord.gateway.ws_connect", connect)
    events = []
    saved = []
    order = []
    stopping = asyncio.Event()

    async def emit(**kwargs):
        order.append("emit")
        if emit_error:
            msg = "ledger unavailable"
            raise RuntimeError(msg)
        events.append(kwargs)
        return True

    async def save(**kwargs):
        saved.append(kwargs["provider_state"])
        order.append("save")

    async def resolve(**_kwargs):
        return await Resolver().resolve(None)

    ctx = ListenerContext(
        connection_id=uuid4(),
        triggers=[trigger],
        emit=emit,
        save_cursor=save,
        resolve_credential=resolve,
        stopping=stopping,
    )
    adapter = DiscordGatewayAdapter(trigger)
    return adapter, ctx, socket, events, saved, order, dialed, transport


async def test_identify_commits_event_before_sequence_and_discards_interaction_tokens(monkeypatch):
    adapter, ctx, socket, events, saved, order, dialed, _transport = await execute(
        monkeypatch,
        [
            {"op": 0, "t": "READY", "s": 1, "d": READY},
            {"op": 0, "t": "MESSAGE_CREATE", "s": 2, "d": MESSAGE},
            {"op": 7},
        ],
    )
    with pytest.raises(ProviderUnavailableError):
        await adapter.start(ctx)
    assert socket.sent[0]["op"] == 2
    assert socket.sent[0]["d"]["intents"] == 1 | (1 << 9) | (1 << 15)
    assert saved[-1]["seq"] == 2
    assert order[-2:] == ["emit", "save"]
    assert events[0]["dedupe_key"] == "discord:message:444"
    assert "must-not-persist" not in json.dumps(events, default=str)
    assert TOKEN not in json.dumps(saved)
    assert dialed[0][0] == "wss://gateway.discord.gg/?v=10&encoding=json"
    assert dialed[0][1]["logger"].isEnabledFor(10) is False
    assert socket.closed == [4000]


async def test_resume_uses_saved_sequence_and_no_identify_budget(monkeypatch):
    trigger = snapshot(
        state={
            "bot_id": BOT["id"],
            "session_id": "saved-session",
            "seq": 5,
            "resume_url": "wss://resume.gateway.discord.gg/",
        }
    )
    adapter, ctx, socket, _events, saved, _order, _dialed, transport = await execute(
        monkeypatch,
        [{"op": 0, "t": "MESSAGE_CREATE", "s": 6, "d": MESSAGE}, {"op": 0, "t": "RESUMED", "s": 7, "d": {}}, {"op": 7}],
        trigger=trigger,
        responses=[BOT, APP, CHANNEL],
    )
    with pytest.raises(ProviderUnavailableError):
        await adapter.start(ctx)
    assert socket.sent[0] == {"op": 6, "d": {"token": TOKEN, "session_id": "saved-session", "seq": 5}}
    assert saved[-1]["seq"] == 7
    assert not any("gateway/bot" in call[1] for call in transport.calls)


async def test_ledger_failure_never_advances_failed_message_sequence(monkeypatch):
    adapter, ctx, _socket, _events, saved, *_ = await execute(
        monkeypatch,
        [{"op": 0, "t": "READY", "s": 1, "d": READY}, {"op": 0, "t": "MESSAGE_CREATE", "s": 2, "d": MESSAGE}],
        emit_error=True,
    )
    with pytest.raises(RuntimeError, match="ledger"):
        await adapter.start(ctx)
    assert saved[-1]["seq"] == 1


async def test_invalid_session_clears_resume_then_backs_off(monkeypatch):
    adapter, ctx, _socket, _events, saved, *_ = await execute(monkeypatch, [{"op": 9, "d": False}])
    with pytest.raises(RateLimitedError):
        await adapter.start(ctx)
    assert "session_id" not in saved[-1]


async def test_missing_message_content_intent_fails_before_socket(monkeypatch):
    adapter, ctx, _socket, _events, _saved, _order, dialed, _ = await execute(
        monkeypatch, [], responses=[BOT, {**APP, "flags": 0}, CHANNEL]
    )
    with pytest.raises(ConnectionNotAuthorizedError, match="not authorized"):
        await adapter.start(ctx)
    assert not dialed


async def test_mention_receiver_does_not_request_privileged_content(monkeypatch):
    adapter, ctx, socket, *_ = await execute(
        monkeypatch,
        [{"op": 7}],
        trigger=snapshot("discord.mention"),
        responses=[BOT, {**APP, "flags": 0}, CHANNEL, GATEWAY],
    )
    with pytest.raises(ProviderUnavailableError):
        await adapter.start(ctx)
    assert socket.sent[0]["d"]["intents"] == 1 | (1 << 9)


async def test_exhausted_identify_budget_fails_before_socket(monkeypatch):
    info = {**GATEWAY, "session_start_limit": {"remaining": 0, "reset_after": 12000}}
    adapter, ctx, _socket, _events, _saved, _order, dialed, _ = await execute(
        monkeypatch, [], responses=[BOT, APP, CHANNEL, info]
    )
    with pytest.raises(RateLimitedError) as result:
        await adapter.start(ctx)
    assert result.value.retry_after == 12
    assert not dialed


async def test_stop_cancels_receiver_and_never_reconnects(monkeypatch):
    adapter, ctx, socket, *_ = await execute(monkeypatch, [{"op": 0, "t": "READY", "s": 1, "d": READY}])
    task = asyncio.create_task(adapter.start(ctx))
    for _ in range(100):
        if adapter.connected:
            break
        await asyncio.sleep(0.001)
    ctx.stopping.set()
    await asyncio.wait_for(task, 1)
    await adapter.stop()
    await adapter.stop()
    assert socket.closed == [4000]
    assert not adapter.healthy()


@pytest.mark.parametrize(
    "url",
    [
        "ws://gateway.discord.gg/",
        "wss://gateway.discord.gg.evil.test/",
        "wss://evil.test/",
        "wss://a@gateway.discord.gg/",
        "wss://gateway.discord.gg:443/",
        "wss://gateway.discord.gg/?token=bad",
        "wss://127.0.0.1/",
        None,
    ],
)
def test_gateway_origins_fail_closed(url):
    with pytest.raises(ProviderUnavailableError):
        gateway_url(url)


@pytest.mark.parametrize(
    "patch",
    [
        {"guild_id": "999"},
        {"channel_id": "999"},
        {"webhook_id": "1"},
        {"author": {"id": "777", "bot": True}},
        {"author": {"id": BOT["id"]}},
        {"type": 20},
    ],
)
def test_unrelated_and_bot_events_are_dropped(patch):
    assert normalize({**MESSAGE, **patch}, bot_id=BOT["id"], kind="discord.message", config=CONFIG) is None


def test_mentions_and_conversation_keys():
    assert normalize({**MESSAGE, "mentions": []}, bot_id=BOT["id"], kind="discord.mention", config=CONFIG) is None
    event = normalize(MESSAGE, bot_id=BOT["id"], kind="discord.mention", config={**CONFIG, "session_scope": "sender"})
    assert event["session_key"] == "discord:123456789:222:333:777"
    assert set(event) == {
        "provider",
        "bot_id",
        "guild_id",
        "channel_id",
        "message_id",
        "sender_id",
        "text",
        "session_key",
    }


def test_normalizer_accepts_actual_saved_inputs_and_rejects_canvas_origins():
    raw = {k: CONFIG[k] for k in ("connection", "guild_id", "channel_ids", "session_scope", "delivery_mode")}
    assert normalize_config("discord.message", raw) == raw
    assert normalize_config("discord.message", {**raw, "delivery_mode": None})["delivery_mode"] == "auto"
    with pytest.raises(ValueError, match="Unsupported Discord"):
        normalize_config("discord.message", {**raw, "api_url": "https://evil.test"})


async def test_heartbeat_without_ack_closes_socket():
    adapter = DiscordGatewayAdapter(snapshot())
    adapter.ws = Socket([])
    with pytest.raises(ProviderUnavailableError):
        await adapter._heartbeat(0.001)
    assert adapter.ws.sent == [{"op": 1, "d": None}]
    assert adapter.ws.closed == [4000]


async def test_provider_heartbeat_request_and_ack(monkeypatch):
    adapter, ctx, socket, *_ = await execute(monkeypatch, [{"op": 1}, {"op": 11}, {"op": 7}])
    with pytest.raises(ProviderUnavailableError):
        await adapter.start(ctx)
    assert socket.sent[-1] == {"op": 1, "d": None}
    assert adapter.acked is True


async def test_forged_ready_identity_never_saves_session(monkeypatch):
    ready = {**READY, "application": {"id": "999"}}
    adapter, ctx, _socket, events, saved, *_ = await execute(monkeypatch, [{"op": 0, "t": "READY", "s": 1, "d": ready}])
    with pytest.raises(ConnectionNotAuthorizedError):
        await adapter.start(ctx)
    assert not events
    assert "session_id" not in saved[-1]


async def test_replayed_message_retains_same_dedupe_id(monkeypatch):
    adapter, ctx, _socket, events, saved, *_ = await execute(
        monkeypatch,
        [
            {"op": 0, "t": "READY", "s": 1, "d": READY},
            {"op": 0, "t": "MESSAGE_CREATE", "s": 2, "d": MESSAGE},
            {"op": 0, "t": "MESSAGE_CREATE", "s": 3, "d": MESSAGE},
            {"op": 7},
        ],
    )
    with pytest.raises(ProviderUnavailableError):
        await adapter.start(ctx)
    assert len(events) == 2
    assert events[0]["dedupe_key"] == events[1]["dedupe_key"]
    assert saved[-1]["seq"] == 3


@pytest.mark.parametrize(
    "hello",
    [
        {"op": 10, "d": None},
        {"op": 10, "d": {"heartbeat_interval": True}},
        {"op": 10, "d": {"heartbeat_interval": 1}},
        [],
    ],
)
async def test_malformed_hello_closes_socket_before_auth(monkeypatch, hello):
    adapter, ctx, socket, *_ = await execute(monkeypatch, [])
    socket.frames = asyncio.Queue()
    socket.frames.put_nowait(json.dumps(hello))
    with pytest.raises(ProviderUnavailableError):
        await adapter.start(ctx)
    assert not socket.sent
    assert socket.closed == [4000]


async def test_rejected_fenced_delivery_does_not_advance_resume_sequence(monkeypatch):
    from langflow.services.triggers.listeners.adapters import ListenerDeliveryRejectedError

    adapter, ctx, _socket, _events, saved, *_ = await execute(
        monkeypatch,
        [
            {"op": 0, "t": "READY", "s": 1, "d": READY},
            {"op": 0, "t": "MESSAGE_CREATE", "s": 2, "d": MESSAGE},
        ],
    )

    async def rejected(**kwargs):
        assert kwargs["expected_kind"] == ctx.triggers[0].kind
        assert kwargs["expected_config"] == ctx.triggers[0].config
        ctx.stopping.set()
        raise ListenerDeliveryRejectedError(reason="stale-lease")

    ctx.emit = rejected
    with pytest.raises(ListenerDeliveryRejectedError):
        await adapter.start(ctx)
    assert saved[-1]["seq"] == 1
    assert ctx.stopping.is_set()


@pytest.mark.parametrize("text", ["x" * 2001, "x" * 4000, "😀" * 2000], ids=["2001-ascii", "4000-ascii", "4000-utf16"])
def test_nitro_message_content_is_delivered_without_truncation(text):
    event = normalize({**MESSAGE, "content": text}, bot_id=BOT["id"], kind="discord.message", config=CONFIG)
    assert event is not None
    assert event["text"] == text


@pytest.mark.parametrize("text", ["x" * 4001, "😀" * 2001], ids=["4001-ascii", "4002-utf16"])
def test_oversized_inbound_message_is_rejected(text):
    assert normalize({**MESSAGE, "content": text}, bot_id=BOT["id"], kind="discord.message", config=CONFIG) is None
