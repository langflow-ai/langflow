"""Discord tools retain bot identity, guild checks, and configured reply targets."""

from types import SimpleNamespace

import pytest
from conftest import APP, BOT, CHANNEL, TOKEN, BotTransport, Resolver
from lfx.schema.data import Data
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_discord import DiscordReplyComponent, DiscordSendMessageComponent


class RecordingResolver(Resolver):
    def __init__(self):
        self.calls = []

    async def resolve(self, request):
        self.calls.append(request)
        return await super().resolve(request)


@pytest.fixture
def recording_resolver(monkeypatch):
    resolver = RecordingResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    return resolver


def tool_component(component_class, **kwargs):
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="actor", user_id="test-user", interactive=True),
        flow_id="test-flow",
        run_id="test-run",
        session_id="test-session",
    )
    return component_class(connection="discord/bot", _vertex=SimpleNamespace(graph=graph, outputs=[]), **kwargs)


@pytest.mark.parametrize(
    ("component_class", "arguments"),
    [(DiscordSendMessageComponent, {"guild_id", "channel_id", "text"}), (DiscordReplyComponent, {"text"})],
)
async def test_action_schemas_keep_the_connection_and_reply_event_configured(component_class, arguments):
    [tool] = await tool_component(component_class).to_toolkit()

    assert set(tool.args_schema.model_fields) == arguments
    assert {"connection", "event"}.isdisjoint(tool.args_schema.model_fields)


async def test_send_tool_uses_each_calls_arguments_and_preserves_the_execution_principal(
    monkeypatch, recording_resolver
):
    transport = BotTransport(
        [
            BOT,
            APP,
            CHANNEL,
            {"id": "444", "channel_id": "333", "content": "first"},
            BOT,
            APP,
            {**CHANNEL, "id": "555", "guild_id": "666"},
            {"id": "777", "channel_id": "555", "content": "second"},
        ]
    ).install(monkeypatch)
    [tool] = await tool_component(DiscordSendMessageComponent).to_toolkit()

    first = await tool.ainvoke({"guild_id": "222", "channel_id": "333", "text": "first"})
    second = await tool.ainvoke({"guild_id": "666", "channel_id": "555", "text": "second"})

    assert first["message_id"] == "444"
    assert second["message_id"] == "777"
    posts = [call for call in transport.calls if call[0] == "POST"]
    assert [call[1] for call in posts] == [
        "https://discord.com/api/v10/channels/333/messages",
        "https://discord.com/api/v10/channels/555/messages",
    ]
    assert [call[3]["content"] for call in posts] == ["first", "second"]
    assert all(call[2]["authorization"] == "Bot " + TOKEN for call in posts)
    assert all(call[3]["allowed_mentions"] == {"parse": [], "replied_user": False} for call in posts)
    assert posts[0][3]["nonce"] != posts[1][3]["nonce"]
    assert all(call[3]["enforce_nonce"] for call in posts)
    assert len(recording_resolver.calls) == 2
    assert all(request.principal.user_id == "test-user" for request in recording_resolver.calls)
    assert all(request.ref.name == "bot" for request in recording_resolver.calls)
    assert all(request.flow_id == "test-flow" for request in recording_resolver.calls)


async def test_reply_tool_retains_the_configured_target_and_uses_current_text(monkeypatch, recording_resolver):
    event = {"provider": "discord", "bot_id": BOT["id"], "guild_id": "222", "channel_id": "333", "message_id": "444"}
    response = {"id": "555", "channel_id": "333"}
    transport = BotTransport(
        [BOT, APP, {**CHANNEL, "type": 11}, response, BOT, APP, {**CHANNEL, "type": 11}, response]
    ).install(monkeypatch)
    [tool] = await tool_component(DiscordReplyComponent, event=Data(data={"payload": {"data": event}})).to_toolkit()

    await tool.ainvoke({"text": "first"})
    await tool.ainvoke({"text": "second"})

    posts = [call for call in transport.calls if call[0] == "POST"]
    assert [call[3]["content"] for call in posts] == ["first", "second"]
    assert all(call[1].endswith("/channels/333/messages") for call in posts)
    assert all(
        call[3]["message_reference"]
        == {"message_id": "444", "channel_id": "333", "guild_id": "222", "fail_if_not_exists": True}
        for call in posts
    )
    assert all(call[3]["allowed_mentions"] == {"parse": [], "replied_user": False} for call in posts)
    assert all(request.principal.user_id == "test-user" for request in recording_resolver.calls)


@pytest.mark.parametrize("mismatch", ["bot", "guild"])
async def test_reply_tool_preserves_bot_and_guild_validation(monkeypatch, recording_resolver, mismatch):
    event = {
        "provider": "discord",
        "bot_id": "999" if mismatch == "bot" else BOT["id"],
        "guild_id": "222",
        "channel_id": "333",
        "message_id": "444",
    }
    responses = [BOT, APP]
    if mismatch == "guild":
        responses.append({**CHANNEL, "guild_id": "999"})
    transport = BotTransport(responses).install(monkeypatch)
    [tool] = await tool_component(DiscordReplyComponent, event=Data(data=event)).to_toolkit()

    refused = await tool.ainvoke({"text": "wrong target"})

    assert "not authorized" in refused.lower()
    assert all(call[0] == "GET" for call in transport.calls)
    assert len(transport.calls) == (2 if mismatch == "bot" else 3)
    assert recording_resolver.calls[0].principal.user_id == "test-user"
