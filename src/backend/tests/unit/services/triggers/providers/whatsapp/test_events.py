"""Raw signature, pure challenge, filtering and canonical retry identity."""

import copy
import hashlib
import hmac
import json

import pytest
from langflow.services.triggers.ingress.verifiers import IngressRejected, IngressRequest, IngressSecrets, state_digest
from langflow.services.triggers.providers.whatsapp.config import normalize_config
from langflow.services.triggers.providers.whatsapp.events import MAX_ITEMS, verify, verify_get
from langflow.services.triggers.source_items import validate_source_items

SECRET = "a" * 32
CONFIG = {"connection": "whatsapp/business", "receive_messages": True, "receive_statuses": True, "allowed_senders": []}
MESSAGE = {
    "id": "wamid.inbound",
    "from": "15551234567",
    "timestamp": "1792700000",
    "type": "text",
    "text": {"body": "Hello"},
}
STATUS = {"id": "wamid.outbound", "recipient_id": "15551234567", "timestamp": "1792700001", "status": "delivered"}


def payload(messages=None, statuses=None):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "222",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "333"},
                            "messages": [MESSAGE] if messages is None else messages,
                            "statuses": [] if statuses is None else statuses,
                        },
                    }
                ],
            }
        ],
    }


def secrets(config=None):
    return IngressSecrets(
        signing_secret=SECRET,
        resource_id="222",
        channel_id="333",
        target_kind="whatsapp.event",
        target_config=config or CONFIG,
        verification_token_digest=state_digest("synthetic-challenge-token"),
    )


def request(body=None, **kwargs):
    encoded = json.dumps(payload() if body is None else body).encode()
    return IngressRequest(
        provider="whatsapp",
        body=encoded,
        headers={
            "X-Hub-Signature-256": "sha256=" + hmac.new(SECRET.encode(), encoded, hashlib.sha256).hexdigest(),
            **kwargs,
        },
        query={},
    )


def test_signed_batch_yields_messages_and_statuses_with_stable_session():
    result = verify(request(payload(statuses=[STATUS])), secrets(), tolerance_s=0)
    validate_source_items(result.source_items, provider="whatsapp")
    assert len(result.source_items) == 2
    assert result.response_status == 200
    assert result.source_items[0]["data"]["text"] == "Hello"
    assert (
        result.source_items[0]["session_key"] == result.source_items[1]["session_key"] == "whatsapp:222:333:15551234567"
    )
    assert result.source_items[1]["version"] == "delivered:1792700001"
    assert (
        verify(request(payload(statuses=[STATUS]), **{"x-request-id": "forged"}), secrets(), tolerance_s=0).source_items
        == result.source_items
    )


@pytest.mark.parametrize("signature", [None, "sha256=bad", "sha256=" + "0" * 64, "é"])
def test_forged_or_missing_signature_fails_closed(signature):
    value = request()
    changed = IngressRequest(
        provider="whatsapp", body=value.body, headers={"x-hub-signature-256": signature} if signature else {}, query={}
    )
    with pytest.raises(IngressRejected):
        verify(changed, secrets(), tolerance_s=0)


def test_retry_reordered_batch_has_same_per_item_identity():
    first = verify(request(payload(statuses=[STATUS])), secrets(), tolerance_s=0)
    second = verify(request(payload(messages=[], statuses=[STATUS])), secrets(), tolerance_s=0)
    assert first.source_items[1] == second.source_items[0]


@pytest.mark.parametrize("field", ["id", "timestamp"])
def test_malformed_later_item_rejects_entire_batch(field):
    bad = {**MESSAGE, "id": "wamid.second", field: []}
    with pytest.raises(IngressRejected):
        verify(request(payload(messages=[MESSAGE, bad])), secrets(), tolerance_s=0)


def test_oversized_batch_rejects_without_partial_delivery():
    with pytest.raises(IngressRejected):
        verify(request(payload(messages=[MESSAGE] * (MAX_ITEMS + 1))), secrets(), tolerance_s=0)


@pytest.mark.parametrize("scope", ["waba", "phone", "sender", "unsupported-type"])
def test_unrelated_or_unsupported_events_acknowledge_without_flow_events(scope):
    body = copy.deepcopy(payload())
    config = dict(CONFIG)
    if scope == "waba":
        body["entry"][0]["id"] = "999"
    elif scope == "phone":
        body["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "999"
    elif scope == "sender":
        config["allowed_senders"] = ["15550000000"]
    else:
        body["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
    result = verify(request(body), secrets(config), tolerance_s=0)
    assert result.source_items == ()
    assert result.response_status == 200


def test_secrets_and_unknown_raw_fields_never_enter_canonical_payload():
    token = "EAA" + "x" * 30
    message = {**MESSAGE, "text": {"body": "Do not expose " + SECRET + " or " + token}, "private_token": token}
    result = verify(request(payload(messages=[message])), secrets(), tolerance_s=0)
    encoded = json.dumps(result.source_items)
    assert SECRET not in encoded
    assert token not in encoded
    assert "private_token" not in encoded


def test_pure_challenge_has_no_event_or_lifecycle_payload():
    value = IngressRequest(
        provider="whatsapp",
        method="GET",
        body=b"",
        headers={},
        query={"hub.mode": "subscribe", "hub.verify_token": "synthetic-challenge-token", "hub.challenge": "12345"},
    )
    result = verify_get(value, secrets(), tolerance_s=0)
    assert result.handshake == "12345"
    assert not result.payload
    assert result.source_items is None
    assert not result.lifecycle


@pytest.mark.parametrize(
    "change",
    [{"hub.mode": "other"}, {"hub.verify_token": "wrong"}, {"hub.challenge": "<script>"}, {"hub.challenge": "1" * 129}],
)
def test_challenge_requires_proof_and_bounded_numeric_echo(change):
    query = {
        "hub.mode": "subscribe",
        "hub.verify_token": "synthetic-challenge-token",
        "hub.challenge": "12345",
        **change,
    }
    with pytest.raises(IngressRejected):
        verify_get(
            IngressRequest(provider="whatsapp", method="GET", body=b"", headers={}, query=query),
            secrets(),
            tolerance_s=0,
        )


@pytest.mark.parametrize(
    "config",
    [
        {"receive_messages": False, "receive_statuses": False},
        {"delivery_mode": "poll"},
        {"allowed_senders": ["https://evil.example"]},
        {"api_origin": "https://evil.example"},
        {"connection": "slack/work"},
    ],
)
def test_config_rejects_unsupported_transport_targets_and_cross_provider(config):
    with pytest.raises(ValueError, match=r".+"):
        normalize_config("whatsapp.event", {**CONFIG, **config})
