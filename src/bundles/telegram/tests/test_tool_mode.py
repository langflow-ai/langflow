"""Telegram tool calls retain the configured bot and trusted reply target."""

from types import SimpleNamespace

import pytest
from conftest import BOT, BotTransport, Resolver
from lfx.schema.data import Data
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_telegram import TelegramNotifyComponent, TelegramReplyComponent, TelegramSendMessageComponent


def tool_component(component_class, **kwargs):
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="actor", user_id="test-user", interactive=True),
        flow_id="test-flow",
        run_id="test-run",
        session_id="test-session",
    )
    return component_class(connection="telegram/bot", _vertex=SimpleNamespace(graph=graph, outputs=[]), **kwargs)


@pytest.mark.parametrize(
    ("component_class", "arguments", "silent_default"),
    [
        (TelegramSendMessageComponent, {"chat_id", "text", "thread_id", "silent"}, False),
        (TelegramNotifyComponent, {"chat_id", "text", "thread_id", "silent"}, True),
        (TelegramReplyComponent, {"text"}, None),
    ],
)
async def test_action_schemas_keep_the_connection_and_reply_event_configured(
    component_class, arguments, silent_default
):
    [tool] = await tool_component(component_class).to_toolkit()

    assert set(tool.args_schema.model_fields) == arguments
    assert {"connection", "event"}.isdisjoint(tool.args_schema.model_fields)
    if silent_default is not None:
        assert tool.args_schema.model_fields["silent"].default is silent_default


@pytest.mark.parametrize(
    ("component_class", "silent_default"),
    [(TelegramSendMessageComponent, False), (TelegramNotifyComponent, True)],
)
async def test_message_tools_use_each_calls_arguments_and_preserve_the_execution_principal(
    monkeypatch, resolver: Resolver, component_class, silent_default
):
    transport = BotTransport(
        [BOT, {"message_id": 7, "text": "first"}, BOT, {"message_id": 8, "text": "second"}]
    ).install(monkeypatch)
    [tool] = await tool_component(component_class).to_toolkit()

    first = await tool.ainvoke({"chat_id": "-1001234", "text": "first", "thread_id": "4"})
    second = await tool.ainvoke({"chat_id": "-1005678", "text": "second", "silent": not silent_default})

    assert [first["message_id"], second["message_id"]] == [7, 8]
    assert transport.calls == [
        ("getMe", {}),
        (
            "sendMessage",
            {"chat_id": -1001234, "text": "first", "message_thread_id": 4, "disable_notification": silent_default},
        ),
        ("getMe", {}),
        ("sendMessage", {"chat_id": -1005678, "text": "second", "disable_notification": not silent_default}),
    ]
    assert all(request.principal.user_id == "test-user" for request in resolver.calls)
    assert all(request.ref.name == "bot" for request in resolver.calls)
    assert all(request.flow_id == "test-flow" for request in resolver.calls)


async def test_reply_tool_uses_the_configured_event_and_agent_text(monkeypatch, resolver: Resolver):
    event = {"provider": "telegram", "bot_id": "123456789", "chat_id": "-1001234", "thread_id": "4", "message_id": 7}
    transport = BotTransport(
        [BOT, {"message_id": 8, "text": "first"}, BOT, {"message_id": 9, "text": "second"}]
    ).install(monkeypatch)
    [tool] = await tool_component(TelegramReplyComponent, event=Data(data={"payload": {"data": event}})).to_toolkit()

    await tool.ainvoke({"text": "first"})
    await tool.ainvoke({"text": "second"})

    messages = [payload for method, payload in transport.calls if method == "sendMessage"]
    assert [message["text"] for message in messages] == ["first", "second"]
    assert all(message["chat_id"] == -1001234 for message in messages)
    assert all(message["message_thread_id"] == 4 for message in messages)
    assert all(
        message["reply_parameters"] == {"message_id": 7, "allow_sending_without_reply": False} for message in messages
    )
    assert all(request.principal.user_id == "test-user" for request in resolver.calls)


async def test_reply_tool_rejects_a_different_bot_before_sending(monkeypatch, resolver: Resolver):
    event = {"provider": "telegram", "bot_id": "987654321", "chat_id": "-1001234", "message_id": 7}
    transport = BotTransport([BOT]).install(monkeypatch)
    [tool] = await tool_component(TelegramReplyComponent, event=Data(data=event)).to_toolkit()

    refused = await tool.ainvoke({"text": "wrong bot"})

    assert isinstance(refused, str)
    assert "not authorized" in refused.lower()
    assert transport.calls == [("getMe", {})]
    assert resolver.calls[0].principal.user_id == "test-user"
