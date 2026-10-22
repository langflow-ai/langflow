"""GitLab signature, credentials, and signed delivery contracts."""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from functools import partial
from types import SimpleNamespace

import httpx
import pytest
from langflow.services.database.models.connection.schemas import ConnectionCreate
from langflow.services.triggers.ingress.verifiers import IngressRejected, IngressRequest
from langflow.services.triggers.providers.gitlab.config import normalize_config
from langflow.services.triggers.providers.gitlab.credentials import validate_manual_credential
from langflow.services.triggers.providers.gitlab.events import signing_key, verify
from lfx.integrations.errors import InvalidRequestError
from lfx_gitlab.client import GitLabClient

SECRET = "synthetic-gitlab-signing-secret"  # noqa: S105  # pragma: allowlist secret


def payload(kind="gitlab.issue"):
    return {
        "object_kind": kind.removeprefix("gitlab."),
        "project": {"id": 80, "path_with_namespace": "group/repo"},
        "object_attributes": {
            "id": 100,
            "iid": 4,
            "project_id": 80,
            "target_project_id": 80,
            "title": "one",
            "action": "open",
            "updated_at": "2026-10-22T00:00:00Z",
        },
        "user": {"id": 11, "username": "member"},
    }


def signed(value=None, *, secret=SECRET, message_id="stable-message", timestamp=None, body=None):
    body = json.dumps(payload() if value is None else value).encode() if body is None else body
    timestamp = str(int(time.time())) if timestamp is None else timestamp
    message = message_id.encode() + b"." + timestamp.encode() + b"." + body
    signature = "v1," + base64.b64encode(hmac.new(signing_key(secret), message, hashlib.sha256).digest()).decode()
    return IngressRequest(
        provider="gitlab",
        body=body,
        headers={"webhook-id": message_id, "webhook-timestamp": timestamp, "webhook-signature": signature},
        query={},
    )


def secrets(kind="gitlab.issue"):
    return SimpleNamespace(
        signing_secret=SECRET,
        resource_id="80",
        channel_id="9",
        target_kind=kind,
        target_config={"project_id": 80, "actions": ["open", "close"]},
    )


@pytest.mark.parametrize("kind", ["gitlab.issue", "gitlab.merge_request"])
def test_signed_events_filter_and_shape(kind):
    result = verify(signed(payload(kind)), secrets(kind), tolerance_s=300)
    assert result.payload["event"] == kind.removeprefix("gitlab.")
    assert result.payload["object_attributes"]["iid"] == 4
    assert result.dedupe_suffix.startswith("gitlab:")


def test_unsigned_headers_and_json_whitespace_cannot_bypass_dedupe():
    first = signed()
    replay = signed(body=json.dumps(payload(), indent=2).encode(), message_id="other-id")
    assert (
        verify(first, secrets(), tolerance_s=300).dedupe_suffix
        == verify(replay, secrets(), tolerance_s=300).dedupe_suffix
    )
    assert (
        verify(
            replace(first, headers={**first.headers, "X-Gitlab-Event-UUID": "untrusted"}), secrets(), tolerance_s=300
        ).dedupe_suffix
        == verify(first, secrets(), tolerance_s=300).dedupe_suffix
    )


@pytest.mark.parametrize(
    "fault",
    [
        "signature",
        "body",
        "stale",
        "future",
        "provider",
        "method",
        "project",
        "issue-project",
        "target",
        "event",
        "action",
        "item",
        "user",
        "timestamp",
        "id",
        "malformed",
    ],
)
def test_forgery_wrong_target_and_bad_shapes_reject(fault):
    value = payload("gitlab.merge_request")
    if fault == "project":
        value["project"]["id"] = 81
    if fault == "issue-project":
        value = payload()
        value["object_attributes"]["project_id"] = 81
    if fault == "target":
        value["object_attributes"]["target_project_id"] = 81
    if fault == "event":
        value["object_kind"] = "push"
    if fault == "action":
        value["object_attributes"]["action"] = "unknown"
    if fault == "item":
        value["object_attributes"]["iid"] = True
    if fault == "user":
        value["user"] = None
    request = signed(
        value,
        timestamp=str(int(time.time()) + (3600 if fault == "future" else -3600))
        if fault in {"stale", "future"}
        else None,
    )
    if fault == "body":
        request = replace(request, body=request.body + b" ")
    if fault == "provider":
        request = replace(request, provider="github")
    if fault == "method":
        request = replace(request, method="GET")
    header = {
        "signature": ("webhook-signature", "v1,wrong"),
        "timestamp": ("webhook-timestamp", "NaN"),
        "id": ("webhook-id", "bad.id"),
        "malformed": ("webhook-signature", "v1,å"),
    }.get(fault)
    if header:
        request = replace(request, headers={**request.headers, header[0]: header[1]})
    with pytest.raises(IngressRejected):
        verify(
            request, secrets("gitlab.issue" if fault == "issue-project" else "gitlab.merge_request"), tolerance_s=300
        )


