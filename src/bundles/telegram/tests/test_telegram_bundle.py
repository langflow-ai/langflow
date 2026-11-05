"""Bundle installation metadata, declarations, and observable message actions."""

import json
from pathlib import Path

import lfx_telegram
import pytest
from conftest import BOT, BotTransport, component
from lfx.extension import load_extension, validate_extension
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.integrations.errors import ConnectionNotAuthorizedError, InvalidRequestError
from lfx.schema.data import Data
from lfx_telegram import (
    TelegramNotifyComponent,
    TelegramOnCommandTriggerComponent,
    TelegramOnMessageTriggerComponent,
    TelegramReplyComponent,
    TelegramSendMessageComponent,
)
from lfx_telegram._validation import message_payload, numeric_id

ROOT = Path(lfx_telegram.__file__).parent


def test_bundle_validates_and_loads():
    result = validate_extension(ROOT)
    assert result.ok, result.errors
    loaded = load_extension(ROOT, distribution="lfx-telegram")
    assert loaded.ok, loaded.errors
    assert loaded.integrations[0].provider_id == "telegram"
    assert len(loaded.integrations[0].capability_manifest.capabilities) == 7


def test_manifest_uses_manual_bot_identity_without_fake_oauth_scopes():
    manifest = IntegrationCapabilityManifest.model_validate_json(
        (ROOT / "components/telegram/capabilities.v1.json").read_text()
    )
    (profile,) = manifest.auth_profiles
    assert profile.identity == "bot"
    assert profile.kind == "api_key"
    assert profile.supports_refresh is False
    for capability in manifest.capabilities:
        assert capability.required_scopes == ()
        assert hasattr(lfx_telegram, capability.component_ref)
        if capability.id.endswith(".poll"):
            assert set(capability.deployment_contexts) == {"self_managed", "desktop"}
        if capability.id.endswith(".webhook"):
            assert set(capability.deployment_contexts) == {"hosted", "self_managed"}


@pytest.mark.parametrize("value", [None, True, 1.2, 0, "0", "01", "+1", "1.0", "@channel", "1/../sendMessage", 2**52])
def test_invalid_numeric_targets_are_rejected(value):
    with pytest.raises(InvalidRequestError):
        numeric_id(value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": ""},
        {"text": "x" * 4097},
        {"text": "😀" * 2049},
        {"thread_id": "-1"},
        {"reply_id": True},
        {"silent": "false"},
    ],
)
def test_message_configuration_rejected_before_io(kwargs):
    with pytest.raises(InvalidRequestError):
        message_payload(**{"chat_id": "-1001234", "text": "hi", **kwargs})


@pytest.mark.parametrize(
    ("cls", "kind"),
    [(TelegramOnMessageTriggerComponent, "telegram.message"), (TelegramOnCommandTriggerComponent, "telegram.command")],
)
def test_trigger_is_a_declaration_and_unwraps_either_transport(cls, kind):
    value = component(cls, allowed_chats=["123"])
    assert value.trigger_definition().kind == kind
    assert value.trigger_definition().needs_connection is True
    for envelope in [
        {"data": {"text": "hi", "session_key": "telegram:bot:123"}},
        {"delivery": {"text": "hi", "session_key": "telegram:bot:123"}},
    ]:
        value.set(event_payload=json.dumps({"payload": envelope}))
        message = value.build_message()
        assert message.text == "hi"
        assert message.session_id == "telegram:bot:123"


@pytest.mark.parametrize(("cls", "silent"), [(TelegramSendMessageComponent, False), (TelegramNotifyComponent, True)])
@pytest.mark.usefixtures("resolver")
async def test_send_uses_verified_bot_and_one_send(monkeypatch, cls, silent):
    transport = BotTransport([BOT, {"message_id": 7, "text": "hello"}]).install(monkeypatch)
    value = component(cls, chat_id="-1001234", text="hello", thread_id="4")
    result = await value.build_message()
    assert result.data["message_id"] == 7
    assert transport.calls == [
        ("getMe", {}),
        ("sendMessage", {"chat_id": -1001234, "text": "hello", "message_thread_id": 4, "disable_notification": silent}),
    ]


@pytest.mark.usefixtures("resolver")
async def test_reply_preserves_target_and_rejects_another_bot(monkeypatch):
    event = {"provider": "telegram", "bot_id": "123456789", "chat_id": "-1001234", "thread_id": "4", "message_id": 7}
    transport = BotTransport([BOT, {"message_id": 8, "text": "reply"}]).install(monkeypatch)
    value = component(TelegramReplyComponent, event=Data(data={"payload": {"data": event}}), text="reply")
    await value.build_message()
    assert transport.calls[-1] == (
        "sendMessage",
        {
            "chat_id": -1001234,
            "text": "reply",
            "message_thread_id": 4,
            "disable_notification": False,
            "reply_parameters": {"message_id": 7, "allow_sending_without_reply": False},
        },
    )
    other = {**event, "bot_id": "987654321"}
    transport = BotTransport([BOT]).install(monkeypatch)
    value = component(TelegramReplyComponent, event=Data(data=other), text="wrong")
    with pytest.raises(ConnectionNotAuthorizedError):
        await value.build_message()
    assert transport.calls == [("getMe", {})]
