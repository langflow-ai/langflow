"""Bundle discovery and bot actions without the Langflow server package."""

import json
from pathlib import Path

import lfx_discord
import pytest
from conftest import APP, BOT, CHANNEL, TOKEN, BotTransport, component, lease
from lfx.extension import load_extension, validate_extension
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
)
from lfx.schema.data import Data
from lfx_discord import (
    DiscordOnMentionTriggerComponent,
    DiscordOnMessageTriggerComponent,
    DiscordReplyComponent,
    DiscordSendMessageComponent,
)
from lfx_discord._client import DiscordClient, redact, snowflake

ROOT = Path(lfx_discord.__file__).parent


def test_bundle_validates_and_loads():
    assert validate_extension(ROOT).ok
    loaded = load_extension(ROOT, distribution="lfx-discord")
    assert loaded.ok, loaded.errors
    assert len(loaded.components) == 4
    assert loaded.integrations[0].provider_id == "discord"
    manifest = loaded.integrations[0].capability_manifest
    assert manifest.auth_profiles[0].supports_refresh is False
    assert all(not cap.required_scopes for cap in manifest.capabilities)
    for cap in manifest.capabilities:
        assert hasattr(lfx_discord, cap.component_ref)
        assert cap.display_name == getattr(lfx_discord, cap.component_ref).display_name
        if ".trigger." in cap.id:
            assert cap.deployment_contexts == ("self_managed",)


@pytest.mark.parametrize("value", [None, True, 0, 123, "01", "0", "1/../messages", "-1", "1.0", str(2**64)])
def test_invalid_ids(value):
    with pytest.raises(InvalidRequestError):
        snowflake(value)


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, AuthExpiredError),
        (403, ConnectionNotAuthorizedError),
        (404, ConnectionNotAuthorizedError),
        (429, RateLimitedError),
        (500, ProviderUnavailableError),
        (302, ProviderUnavailableError),
        (400, InvalidRequestError),
    ],
)
async def test_typed_errors_do_not_copy_provider_body(monkeypatch, status, error):
    transport = BotTransport([(status, {"message": TOKEN, "retry_after": 2})]).install(monkeypatch)
    async with DiscordClient(lease()) as client:
        with pytest.raises(error) as result:
            await client.request("GET", "/users/@me")
    assert TOKEN not in str(result.value)
    assert len(transport.calls) == 1


@pytest.mark.parametrize("path", ["https://evil.test/", "/channels/1/../2", "/webhooks/1/token", "/users/@me?x=1"])
async def test_fixed_api_paths_reject_ssrf_before_io(monkeypatch, path):
    transport = BotTransport([]).install(monkeypatch)
    async with DiscordClient(lease()) as client:
        with pytest.raises(InvalidRequestError):
            await client.request("GET", path)
    assert not transport.calls


async def test_bot_application_identity_proof(monkeypatch):
    BotTransport([BOT, APP]).install(monkeypatch)
    async with DiscordClient(lease()) as client:
        assert (await client.identity())["id"] == BOT["id"]
    for bot, app in [({**BOT, "bot": False}, APP), (BOT, {**APP, "id": "999"})]:
        BotTransport([bot, app]).install(monkeypatch)
        async with DiscordClient(lease()) as client:
            with pytest.raises(ConnectionNotAuthorizedError):
                await client.identity()


async def test_response_redacts_known_token_and_secret_fields(monkeypatch):
    BotTransport([{"content": TOKEN, "token": "another-value"}]).install(monkeypatch)
    async with DiscordClient(lease()) as client:
        result = await client.request("GET", "/users/@me")
    assert result == {"content": "[redacted]"}
    fixture = {
        "interaction_token": "discard",  # pragma: allowlist secret - synthetic fixture
        "nested": {"secret": "discard"},  # pragma: allowlist secret - synthetic fixture
    }
    assert redact(fixture) == {"nested": {}}


