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


def test_the_graph_validation_handshake_is_recognised_without_a_trigger() -> None:
    """The route answers it before resolving a trigger, so it needs no secrets."""
    assert verifiers.validation_token("microsoft", {"validationToken": "tok-1"}) == "tok-1"


def test_only_microsoft_requests_are_handshakes() -> None:
    """A Slack or webhook request with the same query param is an ordinary delivery."""
    assert verifiers.validation_token("slack", {"validationToken": "tok-1"}) is None
    assert verifiers.validation_token("webhook", {"validationToken": "tok-1"}) is None
    assert verifiers.validation_token("microsoft", {}) is None


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("x" * 4096, id="too-long"),
        pytest.param("tok<script>", id="disallowed-characters"),
        pytest.param("", id="empty"),
    ],
)
def test_a_malformed_validation_token_is_not_echoed(token: str) -> None:
    """The echo goes to an anonymous caller: unbounded reflection is a primitive."""
    assert verifiers.validation_token("microsoft", {"validationToken": token}) is None


def test_a_handshake_that_reaches_the_verifier_is_refused_as_a_bad_payload() -> None:
    """There is one handshake answer, in the route. This path is the fallback."""
    request = IngressRequest(provider="microsoft", body=b"", headers={}, query={"validationToken": "tok-1"})
    with pytest.raises(IngressRejected) as excinfo:
        verify(request, IngressSecrets(), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_BAD_PAYLOAD


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


# --------------------------------------------------------------------------- #
# The ledger key
# --------------------------------------------------------------------------- #


def test_the_dedupe_key_uses_the_providers_own_event_identity() -> None:
    from langflow.services.triggers.ingress.intake import dedupe_key

    assert dedupe_key(provider="slack", suffix="Ev123", fallback="unused") == "ingress:slack:Ev123"
    assert dedupe_key(provider="webhook", suffix=None, fallback="digest") == "ingress:webhook:digest"


def test_a_long_key_is_digested_rather_than_truncated() -> None:
    """Truncation could cut exactly where two Graph resource paths diverge.

    Two distinct events collapsing into one ledger row is a silently lost run -
    the dedupe design failing in the direction it cannot detect.
    """
    from langflow.services.database.models.trigger.schemas import DEDUPE_KEY_MAX_LENGTH
    from langflow.services.triggers.ingress.intake import dedupe_key

    shared = "sub-1:" + ("drive/root:/very/deep/path/" * 20)
    first = dedupe_key(provider="microsoft", suffix=shared + "a", fallback="x")
    second = dedupe_key(provider="microsoft", suffix=shared + "b", fallback="x")

    assert len(first) <= DEDUPE_KEY_MAX_LENGTH
    assert len(second) <= DEDUPE_KEY_MAX_LENGTH
    assert first != second, "two distinct events must not share a ledger key"
    assert first.startswith("ingress:microsoft:")


# --------------------------------------------------------------------------- #
# Malformed input is a refusal, never a crash
# --------------------------------------------------------------------------- #
#
# A verifier only runs for a public id that resolved to an accepting trigger, so
# any exception other than IngressRejected becomes a 500 that an unknown id can
# never produce - the existence oracle the uniform 404 exists to close.

_SIGNED_HEADERS = {
    "slack": ("X-Slack-Signature", "X-Slack-Request-Timestamp"),
    "webhook": ("X-Langflow-Signature", "X-Langflow-Timestamp"),
}


@pytest.mark.parametrize("provider", ["slack", "webhook"])
@pytest.mark.parametrize("timestamp", ["inf", "-inf", "1e400", "nan", "Infinity"])
def test_a_non_finite_timestamp_is_refused_as_stale(provider: str, timestamp: str) -> None:
    signature_header, timestamp_header = _SIGNED_HEADERS[provider]
    request = IngressRequest(
        provider=provider,
        body=b"{}",
        headers={signature_header: "v0=00", timestamp_header: timestamp},
        query={},
    )
    with pytest.raises(IngressRejected) as excinfo:
        verify(request, IngressSecrets(signing_secret=SLACK_SECRET), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_STALE_TIMESTAMP


@pytest.mark.parametrize("provider", ["slack", "webhook"])
def test_a_non_ascii_signature_is_refused_not_raised(provider: str) -> None:
    r"""Starlette decodes header bytes as latin-1, so ``b"\xff"`` arrives as ``"ÿ"``.

    ``hmac.compare_digest`` raises TypeError for a non-ASCII str rather than
    answering False.
    """
    signature_header, timestamp_header = _SIGNED_HEADERS[provider]
    request = IngressRequest(
        provider=provider,
        body=b"{}",
        headers={signature_header: "v1=\xff", timestamp_header: str(int(time.time()))},
        query={},
    )
    with pytest.raises(IngressRejected) as excinfo:
        verify(request, IngressSecrets(signing_secret=SLACK_SECRET), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_BAD_SIGNATURE


def test_a_graph_client_state_that_cannot_be_encoded_is_refused_not_raised() -> None:
    """JSON can carry a lone surrogate, which a strict UTF-8 encode refuses."""
    body = b'{"value": [{"subscriptionId": "sub-1", "clientState": "\\ud800"}]}'
    request = IngressRequest(provider="microsoft", body=body, headers={}, query={})
    with pytest.raises(IngressRejected) as excinfo:
        verify(request, IngressSecrets(client_state_digest=state_digest("real")), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_BAD_STATE


def test_a_non_ascii_google_channel_id_is_refused_not_raised() -> None:
    token = "channel-token"  # noqa: S105 - test fixture
    request = IngressRequest(
        provider="google",
        body=b"",
        headers={"X-Goog-Channel-Token": token, "X-Goog-Channel-ID": "chan-\xff"},
        query={},
    )
    with pytest.raises(IngressRejected) as excinfo:
        verify(
            request,
            IngressSecrets(channel_token_digest=state_digest(token), channel_id="chan-1"),
            tolerance_s=TOLERANCE,
        )
    assert excinfo.value.reason == verifiers.REASON_BAD_STATE


def test_an_unexpected_verifier_error_is_still_a_refusal(monkeypatch) -> None:
    """The uniform answer must not depend on every parsing branch being exception-tight."""

    def _broken(_request, _secrets, *, tolerance_s):  # noqa: ARG001
        missing = "a future parsing bug"
        raise KeyError(missing)

    monkeypatch.setitem(verifiers._VERIFIERS, "webhook", _broken)
    request = IngressRequest(provider="webhook", body=b"{}", headers={}, query={})
    with pytest.raises(IngressRejected) as excinfo:
        verify(request, IngressSecrets(signing_secret=WEBHOOK_SECRET), tolerance_s=TOLERANCE)
    assert excinfo.value.reason == verifiers.REASON_VERIFIER_ERROR


# --------------------------------------------------------------------------- #
# The Graph dedupe identity
# --------------------------------------------------------------------------- #


def _graph_notification(*, resource_id: str, etag: str | None = None, change: str = "updated") -> dict:
    resource_data: dict = {"id": resource_id}
    if etag is not None:
        resource_data["@odata.etag"] = etag
    return {
        "subscriptionId": "sub-1",
        "clientState": "client-state-value",
        "changeType": change,
        "resource": f"Users/u/Messages/{resource_id}",
        "resourceData": resource_data,
    }


def _graph_suffix(*notifications: dict) -> str | None:
    request = IngressRequest(
        provider="microsoft", body=json.dumps({"value": list(notifications)}).encode(), headers={}, query={}
    )
    secrets = IngressSecrets(client_state_digest=state_digest("client-state-value"))
    return verify(request, secrets, tolerance_s=TOLERANCE).dedupe_suffix


def test_two_edits_to_one_graph_resource_are_two_events() -> None:
    """Graph distinguishes successive ``updated`` notifications by the resource etag.

    Without it, every edit after the first to the same message or calendar
    event would collapse into the first one's ledger row for the whole
    retention window - a silently lost run each time.
    """
    first = _graph_suffix(_graph_notification(resource_id="msg-1", etag='W/"v1"'))
    second = _graph_suffix(_graph_notification(resource_id="msg-1", etag='W/"v2"'))
    redelivered = _graph_suffix(_graph_notification(resource_id="msg-1", etag='W/"v1"'))

    assert first != second
    assert first == redelivered


def test_a_graph_batch_is_keyed_on_every_notification_in_it() -> None:
    """Keying on the first entry alone would drop the rest of a batch as a duplicate."""
    alone = _graph_suffix(_graph_notification(resource_id="msg-1", change="created"))
    batched = _graph_suffix(
        _graph_notification(resource_id="msg-1", change="created"),
        _graph_notification(resource_id="msg-2", change="created"),
    )

    assert alone != batched
