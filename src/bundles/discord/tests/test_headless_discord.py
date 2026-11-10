"""Exported Discord actions resolve environment credentials and verify the bot."""

import json
from dataclasses import replace

import pytest
from conftest import APP, BOT, CHANNEL, TOKEN, BotTransport, Resolver, lease
from lfx.components.input_output import ChatOutput
from lfx.graph import Graph
from lfx.integrations.errors import AuthExpiredError, ConnectionNotAuthorizedError, normalize_integration_error
from lfx.run.base import RunError, run_flow
from lfx.services.connection.env_resolver import EnvConnectionResolver
from lfx.services.variable.service import VariableService
from lfx_discord import DiscordSendMessageComponent
from lfx_discord._client import DiscordClient


@pytest.fixture
def exported_flow(tmp_path):
    send = DiscordSendMessageComponent(connection="discord/api003", guild_id="222", channel_id="333", text="hello")
    output = ChatOutput(should_store_message=False).set(input_value=send.build_message)
    path = tmp_path / "flow.json"
    path.write_text(Graph(start=send, end=output).dumps(), encoding="utf-8")
    assert TOKEN not in path.read_text(encoding="utf-8")
    return path


@pytest.fixture
def headless_resolver(monkeypatch):
    resolver = EnvConnectionResolver()
    variables = VariableService()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    monkeypatch.setattr("lfx.services.deps.get_variable_service", lambda: variables)


@pytest.mark.usefixtures("headless_resolver")
@pytest.mark.parametrize("json_wire", [False, True])
async def test_exported_headless_send_verifies_environment_bot(monkeypatch, exported_flow, *, json_wire):
    raw = json.dumps({"access_token": TOKEN}) if json_wire else TOKEN
    monkeypatch.setenv("LF_CONNECTION__DISCORD__API003", raw)
    transport = BotTransport([BOT, APP, CHANNEL, {"id": "444", "channel_id": "333", "content": "hello"}]).install(
        monkeypatch
    )

    result = await run_flow(script_path=exported_flow)

    assert result["success"] is True, result
    assert TOKEN not in str(result)
    assert json.loads(result["result"].removeprefix("```json\n").removesuffix("\n```")) == {
        "provider": "discord",
        "bot_id": "123456789",
        "guild_id": "222",
        "channel_id": "333",
        "message_id": "444",
        "text": "hello",
        "session_key": "discord:123456789:222:333",
    }
    assert [call[0] for call in transport.calls] == ["GET", "GET", "GET", "POST"]
    assert transport.calls[-1][2]["authorization"] == "Bot " + TOKEN


@pytest.mark.usefixtures("headless_resolver")
@pytest.mark.parametrize(
    ("responses", "error"),
    [
        ([(401, {"message": "Unauthorized"})], AuthExpiredError),
        ([{**BOT, "bot": False}, APP], ConnectionNotAuthorizedError),
        ([BOT, {**APP, "id": "999"}], ConnectionNotAuthorizedError),
    ],
)
async def test_headless_send_rejects_unverified_bot(monkeypatch, exported_flow, responses, error):
    monkeypatch.setenv("LF_CONNECTION__DISCORD__API003", TOKEN)
    transport = BotTransport(responses).install(monkeypatch)

    with pytest.raises(RunError) as caught:
        await run_flow(script_path=exported_flow)

    assert isinstance(normalize_integration_error(caught.value, provider="discord"), error)
    assert TOKEN not in str(caught.value)
    assert all(method != "POST" for method, *_ in transport.calls)


@pytest.mark.parametrize(
    ("owner_kind", "identity", "provider"),
    [
        ("user", None, "discord"),
        ("env", "user_delegated", "discord"),
        ("env", "service", "discord"),
        ("env", None, "other"),
    ],
)
async def test_headless_support_preserves_credential_identity_checks(monkeypatch, owner_kind, identity, provider):
    credential = replace(await lease().get_credential(), owner_kind=owner_kind, identity=identity, provider=provider)

    async def resolve(_self, _request):
        return credential

    monkeypatch.setattr(Resolver, "resolve", resolve)
    transport = BotTransport([]).install(monkeypatch)
    async with DiscordClient(lease()) as client:
        with pytest.raises(ConnectionNotAuthorizedError):
            await client.identity()
    assert not transport.calls
