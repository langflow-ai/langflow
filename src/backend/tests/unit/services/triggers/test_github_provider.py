"""GitHub signatures, event boundaries, installation setup, and webhook cleanup."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from functools import partial
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langflow.services.database.models.connection.schemas import (
    ConnectionCreate,
    ConnectionCredentialWrite,
    ExecutingIdentityDescriptor,
)
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.triggers.ingress.verifiers import IngressRejected, IngressRequest
from langflow.services.triggers.providers.github.config import normalize_config
from langflow.services.triggers.providers.github.events import verify
from lfx.integrations.errors import ConnectionNotAuthorizedError, InvalidRequestError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease, ResolvedCredential
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_github.client import GitHubClient
from pydantic import SecretStr

SECRET = "deterministic-test-webhook-secret"  # noqa: S105  # pragma: allowlist secret


def payload(kind="github.issue", action="opened"):
    item_name = "issue" if kind == "github.issue" else "pull_request"
    return {
        "repository": {"id": 80, "full_name": "org/repo"},
        "action": action,
        item_name: {"id": 100, "number": 4, "title": "one"},
        "sender": {"id": 9},
    }


def signed(value=None, *, kind="github.issue", event=None, body=None):
    content = json.dumps(payload(kind) if value is None else value).encode() if body is None else body
    signature = "sha256=" + hmac.new(SECRET.encode(), content, hashlib.sha256).hexdigest()
    return IngressRequest(
        provider="github",
        body=content,
        headers={
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": str(uuid4()),
            "X-GitHub-Event": event or ("issues" if kind == "github.issue" else "pull_request"),
        },
        query={},
    )


def secrets(kind="github.issue", actions=None):
    return SimpleNamespace(
        signing_secret=SECRET,
        resource_id="80",
        target_kind=kind,
        target_config={"repository": "org/repo", "actions": actions or ["opened", "closed"]},
    )


@pytest.mark.parametrize("kind", ["github.issue", "github.pull_request"])
def test_exact_issue_and_pull_request_payloads(kind):
    result = verify(signed(kind=kind), secrets(kind), tolerance_s=300)
    assert result.payload["action"] == "opened"
    assert result.payload["provider"] == "github"
    assert result.payload["repository"]["id"] == 80
    assert result.dedupe_suffix.startswith("github:")


def test_unsigned_delivery_id_change_cannot_bypass_deduplication():
    first = signed()
    replay = replace(first, headers={**first.headers, "X-GitHub-Delivery": str(uuid4())})
    assert (
        verify(first, secrets(), tolerance_s=300).dedupe_suffix
        == verify(replay, secrets(), tolerance_s=300).dedupe_suffix
    )


@pytest.mark.parametrize(
    "change",
    [
        "signature",
        "body",
        "missing",
        "malformed",
        "provider",
        "delivery",
        "repository",
        "repository_id",
        "event",
        "action",
        "number",
        "item",
        "issue_is_pr",
    ],
)
def test_forgery_mismatch_and_unknown_events_reject(change):
    value = payload()
    headers = {}
    if change == "repository":
        value["repository"]["full_name"] = "other/repo"
    if change == "repository_id":
        value["repository"]["id"] = 81
    if change == "action":
        value["action"] = "unknown_action"
    if change == "number":
        value["issue"]["number"] = True
    if change == "item":
        value["issue"] = []
    if change == "issue_is_pr":
        value["issue"]["pull_request"] = {}
    request = signed(value, event="push" if change == "event" else None)
    if change == "signature":
        headers["X-Hub-Signature-256"] = "sha256=" + "0" * 64
    if change == "missing":
        headers["X-Hub-Signature-256"] = ""
    if change == "malformed":
        headers["X-Hub-Signature-256"] = "sha256=å"
    if change == "delivery":
        headers["X-GitHub-Delivery"] = "not-a-delivery-id"
    request = replace(request, headers={**request.headers, **headers})
    if change == "body":
        request = replace(request, body=request.body + b" ")
    if change == "provider":
        request = replace(request, provider="gitlab")
    with pytest.raises(IngressRejected):
        verify(request, secrets(), tolerance_s=300)


@pytest.mark.parametrize(
    "body",
    [b"null", b"[]", b"not-json", b"\xff", b"x" * (1024 * 1024 + 1)],
    ids=["null", "list", "garbage", "bad-utf8", "oversize"],
)
def test_malformed_or_oversized_signed_payloads_reject(body):
    with pytest.raises(IngressRejected):
        verify(signed(body=body), secrets(), tolerance_s=300)


@pytest.mark.parametrize("mode", ["ping", "filtered"])
def test_signed_ping_and_filtered_actions_do_not_fire(mode):
    request = signed(event="ping" if mode == "ping" else None)
    result = verify(request, secrets(actions=["closed"]), tolerance_s=300)
    assert result.handshake == ""
    assert result.payload == {}


def test_repository_name_is_case_insensitive_but_id_is_bound():
    value = payload()
    value["repository"]["full_name"] = "ORG/REPO"
    assert verify(signed(value), secrets(), tolerance_s=300).payload


@pytest.mark.parametrize(
    "raw",
    [
        {"repository": "https://evil.example"},
        {"connection": "gitlab/work"},
        {"delivery_mode": "poll"},
        {"actions": []},
        {"actions": ["push"]},
        {"actions": "opened"},
    ],
)
def test_invalid_trigger_config_fails_before_remote_calls(raw):
    config = {"connection": "github/work", "repository": "org/repo", "actions": ["opened"]}
    config.update(raw)
    with pytest.raises((ValueError, InvalidRequestError)):
        normalize_config("github.issue", config)


def test_trigger_config_is_normalized_and_has_no_secret_fields():
    result = normalize_config(
        "github.issue",
        {
            "connection": "github/work",
            "repository": "Org/Repo",
            "actions": ["closed", "opened", "closed"],
            "access_token": "not-persisted",
        },
    )
    assert result == {
        "connection": "github/work",
        "repository": "org/repo",
        "actions": ["closed", "opened"],
        "delivery_mode": "push",
        "include_bot_events": False,
    }


class Resolver:
    async def resolve(self, _request):
        return ResolvedCredential(access_token=SecretStr("test-installation"), provider="github", identity="service")


def credential_lease():
    return CredentialLease(
        Resolver(),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="github", name="work"),
            principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        ),
    )


def trigger():
    return Trigger(
        id=uuid4(),
        flow_id=uuid4(),
        user_id=uuid4(),
        name="github",
        provider="github",
        kind="github.issue",
        connection_id=uuid4(),
        public_id="opaque",
        signing_secret_encrypted="encrypted",  # noqa: S106  # pragma: allowlist secret
        config={"connection": "github/work", "repository": "org/repo", "actions": ["opened"]},
    )


@pytest.mark.parametrize("existing", [False, True])
async def test_provision_reconciles_exact_callback_and_pins_repository(monkeypatch, existing):
    from langflow.services.triggers.providers.github import runtime

    requests = []
    row = trigger()
    address = "https://langflow.example/api/v1/triggers/ingress/github/opaque"

    def handle(request):
        requests.append(request)
        if request.url.path == "/installation/repositories":
            return httpx.Response(200, json={"repositories": [], "total_count": 0})
        if request.url.path == "/repos/org/repo":
            return httpx.Response(200, json={"id": 80})
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": 44, "config": {"url": address}}] if existing else [])
        return httpx.Response(201, json={"id": 44})

    async def lease(*_args, **_kwargs):
        return credential_lease()

    async def ingress(*_args):
        return address

    from langflow.services.database.models.trigger.model import TriggerSubscription

    reservation = TriggerSubscription(
        trigger_id=row.id,
        connection_id=row.connection_id,
        provider="github",
        provider_subscription_id="pending:test",
        provider_state={"repository": "org/repo", "callback": address},
        state="pending",
    )

    async def lock(_session, _trigger_id):
        return row

    class Session:
        def add(self, _row):
            return None

        async def exec(self, _statement):
            return SimpleNamespace(first=lambda: None, all=lambda: [reservation])

        async def get(self, *_args, **_kwargs):
            return reservation

        async def flush(self):
            return None

    session = Session()
    monkeypatch.setattr(runtime, "GitHubClient", partial(GitHubClient, transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(runtime, "source_lease", lease)
    monkeypatch.setattr(runtime, "source_ingress_url", ingress)
    monkeypatch.setattr(runtime, "decrypt_api_key", lambda _value: SECRET)
    monkeypatch.setattr(runtime, "lock_trigger", lock)
    result = await runtime.provision(session, row)
    assert result is reservation
    stored = reservation.model_dump()
    request = requests[-1]
    assert request.method == ("PATCH" if existing else "POST")
    assert request.url.path == ("/repos/org/repo/hooks/44" if existing else "/repos/org/repo/hooks")
    body = json.loads(request.content)
    assert body["events"] == ["issues"]
    assert body["config"] == {"url": address, "content_type": "json", "secret": SECRET, "insecure_ssl": "0"}
    assert stored["expires_at"] is None
    assert stored["provider_subscription_id"] == "org/repo:44"
    assert stored["provider_state"]["repository_id"] == "80"
    assert SECRET not in repr(stored)


@pytest.mark.parametrize("status", [204, 404])
async def test_remote_cleanup_is_fixed_operation_and_missing_hook_succeeds(monkeypatch, status):
    from langflow.services.triggers.providers.github import runtime

    requests = []

    address = "https://langflow.example/api/v1/triggers/ingress/github/opaque"

    def handle(request):
        requests.append(request)
        if request.url.path == "/installation/repositories":
            return httpx.Response(200, json={})
        if request.method == "GET":
            return httpx.Response(200, json={"id": 44, "config": {"url": address}})
        return httpx.Response(status)

    async def idle(_task):
        return False

    monkeypatch.setattr(runtime, "_setup_in_progress", idle)
    monkeypatch.setattr(runtime, "GitHubClient", partial(GitHubClient, transport=httpx.MockTransport(handle)))
    task = SimpleNamespace(
        id=uuid4(),
        provider_state={"repository": "org/repo", "callback": address},
        provider_subscription_id="org/repo:44",
    )
    await runtime.revoke(task, credential_lease())
    assert requests[-1].method == "DELETE"
    assert requests[-1].url.path == "/repos/org/repo/hooks/44"
    assert requests[-2].method == "GET"


def manual_payload(**credentials):
    values = {
        "access_token": SecretStr("test-installation"),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
        **credentials,
    }
    return ConnectionCreate(
        provider_key="github",
        name="work",
        display_name="GitHub",
        granted_scopes=["user-claimed-permission"],
        executing_identity=ExecutingIdentityDescriptor(identity="user_delegated"),
        credentials=ConnectionCredentialWrite(**values),
    )


async def test_manual_installation_identity_discards_scope_and_account_claims(monkeypatch):
    from langflow.services.triggers.providers.github import credentials

    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"repositories": [], "total_count": 0})

    monkeypatch.setattr(credentials, "GitHubClient", partial(GitHubClient, transport=httpx.MockTransport(handle)))
    original = manual_payload()
    result = await credentials.validate_manual_credential(original, context="self_managed")
    assert result.executing_identity.identity == "service"
    assert result.executing_identity.account is None
    assert result.granted_scopes == []
    assert result.credentials.expires_at <= original.credentials.expires_at
    assert all(call.url.path == "/installation/repositories" for call in calls)


@pytest.mark.parametrize(
    "credential_values",
    [
        {"expires_at": None},
        {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)},
        {"refresh_token": SecretStr("not-allowed")},
        {"token_type": "Basic"},
    ],
)
async def test_manual_credentials_reject_invalid_expiry_and_secrets(credential_values):
    from langflow.services.triggers.providers.github.credentials import validate_manual_credential

    with pytest.raises(InvalidRequestError):
        await validate_manual_credential(manual_payload(**credential_values), context="self_managed")


async def test_manual_personal_token_fails_installation_probe(monkeypatch):
    from langflow.services.triggers.providers.github import credentials

    monkeypatch.setattr(
        credentials,
        "GitHubClient",
        partial(GitHubClient, transport=httpx.MockTransport(lambda _request: httpx.Response(403))),
    )
    with pytest.raises(ConnectionNotAuthorizedError):
        await credentials.validate_manual_credential(manual_payload(), context="desktop")


@pytest.mark.parametrize("include", [False, True])
def test_bot_event_requires_explicit_opt_in(include):
    value = payload()
    value["sender"]["type"] = "Bot"
    settings = secrets()
    settings.target_config["include_bot_events"] = include
    result = verify(signed(value), settings, tolerance_s=300)
    assert bool(result.payload) is include


def test_missing_optional_canvas_values_use_supported_defaults():
    result = normalize_config(
        "github.issue",
        {
            "connection": "github/work",
            "repository": "org/repo",
            "delivery_mode": None,
            "actions": None,
            "include_bot_events": None,
        },
    )
    assert result["delivery_mode"] == "push"
    assert result["actions"] == ["closed", "opened", "reopened"]
    assert result["include_bot_events"] is False


def test_provider_credentials_are_removed_from_signed_event_outputs():
    value = payload()
    value["repository"]["temp_clone_token"] = "test-only-provider-value"  # noqa: S105  # pragma: allowlist secret
    result = verify(signed(value), secrets(), tolerance_s=300)
    assert "temp_clone_token" not in result.payload["repository"]


@pytest.mark.parametrize("changed", [False, True])
async def test_pending_cleanup_paginates_original_repository_and_rechecks_each_callback(monkeypatch, changed):
    from langflow.services.triggers.providers.github import runtime
    from langflow.services.triggers.source_errors import SourceConfigurationError

    address = "https://langflow.example/api/v1/triggers/ingress/github/opaque"
    foreign = "https://foreign.example/unrelated"
    requests = []
    task_id = uuid4()

    async def idle(_task):
        return False

    def handle(request):
        requests.append(request)
        if request.url.path == "/installation/repositories":
            return httpx.Response(200, json={})
        assert request.url.host == "api.github.com"
        assert request.url.path.startswith("/repos/org/repo/hooks")
        if request.url.path.endswith("/hooks"):
            if request.url.params["page"] == "1":
                return httpx.Response(
                    200,
                    json=[{"id": i, "config": {"url": foreign}} for i in range(1, 101)],
                    headers={"Link": '<https://foreign.example/secrets>; rel="next"'},
                )
            assert request.url.params["page"] == "2"
            return httpx.Response(200, json=[{"id": 101, "config": {"url": address}}])
        assert request.url.path.endswith("/101")
        if request.method == "GET":
            return httpx.Response(200, json={"id": 101, "config": {"url": foreign if changed else address}})
        return httpx.Response(204)

    monkeypatch.setattr(runtime, "_setup_in_progress", idle)
    monkeypatch.setattr(runtime, "GitHubClient", partial(GitHubClient, transport=httpx.MockTransport(handle)))
    task = SimpleNamespace(
        id=task_id,
        provider_state={"repository": "org/repo", "callback": address},
        provider_subscription_id=f"pending:{task_id}",
    )
    if changed:
        with pytest.raises(SourceConfigurationError, match="no longer belongs"):
            await runtime.revoke(task, credential_lease())
        assert all(request.method != "DELETE" for request in requests)
    else:
        await runtime.revoke(task, credential_lease())
        assert [(request.method, request.url.path) for request in requests if request.method == "DELETE"] == [
            ("DELETE", "/repos/org/repo/hooks/101")
        ]