@pytest.mark.usefixtures("resolver")
async def test_send_action_checks_guild_and_disables_mentions(monkeypatch):
    transport = BotTransport([BOT, APP, CHANNEL, {"id": "444", "channel_id": "333", "content": "hello"}]).install(
        monkeypatch
    )
    value = component(DiscordSendMessageComponent, guild_id="222", channel_id="333", text="hello")
    result = await value.build_message()
    assert result.data["message_id"] == "444"
    sent = transport.calls[-1]
    assert sent[0:2] == ("POST", "https://discord.com/api/v10/channels/333/messages")
    assert sent[2]["authorization"] == "Bot " + TOKEN
    assert sent[3]["allowed_mentions"] == {"parse": [], "replied_user": False}
    assert len(sent[3]["nonce"]) <= 25
    assert sent[3]["enforce_nonce"] is True


@pytest.mark.usefixtures("resolver")
async def test_reply_preserves_channel_thread_and_bot_identity(monkeypatch):
    event = {"provider": "discord", "bot_id": BOT["id"], "guild_id": "222", "channel_id": "333", "message_id": "444"}
    transport = BotTransport([BOT, APP, {**CHANNEL, "type": 11}, {"id": "555", "channel_id": "333"}]).install(
        monkeypatch
    )
    await component(DiscordReplyComponent, event=Data(data={"payload": {"data": event}}), text="reply").build_message()
    assert transport.calls[-1][3]["message_reference"] == {
        "message_id": "444",
        "channel_id": "333",
        "guild_id": "222",
        "fail_if_not_exists": True,
    }
    transport = BotTransport([BOT, APP]).install(monkeypatch)
    with pytest.raises(ConnectionNotAuthorizedError):
        await component(
            DiscordReplyComponent, event=Data(data={**event, "bot_id": "999"}), text="reply"
        ).build_message()
    assert len(transport.calls) == 2


@pytest.mark.usefixtures("resolver")
async def test_cross_guild_channel_is_rejected_before_send(monkeypatch):
    transport = BotTransport([BOT, APP, {**CHANNEL, "guild_id": "999"}]).install(monkeypatch)
    with pytest.raises(ConnectionNotAuthorizedError):
        await component(DiscordSendMessageComponent, guild_id="222", channel_id="333", text="hello").build_message()
    assert all(method != "POST" for method, *_ in transport.calls)


@pytest.mark.parametrize("text", ["", " ", "x" * 2001, "😀" * 1001])
async def test_invalid_text_does_not_resolve_or_send(text):
    with pytest.raises(InvalidRequestError):
        await component(DiscordSendMessageComponent, guild_id="222", channel_id="333", text=text).build_message()


@pytest.mark.parametrize("cls", [DiscordOnMentionTriggerComponent, DiscordOnMessageTriggerComponent])
def test_saved_trigger_inputs_and_conversation_message(cls):
    value = component(cls, guild_id="222", channel_ids=["333"])
    definition = value.trigger_definition()
    assert definition.kind in {"discord.message", "discord.mention"}
    assert definition.needs_connection
    value.set(event_payload=json.dumps({"payload": {"data": {"text": "hello", "session_key": "discord:123:222:333"}}}))
    message = value.build_message()
    assert message.text == "hello"
    assert message.session_id == "discord:123:222:333"


@pytest.mark.usefixtures("resolver")
async def test_repeated_send_in_one_graph_run_has_distinct_nonces(monkeypatch):
    response = {"id": "444", "channel_id": "333", "content": "hello"}
    transport = BotTransport([BOT, APP, CHANNEL, response, BOT, APP, CHANNEL, response]).install(monkeypatch)
    value = component(DiscordSendMessageComponent, guild_id="222", channel_id="333", text="hello")
    await value.build_message()
    await value.build_message()
    posts = [payload for method, _url, _headers, payload in transport.calls if method == "POST"]
    assert len(posts) == 2
    assert posts[0]["nonce"] != posts[1]["nonce"]
    assert all(payload["enforce_nonce"] for payload in posts)
