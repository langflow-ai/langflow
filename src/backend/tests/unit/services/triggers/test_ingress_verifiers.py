"""The signature checks, exercised against provider-shaped payloads.

These are pure functions of bytes plus secrets, so every case here is a real
one: a correct Slack signature, a tampered body, a replayed timestamp, a
``clientState`` that does not match. Nothing is mocked, because there is nothing
to mock - which is exactly why verification was written as a pure function.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from langflow.services.triggers.ingress import verifiers
from langflow.services.triggers.ingress.verifiers import (
    IngressRejected,
    IngressRequest,
    IngressSecrets,
    state_digest,
    verify,
)

TOLERANCE = 300
SLACK_SECRET = "slack-signing-secret"  # noqa: S105 - test fixture  # pragma: allowlist secret
WEBHOOK_SECRET = "webhook-signing-secret"  # noqa: S105 - test fixture  # pragma: allowlist secret


def _slack_request(body: bytes, *, secret: str = SLACK_SECRET, timestamp: int | None = None) -> IngressRequest:
    timestamp = timestamp if timestamp is not None else int(time.time())
    basestring = f"v0:{timestamp}:".encode() + body
    signature = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return IngressRequest(
        provider="slack",
        body=body,
        headers={"X-Slack-Signature": signature, "X-Slack-Request-Timestamp": str(timestamp)},
        query={},
    )


def _webhook_request(body: bytes, *, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> IngressRequest:
    timestamp = timestamp if timestamp is not None else int(time.time())
    signature = verifiers.sign_webhook_payload(secret, timestamp=timestamp, body=body)
    return IngressRequest(
        provider="webhook",
        body=body,
        headers={"X-Langflow-Signature": signature, "X-Langflow-Timestamp": str(timestamp)},
        query={},
    )


# --------------------------------------------------------------------------- #
# Slack
# --------------------------------------------------------------------------- #


def test_a_correctly_signed_slack_event_verifies_and_dedupes_on_event_id() -> None:
    body = json.dumps(
        {"type": "event_callback", "event_id": "Ev123", "event": {"type": "message", "ts": "1700000000.1"}}
    ).encode()
    verified = verify(_slack_request(body), IngressSecrets(signing_secret=SLACK_SECRET), tolerance_s=TOLERANCE)
    assert verified.dedupe_suffix == "Ev123"
    assert verified.payload["event"]["type"] == "message"


def test_slack_retries_of_one_event_share_a_dedupe_key() -> None:
    """Slack retries at 0, 1, and 5 minutes; three deliveries must be one run."""
    body = json.dumps({"type": "event_callback", "event_id": "Ev123", "event": {"ts": "1"}}).encode()
    now = int(time.time())
    suffixes = {
        verify(
            _slack_request(body, timestamp=now - offset),
            IngressSecrets(signing_secret=SLACK_SECRET),
            tolerance_s=TOLERANCE,
        ).dedupe_suffix
        for offset in (0, 60, 290)
    }
    assert suffixes == {"Ev123"}


def test_a_tampered_slack_body_fails() -> None:
    request = _slack_request(b'{"type":"event_callback","event_id":"Ev1"}')
    tampered = IngressRequest(
        provider="slack",
        body=b'{"type":"event_callback","event_id":"Ev2"}',
        headers=request.headers,
        query={},
    )
    with pytest.raises(IngressRejected) as excinfo:
        verify(tampered, IngressSecrets(signing_secret=SLACK_SECRET), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_BAD_SIGNATURE


@pytest.mark.parametrize("offset", [-4000, 4000])
def test_a_stale_or_future_slack_timestamp_fails(offset: int) -> None:
    """Both directions: a future timestamp stays 'fresh' for as long as an attacker likes."""
    body = b'{"type":"event_callback","event_id":"Ev1"}'
    with pytest.raises(IngressRejected) as excinfo:
        verify(
            _slack_request(body, timestamp=int(time.time()) + offset),
            IngressSecrets(signing_secret=SLACK_SECRET),
            tolerance_s=TOLERANCE,
        )
    assert excinfo.value.reason == verifiers.REASON_STALE_TIMESTAMP


def test_a_slack_delivery_with_no_configured_secret_fails_closed() -> None:
    body = b'{"type":"event_callback","event_id":"Ev1"}'
    with pytest.raises(IngressRejected) as excinfo:
        verify(_slack_request(body), IngressSecrets(), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_MISSING_SECRET


def test_the_slack_url_verification_handshake_is_echoed_not_stored() -> None:
    body = json.dumps({"type": "url_verification", "challenge": "abc123"}).encode()
    verified = verify(_slack_request(body), IngressSecrets(signing_secret=SLACK_SECRET), tolerance_s=TOLERANCE)
    assert verified.handshake == "abc123"
    assert verified.dedupe_suffix is None


# --------------------------------------------------------------------------- #
# Microsoft Graph
# --------------------------------------------------------------------------- #


def test_the_graph_validation_handshake_echoes_the_token() -> None:
    request = IngressRequest(provider="microsoft", body=b"", headers={}, query={"validationToken": "tok-1"})
    verified = verify(request, IngressSecrets(), tolerance_s=TOLERANCE)
    assert verified.handshake == "tok-1"
    assert verified.handshake_media_type == "text/plain"


def test_a_graph_notification_verifies_against_the_stored_client_state_digest() -> None:
    secret = "client-state-value"  # noqa: S105 - test fixture  # pragma: allowlist secret
    body = json.dumps(
        {
            "value": [
                {
                    "subscriptionId": "sub-1",
                    "clientState": secret,
                    "changeType": "created",
                    "resourceData": {"id": "msg-1"},
                }
            ]
        }
    ).encode()
    request = IngressRequest(provider="microsoft", body=body, headers={}, query={})
    verified = verify(request, IngressSecrets(client_state_digest=state_digest(secret)), tolerance_s=TOLERANCE)
    assert verified.dedupe_suffix == "sub-1:msg-1:created"
    # Thin notification: ids only. Nothing is fetched back in the request.
    assert "resourceData" in verified.payload["value"][0]


def test_a_graph_notification_with_the_wrong_client_state_fails() -> None:
    body = json.dumps({"value": [{"subscriptionId": "sub-1", "clientState": "not-it"}]}).encode()
    request = IngressRequest(provider="microsoft", body=body, headers={}, query={})
    with pytest.raises(IngressRejected) as excinfo:
        verify(request, IngressSecrets(client_state_digest=state_digest("real")), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_BAD_STATE


def test_one_bad_client_state_rejects_the_whole_batch() -> None:
    """Graph batches notifications; a batch is trusted as a whole or not at all."""
    secret = "client-state-value"  # noqa: S105 - test fixture  # pragma: allowlist secret
    body = json.dumps(
        {
            "value": [
                {"subscriptionId": "sub-1", "clientState": secret},
                {"subscriptionId": "sub-2", "clientState": "forged"},
            ]
        }
    ).encode()
    request = IngressRequest(provider="microsoft", body=body, headers={}, query={})
    with pytest.raises(IngressRejected):
        verify(request, IngressSecrets(client_state_digest=state_digest(secret)), tolerance_s=TOLERANCE)


def test_a_graph_lifecycle_notification_is_reported_and_never_becomes_an_event() -> None:
    secret = "client-state-value"  # noqa: S105 - test fixture  # pragma: allowlist secret
    body = json.dumps(
        {"value": [{"subscriptionId": "sub-1", "clientState": secret, "lifecycleEvent": "reauthorizationRequired"}]}
    ).encode()
    request = IngressRequest(provider="microsoft", body=body, headers={}, query={})
    verified = verify(request, IngressSecrets(client_state_digest=state_digest(secret)), tolerance_s=TOLERANCE)
    assert verified.lifecycle == (("sub-1", "reauthorizationRequired"),)
    assert verified.dedupe_suffix is None


# --------------------------------------------------------------------------- #
# Google
# --------------------------------------------------------------------------- #


def test_a_google_push_verifies_its_channel_token() -> None:
    token = "channel-token"  # noqa: S105 - test fixture
    request = IngressRequest(
        provider="google",
        body=b"",
        headers={
            "X-Goog-Channel-Token": token,
            "X-Goog-Channel-ID": "chan-1",
            "X-Goog-Message-Number": "7",
            "X-Goog-Resource-State": "exists",
        },
        query={},
    )
    verified = verify(
        request,
        IngressSecrets(channel_token_digest=state_digest(token), channel_id="chan-1"),
        tolerance_s=TOLERANCE,
    )
    assert verified.dedupe_suffix == "chan-1:7"


def test_a_google_token_from_another_channel_is_refused() -> None:
    """A token is per channel; accepting it elsewhere is a confused deputy."""
    token = "channel-token"  # noqa: S105 - test fixture
    request = IngressRequest(
        provider="google",
        body=b"",
        headers={"X-Goog-Channel-Token": token, "X-Goog-Channel-ID": "other-channel"},
        query={},
    )
    with pytest.raises(IngressRejected) as excinfo:
        verify(
            request,
            IngressSecrets(channel_token_digest=state_digest(token), channel_id="chan-1"),
            tolerance_s=TOLERANCE,
        )
    assert excinfo.value.reason == verifiers.REASON_BAD_STATE


# --------------------------------------------------------------------------- #
# The generic signed webhook
# --------------------------------------------------------------------------- #


def test_a_signed_webhook_delivery_verifies_and_dedupes_on_its_body() -> None:
    body = json.dumps({"order": 42}).encode()
    verified = verify(_webhook_request(body), IngressSecrets(signing_secret=WEBHOOK_SECRET), tolerance_s=TOLERANCE)
    assert verified.payload == {"order": 42}
    assert verified.dedupe_suffix


def test_the_old_secret_stops_verifying_the_moment_it_is_rotated() -> None:
    body = json.dumps({"order": 42}).encode()
    request = _webhook_request(body, secret="old-secret")  # noqa: S106 - test fixture
    with pytest.raises(IngressRejected) as excinfo:
        verify(request, IngressSecrets(signing_secret="new-secret"), tolerance_s=TOLERANCE)  # noqa: S106  # pragma: allowlist secret
    assert excinfo.value.reason == verifiers.REASON_BAD_SIGNATURE


def test_an_unsigned_webhook_post_is_refused() -> None:
    request = IngressRequest(provider="webhook", body=b"{}", headers={}, query={})
    with pytest.raises(IngressRejected) as excinfo:
        verify(request, IngressSecrets(signing_secret=WEBHOOK_SECRET), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_MISSING_SIGNATURE


def test_a_body_that_is_not_a_json_object_is_refused() -> None:
    request = _webhook_request(b"[1, 2, 3]")
    with pytest.raises(IngressRejected) as excinfo:
        verify(request, IngressSecrets(signing_secret=WEBHOOK_SECRET), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_BAD_PAYLOAD


def test_headers_are_read_case_insensitively() -> None:
    """A signature check that reads None because of header casing never fails."""
    body = json.dumps({"order": 1}).encode()
    timestamp = int(time.time())
    signature = verifiers.sign_webhook_payload(WEBHOOK_SECRET, timestamp=timestamp, body=body)
    request = IngressRequest(
        provider="webhook",
        body=body,
        headers={"x-langflow-signature": signature, "x-langflow-timestamp": str(timestamp)},
        query={},
    )
    assert verify(request, IngressSecrets(signing_secret=WEBHOOK_SECRET), tolerance_s=TOLERANCE).payload == {"order": 1}


def test_an_unknown_provider_is_refused() -> None:
    request = IngressRequest(provider="dropbox", body=b"{}", headers={}, query={})
    with pytest.raises(IngressRejected) as excinfo:
        verify(request, IngressSecrets(), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_UNKNOWN_PROVIDER