@pytest.mark.parametrize(
    "body",
    [b"null", b"[]", b"not-json", b"\xff", b"x" * (1024 * 1024 + 1)],
    ids=["null", "array", "invalid-json", "invalid-utf8", "oversized"],
)
def test_malformed_signed_payloads_reject(body):
    with pytest.raises(IngressRejected):
        verify(signed(body=body), secrets(), tolerance_s=300)


@pytest.mark.parametrize("filter_name", ["self", "bot", "action", "confidential"])
def test_filtered_events_are_acknowledged_without_ledger_payload(filter_name):
    value = payload()
    if filter_name == "self":
        value["user"]["id"] = 9
    if filter_name == "bot":
        value["user"]["bot"] = True
    if filter_name == "action":
        value["object_attributes"]["action"] = "update"
    if filter_name == "confidential":
        value["object_attributes"]["confidential"] = True
    result = verify(signed(value), secrets(), tolerance_s=300)
    assert result.handshake == ""
    assert result.payload == {}


def test_payload_omits_sensitive_and_unbounded_provider_metadata():
    value = payload()
    value["project"]["http_url_to_repo"] = "https://oauth:secret@gitlab.com/repo"  # pragma: allowlist secret
    value["object_attributes"]["token"] = "plaintext-secret"  # noqa: S105  # pragma: allowlist secret
    value["user"]["email"] = "private@example.com"
    result = verify(signed(value), secrets(), tolerance_s=300)
    assert "secret" not in json.dumps(result.payload)
    assert "email" not in result.payload["user"]


@pytest.mark.parametrize(
    "raw",
    [
        {"connection": "github/work"},
        {"delivery_mode": "poll"},
        {"project_id": "../1"},
        {"actions": ["unknown"]},
        {"include_self_events": "false"},
        {"actions": []},
    ],
)
def test_invalid_configuration_rejects(raw):
    with pytest.raises((ValueError, InvalidRequestError)):
        normalize_config("gitlab.issue", {"connection": "gitlab/work", "project_id": 80, **raw})


def token_payload():
    return ConnectionCreate(
        provider_key="gitlab",
        name="work",
        display_name="GitLab",
        granted_scopes=["invented"],
        executing_identity={"identity": "service"},
        credentials={"access_token": "test-personal-token"},
    )


@pytest.mark.parametrize("fault", [None, "scope", "expired", "revoked", "bot", "identity", "no-expiry", "network"])
async def test_manual_token_uses_actual_scope_identity_origin_and_expiry(monkeypatch, fault):
    expiry = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%d")

    def handle(request):
        assert request.url.host == "gitlab.com"
        if fault == "network":
            msg = "test-personal-token"
            raise httpx.ConnectError(msg, request=request)
        if request.url.path.endswith("/user"):
            return httpx.Response(
                200,
                json={
                    "id": 9 if fault != "identity" else 10,
                    "username": "owner",
                    "bot": fault == "bot",
                    "state": "active",
                },
            )
        return httpx.Response(
            200,
            json={
                "id": 5,
                "user_id": 9,
                "scopes": ["read_api"] if fault == "scope" else ["api", "read_user"],
                "active": True,
                "revoked": fault == "revoked",
                "expires_at": None if fault == "no-expiry" else "2000-01-01" if fault == "expired" else expiry,
            },
        )

    monkeypatch.setattr(
        "langflow.services.triggers.providers.gitlab.credentials.GitLabClient",
        partial(GitLabClient, transport=httpx.MockTransport(handle)),
    )
    if fault is not None:
        from lfx.integrations.errors import IntegrationNetworkError

        with pytest.raises((InvalidRequestError, IntegrationNetworkError)) as caught:
            await validate_manual_credential(token_payload(), context="self_managed")
        assert "test-personal-token" not in str(caught.value)
    else:
        result = await validate_manual_credential(token_payload(), context="self_managed")
        assert result.granted_scopes == ["api"]
        assert result.executing_identity.identity == "user_delegated"
        assert result.executing_identity.account.id == "9"
        assert result.executing_identity.account.tenant_id == "https://gitlab.com"
        assert result.credentials.expires_at.strftime("%Y-%m-%d") == expiry
