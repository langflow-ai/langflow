"""Recorded Google source push contracts at the unauthenticated boundary."""

from __future__ import annotations

import base64
import json

import pytest
from google.oauth2 import id_token
from langflow.services.triggers.ingress.verifiers import (
    IngressRejected,
    IngressRequest,
    IngressSecrets,
    state_digest,
    verify_gmail_pubsub,
    verify_google,
)


def _pubsub_request() -> IngressRequest:
    update = base64.b64encode(json.dumps({"emailAddress": "owner@example.com", "historyId": "123"}).encode()).decode()
    return IngressRequest(
        provider="google",
        body=json.dumps({"message": {"messageId": "delivery-1", "data": update}}).encode(),
        headers={"Authorization": "Bearer signed-id-token"},
        query={},
    )


async def test_gmail_pubsub_requires_the_expected_signed_service_account(monkeypatch) -> None:
    def valid_token(_token, _request, audience):
        assert audience == "https://example.com/api/v1/triggers/ingress/google/public-id"
        return {"email": "push@example.iam.gserviceaccount.com", "email_verified": True}

    monkeypatch.setattr(id_token, "verify_oauth2_token", valid_token)
    secrets = IngressSecrets(
        pubsub_service_account="push@example.iam.gserviceaccount.com",
        pubsub_audience="https://example.com/api/v1/triggers/ingress/google/public-id",
    )
    verified = await verify_gmail_pubsub(_pubsub_request(), secrets)
    assert verified.payload == {"history_id": "123"}
    assert verified.dedupe_suffix == "pubsub:delivery-1"

    monkeypatch.setattr(
        id_token,
        "verify_oauth2_token",
        lambda *_args: {"email": "other@example.iam.gserviceaccount.com", "email_verified": True},
    )
    with pytest.raises(IngressRejected, match="bad_signature"):
        await verify_gmail_pubsub(_pubsub_request(), secrets)


def test_google_sync_message_is_not_an_event() -> None:
    request = IngressRequest(
        provider="google",
        body=b"",
        headers={
            "X-Goog-Channel-Token": "channel-secret",
            "X-Goog-Channel-ID": "channel-1",
            "X-Goog-Resource-ID": "resource-1",
            "X-Goog-Resource-State": "sync",
            "X-Goog-Message-Number": "1",
        },
        query={},
    )
    secrets = IngressSecrets(
        channel_token_digest=state_digest("channel-secret"),
        channel_id="channel-1",
        resource_id="resource-1",
    )
    assert verify_google(request, secrets, tolerance_s=300).handshake == ""
    with pytest.raises(IngressRejected, match="bad_client_state"):
        verify_google(request, IngressSecrets(**{**secrets.__dict__, "resource_id": "wrong"}), tolerance_s=300)
