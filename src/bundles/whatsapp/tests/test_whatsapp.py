"""Installed declarations and observable Cloud API request contracts."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import lfx_whatsapp
import pytest
from conftest import DEBUG, PHONES, TOKEN, GraphTransport, component, lease
from lfx.extension import load_extension, validate_extension
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
)
from lfx.integrations.models import ResolvedCredential
from lfx.schema.data import Data
from lfx_whatsapp import (
    WhatsAppOnEventTriggerComponent,
    WhatsAppReplyComponent,
    WhatsAppSendTemplateComponent,
    WhatsAppSendTextComponent,
)
from lfx_whatsapp._client import WhatsAppClient, settings
from lfx_whatsapp._components import recipient, text_body
from pydantic import SecretStr


def test_installed_bundle_loads_all_four_components():
    root = Path(lfx_whatsapp.__file__).parent
    result = validate_extension(root)
    assert result.ok, result.errors
    loaded = load_extension(root, distribution="lfx-whatsapp")
    assert loaded.ok, loaded.errors
    assert len(loaded.components) == 4
    assert loaded.integrations[0].provider_id == "whatsapp"
    assert len(loaded.integrations[0].capability_manifest.capabilities) == 4


@pytest.mark.parametrize("value", [None, 123, "0123456789", "+15551234567", "1/../../x", "x" * 20])
def test_recipient_rejects_ambiguous_or_url_targets(value):
    with pytest.raises(ValueError, match=r".+"):
        recipient(value)


@pytest.mark.parametrize("value", [None, "", " ", "x" * 4097])
def test_text_is_bounded(value):
    with pytest.raises(ValueError, match=r".+"):
        text_body(value)


def test_settings_refuse_untrusted_version_and_hide_app_secret(monkeypatch):
    assert "a" * 32 not in repr(settings())
    monkeypatch.setenv("LANGFLOW_WHATSAPP_GRAPH_VERSION", "https://evil.example")
    with pytest.raises(InvalidRequestError):
        settings()


@pytest.mark.usefixtures("resolver")
async def test_send_text_proves_app_and_phone_then_sends_once(monkeypatch):
    transport = GraphTransport([DEBUG, PHONES, {"messages": [{"id": "wamid.sent"}]}]).install(monkeypatch)
    result = await component(WhatsAppSendTextComponent, to="15551234567", text="Hello").build_message()
    assert result.data["accepted"] is True
    assert result.data["message_id"] == "wamid.sent"
    assert [r.url.path for r in transport.requests] == [
        "/v25.0/debug_token",
        "/v25.0/222/phone_numbers",
        "/v25.0/333/messages",
    ]
    assert transport.requests[0].url.params["input_token"] == TOKEN
    assert transport.requests[0].headers["authorization"] == "Bearer 111|" + "a" * 32
    assert json.loads(transport.requests[-1].content) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "15551234567",
        "type": "text",
        "text": {"body": "Hello", "preview_url": False},
    }
    assert TOKEN not in repr(result)


@pytest.mark.usefixtures("resolver")
async def test_reply_preserves_sender_and_message_context(monkeypatch):
    event = {
        "provider": "whatsapp",
        "event": "message",
        "phone_id": "333",
        "waba_id": "222",
        "message_id": "wamid.received",
        "sender": "15551234567",
    }
    transport = GraphTransport([DEBUG, PHONES, {"messages": [{"id": "wamid.reply"}]}]).install(monkeypatch)
    await component(WhatsAppReplyComponent, event=Data(data={"payload": {"data": event}}), text="Reply").build_message()
    assert json.loads(transport.requests[-1].content)["context"] == {"message_id": "wamid.received"}
    assert json.loads(transport.requests[-1].content)["to"] == event["sender"]
    transport = GraphTransport([]).install(monkeypatch)
    with pytest.raises(InvalidRequestError, match="same WhatsApp"):
        await component(
            WhatsAppReplyComponent, event=Data(data={**event, "phone_id": "444"}), text="No"
        ).build_message()
    assert not transport.requests


@pytest.mark.usefixtures("resolver")
async def test_template_uses_approved_name_and_positional_text_body(monkeypatch):
    transport = GraphTransport([DEBUG, PHONES, {"messages": [{"id": "wamid.template"}]}]).install(monkeypatch)
    await component(
        WhatsAppSendTemplateComponent,
        to="15551234567",
        template_name="order_update",
        language="en_US",
        body_parameters=["123"],
    ).build_message()
    assert json.loads(transport.requests[-1].content)["template"] == {
        "name": "order_update",
        "language": {"code": "en_US"},
        "components": [{"type": "body", "parameters": [{"type": "text", "text": "123"}]}],
    }


@pytest.mark.parametrize(
    "change",
    [
        {"app_id": "999"},
        {"type": "USER"},
        {"is_valid": False},
        {"scopes": ["whatsapp_business_messaging"]},
        {"expires_at": -1},
    ],
)
async def test_identity_and_permissions_are_verified_from_meta(monkeypatch, change):
    debug = copy.deepcopy(DEBUG)
    debug["data"].update(change)
    GraphTransport([debug]).install(monkeypatch)
    async with WhatsAppClient(lease()) as client:
        with pytest.raises(ConnectionNotAuthorizedError):
            await client.verify_account()


async def test_expiry_is_actual_provider_expiry_and_expired_tokens_fail(monkeypatch):
    import time

    debug = copy.deepcopy(DEBUG)
    debug["data"].update(expires_at=int(time.time()) + 3600, data_access_expires_at=int(time.time()) + 1800)
    GraphTransport([debug, PHONES]).install(monkeypatch)
    async with WhatsAppClient(lease()) as client:
        scopes, expiry = await client.verify_account()
    assert int(expiry.timestamp()) == debug["data"]["data_access_expires_at"]
    assert len(scopes) == 2
    debug["data"]["expires_at"] = 1
    GraphTransport([debug]).install(monkeypatch)
    async with WhatsAppClient(lease()) as client:
        with pytest.raises(AuthExpiredError):
            await client.verify_account()


async def test_phone_membership_follows_only_opaque_cursor(monkeypatch):
    first = {"data": [], "paging": {"next": "https://evil.example/stolen", "cursors": {"after": "opaque"}}}
    transport = GraphTransport([DEBUG, first, PHONES]).install(monkeypatch)
    async with WhatsAppClient(lease()) as client:
        await client.verify_account()
    assert transport.requests[-1].url.host == "graph.facebook.com"
    assert transport.requests[-1].url.params["after"] == "opaque"


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (401, {}, AuthExpiredError),
        (429, {}, RateLimitedError),
        (403, {}, ConnectionNotAuthorizedError),
        (500, {}, ProviderUnavailableError),
        (400, {"error": {"code": 131047, "message": TOKEN}}, InvalidRequestError),
    ],
)
async def test_provider_failures_are_sanitized_and_not_retried(monkeypatch, status, body, error):
    transport = GraphTransport([(status, body)]).install(monkeypatch)
    async with WhatsAppClient(lease()) as client:
        with pytest.raises(error) as caught:
            await client.request("POST", "333/messages", body={})
    assert TOKEN not in str(caught.value)
    assert len(transport.requests) == 1


async def test_uncertain_send_network_failure_is_not_retried(monkeypatch):
    transport = GraphTransport([httpx.ReadTimeout("secret URL " + TOKEN)]).install(monkeypatch)
    async with WhatsAppClient(lease()) as client:
        with pytest.raises(ProviderUnavailableError) as caught:
            await client.request("POST", "333/messages", body={})
    assert TOKEN not in str(caught.value)
    assert len(transport.requests) == 1


def test_trigger_declaration_preserves_conversation_session():
    value = component(WhatsAppOnEventTriggerComponent)
    assert value.trigger_definition().kind == "whatsapp.event"
    value.set(
        event_payload=json.dumps(
            {"payload": {"data": {"text": "Hello", "session_key": "whatsapp:222:333:15551234567"}}}
        )
    )
    message = value.build_message()
    assert message.text == "Hello"
    assert message.session_id == "whatsapp:222:333:15551234567"


@pytest.mark.parametrize(("provider", "identity"), [("whatsapp", None), ("whatsapp", "bot"), ("github", "service")])
async def test_normal_client_keeps_strict_provider_and_service_identity_checks(monkeypatch, provider, identity):
    async def credential():
        return ResolvedCredential(access_token=SecretStr(TOKEN), provider=provider, identity=identity)

    transport = GraphTransport([]).install(monkeypatch)
    async with WhatsAppClient(SimpleNamespace(get_credential=credential)) as client:
        with pytest.raises(ConnectionNotAuthorizedError):
            await client.request("GET", "debug_token")
    assert transport.requests == []
