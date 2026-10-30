"""Run the real GitHub provider through connection, trigger, ledger, and cleanup services."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from langflow.services.connection.service import (
    DatabaseConnectionResolverService,
    _decrypt_credential_payload,
    _encrypt_credential_payload,
)
from langflow.services.database.models.connection.model import Connection, ConnectionSecret
from langflow.services.database.models.connection.schemas import ConnectionCreate, ConnectionTokenRenewal
from langflow.services.database.models.trigger.model import (
    Trigger,
    TriggerCleanup,
    TriggerEvent,
    TriggerLease,
    TriggerSubscription,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import dispatcher, leases
from langflow.services.triggers.providers import registry
from langflow.services.triggers.providers.github import credentials, runtime
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from langflow.services.triggers.service import TriggerService
from langflow.services.triggers.source_cleanup import preserve_user_cleanup_credentials, run_cleanup_pass
from langflow.services.triggers.source_errors import SourceConfigurationError
from lfx.extension.bundle_registry import BundleRecord
from lfx.extension.loader import LoadedIntegration
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.integrations.errors import IntegrationPolicyBlockedError
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service
from lfx_github.client import GitHubClient
from lfx_github.components.github import GitHubOnIssueTriggerComponent
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster
BUNDLE_ROOT = Path(__file__).resolve().parents[5] / "bundles/github"


@pytest.fixture
def github_runtime(monkeypatch, client):  # noqa: ARG001
    from lfx.extension import bundle_registry

    manifest_path = BUNDLE_ROOT / "src/lfx_github/components/github/capabilities.v1.json"
    manifest = IntegrationCapabilityManifest.model_validate_json(manifest_path.read_text())
    owner = LoadedIntegration(
        extension_id="lfx-github",
        extension_version="0.1.0",
        bundle="github",
        provider_id="github",
        manifest_path=manifest_path,
        capability_manifest=manifest,
        distribution="lfx-github",
    )
    record = BundleRecord(
        bundle="github",
        extension_id="lfx-github",
        extension_version="0.1.0",
        slot="official",
        integrations=(owner,),
        components=tuple(SimpleNamespace(class_name=cap.component_ref) for cap in manifest.capabilities),
    )
    monkeypatch.setattr(
        bundle_registry,
        "get_default_registry",
        lambda: SimpleNamespace(snapshot=lambda: {"github": record}, list_integrations=lambda: [owner]),
    )
    monkeypatch.setattr(registry, "all_providers", lambda: (runtime.PROVIDER,))
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_origin", "https://langflow.example")
    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_enabled", True)
    hooks = {}
    calls = []
    controls = SimpleNamespace(
        fail_create_once=False,
        create_started=None,
        create_release=None,
        delete_started=None,
        delete_release=None,
        next_id=44,
        rejected_tokens=set(),
        installation_status=200,
        missing_repository=False,
    )

    async def handle(request):
        calls.append((request.method, request.url.path))
        if request.headers["authorization"].removeprefix("Bearer ") in controls.rejected_tokens:
            return httpx.Response(401)
        path = request.url.path
        if path == "/installation/repositories":
            if controls.installation_status != 200:
                return httpx.Response(
                    controls.installation_status, json={"message": "private provider response test-installation"}
                )
            return httpx.Response(
                200,
                json={
                    "total_count": 1,
                    "repositories": [{"id": 80, "full_name": "org/repo", "owner": {"id": 9, "login": "org"}}],
                },
            )
        if controls.missing_repository:
            return httpx.Response(404)
        if path == "/repos/org/repo":
            return httpx.Response(200, json={"id": 80})
        if request.method == "GET" and path.endswith("/hooks"):
            return httpx.Response(200, json=list(hooks.values()))
        if request.method == "POST" and path.endswith("/hooks"):
            hook_id = controls.next_id
            controls.next_id += 1
            if controls.create_started is not None:
                controls.create_started.set()
                await controls.create_release.wait()
            hooks[hook_id] = {"id": hook_id, **json.loads(request.content)}
            if controls.fail_create_once:
                controls.fail_create_once = False
                msg = "The response was lost after GitHub accepted the hook"
                raise httpx.ReadTimeout(msg, request=request)
            return httpx.Response(201, json={"id": hook_id})
        hook_id = int(path.rsplit("/", 1)[-1])
        if request.method == "GET":
            return httpx.Response(200, json=hooks[hook_id]) if hook_id in hooks else httpx.Response(404)
        if request.method == "PATCH" and hook_id in hooks:
            hooks[hook_id].update(json.loads(request.content))
            return httpx.Response(200, json={"id": hook_id})
        if request.method == "DELETE":
            if controls.delete_started is not None:
                controls.delete_started.set()
                await controls.delete_release.wait()
            hooks.pop(hook_id, None)
            return httpx.Response(204)
        pytest.fail("Unexpected GitHub HTTP operation")

    factory = partial(GitHubClient, transport=httpx.MockTransport(handle))
    monkeypatch.setattr(runtime, "GitHubClient", factory)
    monkeypatch.setattr(credentials, "GitHubClient", factory)
    return SimpleNamespace(hooks=hooks, calls=calls, controls=controls)


async def create_connection(user_id, *, background=True, token=None):
    payload = json.loads((BUNDLE_ROOT / "tests/fixtures/manual-token-dialog.json").read_text())
    payload["allow_non_interactive"] = background
    if token is not None:
        payload["credentials"]["access_token"] = token
    async with session_scope() as session:
        owner = await session.get(User, user_id)
        return await DatabaseConnectionResolverService().create(
            session, user=owner, payload=ConnectionCreate.model_validate(payload)
        )


async def save_trigger(flow_id, owner_id, *, connection="github/work", repository="org/repo", actions=None):
    node = GitHubOnIssueTriggerComponent(connection=connection, repository=repository, actions=actions or ["opened"])
    data = {
        "nodes": [
            {
                "id": "github-source",
                "data": {
                    "type": "ext:github:GitHubOnIssueTriggerComponent@official",
                    "node": {"template": {field: {"value": value} for field, value in node.trigger_config().items()}},
                },
            }
        ],
        "edges": [],
    }
    async with session_scope() as session:
        await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=owner_id, flow_data=data)
    async with session_scope() as session:
        return (await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).one()


async def test_missing_repository_cleanup_allows_corrected_trigger(github_runtime, trigger_owner, owned_flow):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner, repository="org/repoo")
    github_runtime.controls.missing_repository = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="Source activation failed"):
            await TriggerService().enable_and_activate(session, row=row)
    await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        await TriggerService().disable(session, row=await session.get(Trigger, trigger.id))
    assert await run_cleanup_pass() == 1
    async with session_scope() as session:
        assert (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).all() == []
    github_runtime.controls.missing_repository = False
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
    assert len(github_runtime.hooks) == 1


@pytest.mark.parametrize("reject_token", [False, True])
async def test_active_enable_preserves_live_subscription(
    github_runtime, trigger_owner, owned_flow, reject_token, client
):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        subscription = (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))
        ).one()
        before = subscription.model_dump()
    calls_before = list(github_runtime.calls)
    if reject_token:
        github_runtime.controls.rejected_tokens.add("test-installation")
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable(session, row=row)
        assert row.state == "active"
        subscription = await session.get(TriggerSubscription, before["id"])
        assert subscription.model_dump() == before
        assert (await runtime.ingress_secrets(session, row)).signing_secret
        await TriggerService().activate_push_source(session, row=row)
        assert row.state == "active"
    assert github_runtime.calls == calls_before
    body = json.dumps(
        {
            "repository": {"id": 80, "full_name": "org/repo"},
            "action": "opened",
            "issue": {"id": 100, "number": 4},
            "sender": {"id": 9, "type": "User"},
        }
    ).encode()
    hook = next(iter(github_runtime.hooks.values()))
    signature = "sha256=" + hmac.new(hook["config"]["secret"].encode(), body, hashlib.sha256).hexdigest()
    response = await client.post(
        f"/api/v1/triggers/ingress/github/{row.public_id}",
        content=body,
        headers={"X-Hub-Signature-256": signature, "X-GitHub-Event": "issues", "X-GitHub-Delivery": str(uuid4())},
    )
    assert response.status_code == 202, response.text


@pytest.mark.parametrize("renew", [False, True])
@pytest.mark.usefixtures("github_runtime")
async def test_dns_failure_has_safe_connection_error(client, logged_in_headers, monkeypatch, renew):
    from lfx.utils import ssrf_httpx
    from lfx.utils.ssrf_protection import SSRFProtectionError

    payload = json.loads((BUNDLE_ROOT / "tests/fixtures/manual-token-dialog.json").read_text())
    url = "/api/v1/connections"
    if renew:
        created = await client.post(url, headers=logged_in_headers, json=payload)
        assert created.status_code == 201
        url += f"/{created.json()['id']}/token"
        payload = {"credentials": payload["credentials"]}

    def unavailable(_url):
        msg = "DNS resolution failed for api.github.com with private diagnostic"
        raise SSRFProtectionError(msg)

    monkeypatch.setattr(credentials, "GitHubClient", GitHubClient)
    monkeypatch.setattr(ssrf_httpx, "is_ssrf_protection_enabled", lambda: True)
    monkeypatch.setattr(ssrf_httpx, "_validate_and_resolve_strict_url", unavailable)
    response = await client.post(url, headers=logged_in_headers, json=payload)
    assert response.status_code == 422, response.text
    assert "could not reach GitHub" in response.json()["detail"]
    assert "private diagnostic" not in response.text


@pytest.mark.usefixtures("github_runtime")
async def test_dialog_payload_is_accepted_and_catalog_requires_expiration(trigger_owner, client, logged_in_headers):
    connection = await create_connection(trigger_owner)
    assert connection.executing_identity.identity == "service"
    assert connection.executing_identity.account.model_dump(exclude_none=True) == {"id": "9", "display": "org"}
    async with session_scope() as session:
        stored = await session.get(Connection, connection.id)
        assert stored.executing_identity["account"] == {"id": "9", "display": "org", "tenant_id": None}
    assert connection.granted_scopes == []
    response = await client.get("/api/v1/integrations", headers=logged_in_headers)
    assert response.status_code == 200
    provider = next(item for item in response.json()["providers"] if item["provider_id"] == "github")
    assert provider["manual_token_profiles"] == [
        {"id": "github-installation", "identity": "service", "required_scopes": [], "requires_expiry": True}
    ]


@pytest.mark.parametrize("revoke_first", [False, True])
@pytest.mark.usefixtures("github_runtime")
async def test_manual_token_renewal_preserves_connection_identity(client, logged_in_headers, revoke_first):
    payload = json.loads((BUNDLE_ROOT / "tests/fixtures/manual-token-dialog.json").read_text())
    created = await client.post("/api/v1/connections", headers=logged_in_headers, json=payload)
    assert created.status_code == 201, created.text
    original = created.json()
    if revoke_first:
        revoked = await client.post(f"/api/v1/connections/{original['id']}/revoke", headers=logged_in_headers)
        assert revoked.status_code == 200, revoked.text
    replacement = {
        "credentials": {
            "access_token": "replacement-installation",  # pragma: allowlist secret
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        },
        "allow_non_interactive": False,
    }

    renewed = await client.post(
        f"/api/v1/connections/{original['id']}/token", headers=logged_in_headers, json=replacement
    )

    assert renewed.status_code == 200, renewed.text
    result = renewed.json()
    for field in ("id", "owner_id", "provider_key", "name", "display_name", "ownership_mode", "created_at"):
        assert result[field] == original[field]
    assert result["status"] == "ready"
    assert result["has_credentials"] is True
    assert result["allow_non_interactive"] is False
    assert "replacement-installation" not in renewed.text
    async with session_scope() as session:
        secret = await session.get(ConnectionSecret, UUID(original["id"]))
        assert (
            _decrypt_credential_payload(secret.encrypted_payload)["access_token"]
            == replacement["credentials"]["access_token"]
        )
        assert (
            len((await session.exec(select(Connection).where(Connection.owner_id == UUID(original["owner_id"])))).all())
            == 1
        )


@pytest.mark.parametrize("expiry", [None, "2020-01-01T12:00:00Z", "2030-01-01T12:00:00"])
async def test_token_renewal_requires_future_zoned_expiration(github_runtime, client, logged_in_headers, expiry):
    payload = json.loads((BUNDLE_ROOT / "tests/fixtures/manual-token-dialog.json").read_text())
    created = await client.post("/api/v1/connections", headers=logged_in_headers, json=payload)
    assert created.status_code == 201, created.text
    calls_before = len(github_runtime.calls)
    payload["credentials"]["expires_at"] = expiry

    response = await client.post(
        f"/api/v1/connections/{created.json()['id']}/token",
        headers=logged_in_headers,
        json={"credentials": payload["credentials"]},
    )

    assert response.status_code == 422, response.text
    assert len(github_runtime.calls) == calls_before


async def test_token_renewal_respects_provider_policy(github_runtime, client, logged_in_headers, monkeypatch):
    payload = json.loads((BUNDLE_ROOT / "tests/fixtures/manual-token-dialog.json").read_text())
    created = await client.post("/api/v1/connections", headers=logged_in_headers, json=payload)
    assert created.status_code == 201, created.text
    calls_before = len(github_runtime.calls)

    async def deny(*_args, **_kwargs):
        raise IntegrationPolicyBlockedError(provider="github")

    monkeypatch.setattr("langflow.services.connection.service.enforce_integration_policy_for_provider", deny)
    response = await client.post(
        f"/api/v1/connections/{created.json()['id']}/token",
        headers=logged_in_headers,
        json={"credentials": payload["credentials"]},
    )

    assert response.status_code == 403, response.text
    assert len(github_runtime.calls) == calls_before


async def test_renewed_connection_keeps_trigger_binding_and_webhook_cleanup(github_runtime, trigger_owner, owned_flow):
    connection = await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
    github_runtime.controls.rejected_tokens.add("test-installation")
    async with session_scope() as session:
        row = await session.get(Connection, connection.id)
        owner = await session.get(User, trigger_owner)
        await DatabaseConnectionResolverService().renew_token(
            session,
            row=row,
            user=owner,
            payload=ConnectionTokenRenewal.model_validate(
                {
                    "credentials": {
                        "access_token": "replacement-installation",  # pragma: allowlist secret
                        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                    },
                    "allow_non_interactive": True,
                }
            ),
        )
        row = await session.get(Trigger, trigger.id)
        assert row.connection_id == connection.id
        await TriggerService().disable(session, row=row)

    assert await run_cleanup_pass() == 1
    assert not github_runtime.hooks


@pytest.mark.parametrize("status", [401, 403, 429, 503])
async def test_rejected_token_renewal_preserves_existing_credential(github_runtime, client, logged_in_headers, status):
    payload = json.loads((BUNDLE_ROOT / "tests/fixtures/manual-token-dialog.json").read_text())
    created = await client.post("/api/v1/connections", headers=logged_in_headers, json=payload)
    assert created.status_code == 201, created.text
    connection_id = UUID(created.json()["id"])
    async with session_scope() as session:
        encrypted_before = (await session.get(ConnectionSecret, connection_id)).encrypted_payload
    github_runtime.controls.installation_status = status

    response = await client.post(
        f"/api/v1/connections/{connection_id}/token",
        headers=logged_in_headers,
        json={"credentials": payload["credentials"], "allow_non_interactive": False},
    )

    assert response.status_code == 422, response.text
    assert "private provider response" not in response.text
    async with session_scope() as session:
        assert (await session.get(ConnectionSecret, connection_id)).encrypted_payload == encrypted_before
        row = await session.get(Connection, connection_id)
        assert row.status == "ready"
        assert row.allow_non_interactive is True


async def test_foreign_connection_cannot_be_renewed(github_runtime, trigger_owner, client, logged_in_headers):
    connection = await create_connection(trigger_owner)
    calls_before = len(github_runtime.calls)
    payload = json.loads((BUNDLE_ROOT / "tests/fixtures/manual-token-dialog.json").read_text())

    response = await client.post(
        f"/api/v1/connections/{connection.id}/token",
        headers=logged_in_headers,
        json={"credentials": payload["credentials"]},
    )

    assert response.status_code == 404, response.text
    assert len(github_runtime.calls) == calls_before


@pytest.mark.parametrize(
    ("status", "expiry", "message"),
    [
        (401, "future", "GitHub rejected this token"),
        (403, "future", "GitHub App installation token"),
        (429, "future", "GitHub rate limited this token check"),
        (503, "future", "GitHub could not check this token"),
        (200, "past", "requires a future token expiration time"),
        (200, "missing", "requires a future token expiration time"),
    ],
)
async def test_rejected_manual_connection_returns_actionable_422(
    github_runtime, client, logged_in_headers, status, expiry, message
):
    github_runtime.controls.installation_status = status
    payload = json.loads((BUNDLE_ROOT / "tests/fixtures/manual-token-dialog.json").read_text())
    if expiry == "past":
        payload["credentials"]["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    elif expiry == "missing":
        payload["credentials"].pop("expires_at")
    response = await client.post("/api/v1/connections", json=payload, headers=logged_in_headers)
    assert response.status_code == 422, response.text
    assert message in response.json()["detail"]
    assert "test-installation" not in response.text
    assert "private provider response" not in response.text
    async with session_scope() as session:
        assert (await session.exec(select(Connection).where(Connection.provider_key == "github"))).all() == []


async def test_pause_cleanup_blocks_reenable_until_old_hook_is_deleted(github_runtime, trigger_owner, owned_flow):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
    assert len(github_runtime.hooks) == 1
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
    calls_before = len(github_runtime.calls)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(SourceConfigurationError, match="still being removed"):
            await TriggerService().enable(session, row=row)
    assert len(github_runtime.calls) == calls_before
    assert len(github_runtime.hooks) == 1
    assert await run_cleanup_pass() == 1
    assert github_runtime.hooks == {}
    async with session_scope() as session:
        assert (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).all() == []
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
    assert len(github_runtime.hooks) == 1
    assert await run_cleanup_pass() == 0
    assert len(github_runtime.hooks) == 1


@pytest.mark.parametrize("failure", ["expired", "revoked"])
@pytest.mark.parametrize("hook_removed", [False, True])
async def test_recreated_connection_recovers_cleanup_and_reenable(
    github_runtime, trigger_owner, owned_flow, failure, hook_removed
):
    connection = await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
    if failure == "expired":
        async with session_scope() as session:
            secret = await session.get(ConnectionSecret, connection.id)
            payload = _decrypt_credential_payload(secret.encrypted_payload)
            payload["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            secret.encrypted_payload = _encrypt_credential_payload(json.dumps(payload))
            session.add(secret)
    else:
        github_runtime.controls.rejected_tokens.add("test-installation")
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
    assert await run_cleanup_pass() == 0
    async with session_scope() as session:
        task = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).one()
        assert task.attempt == 1
        assert task.available_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
        original = await session.get(Connection, connection.id)
        await DatabaseConnectionResolverService().delete(session, original)
    replacement = await create_connection(trigger_owner, token="test-installation-renewed")  # noqa: S106  # pragma: allowlist secret
    assert replacement.id != connection.id
    await save_trigger(owned_flow, trigger_owner)
    if hook_removed:
        github_runtime.hooks.clear()
    assert await run_cleanup_pass() == 1
    assert github_runtime.hooks == {}
    async with session_scope() as session:
        assert (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).all() == []
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        assert row.connection_id == replacement.id
    assert set(github_runtime.hooks) == {45}
    assert await run_cleanup_pass() == 0
    assert set(github_runtime.hooks) == {45}


@pytest.mark.parametrize("invalid_binding", ["trigger_owner", "connection_owner", "provider", "background"])
async def test_cleanup_recovery_rejects_unrelated_or_unconsented_connection(
    github_runtime, trigger_owner, owned_flow, invalid_binding
):
    connection = await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        await TriggerService().disable(session, row=row)
        await DatabaseConnectionResolverService().delete(session, await session.get(Connection, connection.id))
    replacement = await create_connection(trigger_owner, token="test-installation-renewed")  # noqa: S106  # pragma: allowlist secret
    await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        if invalid_binding in {"trigger_owner", "connection_owner"}:
            foreign = User(username=f"github-foreign-{uuid4().hex}", password="test-only", is_active=True)  # noqa: S106  # pragma: allowlist secret
            session.add(foreign)
            await session.flush()
            if invalid_binding == "trigger_owner":
                row = await session.get(Trigger, trigger.id)
                row.user_id = foreign.id
            else:
                row = await session.get(Connection, replacement.id)
                row.owner_id = foreign.id
        else:
            row = await session.get(Connection, replacement.id)
            if invalid_binding == "provider":
                row.provider_key = "slack"
            else:
                row.allow_non_interactive = False
        session.add(row)
    before = len(github_runtime.calls)
    assert await run_cleanup_pass() == 0
    assert len(github_runtime.calls) == before
    assert set(github_runtime.hooks) == {44}
    async with session_scope() as session:
        task = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).one()
        assert task.connection_id == connection.id


async def test_cleanup_recovery_preserves_foreign_callback(github_runtime, trigger_owner, owned_flow):
    connection = await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        await TriggerService().disable(session, row=row)
        await DatabaseConnectionResolverService().delete(session, await session.get(Connection, connection.id))
    replacement = await create_connection(trigger_owner, token="test-installation-renewed")  # noqa: S106  # pragma: allowlist secret
    await save_trigger(owned_flow, trigger_owner)
    github_runtime.hooks[44]["config"]["url"] = "https://foreign.example/unrelated"
    before = len(github_runtime.calls)
    assert await run_cleanup_pass() == 0
    assert set(github_runtime.hooks) == {44}
    assert ("DELETE", "/repos/org/repo/hooks/44") not in github_runtime.calls[before:]
    async with session_scope() as session:
        task = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).one()
        assert task.connection_id == replacement.id
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(SourceConfigurationError, match="still being removed"):
            await TriggerService().enable(session, row=row)


async def test_signed_redelivery_enters_ledger_once_and_dispatches_as_owner(
    github_runtime, trigger_owner, owned_flow, client, fake_background_service
):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        public_id = row.public_id
    hook = next(iter(github_runtime.hooks.values()))
    body = json.dumps(
        {
            "repository": {"id": 80, "full_name": "org/repo"},
            "action": "opened",
            "issue": {"id": 100, "number": 4},
            "sender": {"id": 9, "type": "User"},
        }
    ).encode()
    signature = "sha256=" + hmac.new(hook["config"]["secret"].encode(), body, hashlib.sha256).hexdigest()
    url = f"/api/v1/triggers/ingress/github/{public_id}"
    for _ in range(2):
        response = await client.post(
            url,
            content=body,
            headers={"X-Hub-Signature-256": signature, "X-GitHub-Event": "issues", "X-GitHub-Delivery": str(uuid4())},
        )
        assert response.status_code == 202, response.text
    async with session_scope() as session:
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).all()
        assert len(events) == 1
        assert "secret" not in json.dumps(events[0].payload)
    assert await dispatcher.run_once(owner="github-dispatch-test") == 1
    assert fake_background_service.submits[0]["user_id"] == trigger_owner


@pytest.mark.parametrize("condition", ["consent", "owner", "ingress"])
async def test_missing_consent_cross_user_and_no_ingress_refuse_activation(
    github_runtime, trigger_owner, owned_flow, condition, monkeypatch
):
    await create_connection(trigger_owner, background=condition != "consent")
    if condition == "owner":
        async with session_scope() as session:
            foreign = User(username=f"github-foreign-{uuid4().hex}", password="test-only", is_active=True)  # noqa: S106  # pragma: allowlist secret
            session.add(foreign)
            await session.flush()
            foreign_id = foreign.id
        await create_connection(foreign_id)
    trigger = await save_trigger(owned_flow, trigger_owner)
    if condition == "owner":
        from langflow.services.database.models.connection.model import Connection

        async with session_scope() as session:
            from sqlmodel import update

            await session.exec(
                update(Connection).where(Connection.owner_id == trigger_owner).values(owner_id=foreign_id, name="other")
            )
    if condition == "ingress":
        monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_origin", None)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match=r"background|owner|connection|ingress|HTTPS"):
            await TriggerService().enable(session, row=row)
    assert github_runtime.hooks == {}


async def test_blocked_github_capability_never_creates_webhook(github_runtime, trigger_owner, owned_flow):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    bundle = get_policy_bundle_service()
    original = bundle.snapshot
    bundle.publish(
        replace(
            original,
            revision=original.revision + 1,
            initialized=True,
            blocked_integration_action_keys=frozenset({"integrations.github.trigger.issue"}),
        )
    )
    get_integration_policy_service().invalidate()
    try:
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            with pytest.raises((ValueError, IntegrationPolicyBlockedError), match=r"blocked|policy|available"):
                await TriggerService().enable_and_activate(session, row=row)
        assert github_runtime.hooks == {}
    finally:
        bundle.publish(replace(original, revision=bundle.snapshot.revision + 1))
        get_integration_policy_service().invalidate()


async def pending_subscription(trigger_id):
    async with session_scope() as session:
        rows = (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == trigger_id))
        ).all()
        assert len(rows) == 1
        return rows[0]


@pytest.mark.parametrize("remove", ["pause", "delete", "owner_delete"])
async def test_uncertain_create_keeps_cleanup_intent_after_pause_or_delete(
    github_runtime, trigger_owner, owned_flow, remove
):
    connection = await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    github_runtime.controls.fail_create_once = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="Source activation failed"):
            await TriggerService().enable_and_activate(session, row=row)
    reservation = await pending_subscription(trigger.id)
    assert reservation.state == "pending"
    assert reservation.provider_subscription_id == f"pending:{reservation.id}"
    assert reservation.connection_id == connection.id
    assert set(reservation.provider_state) == {"repository", "callback"}
    assert len(github_runtime.hooks) == 1
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        if remove == "pause":
            await TriggerService().disable(session, row=row)
        else:
            await TriggerService().delete(session, row=row)
        await session.flush()
        task = await session.get(TriggerCleanup, reservation.id)
        assert task is not None
        assert task.provider_subscription_id == reservation.provider_subscription_id
        if remove == "owner_delete":
            await preserve_user_cleanup_credentials(session, user_id=trigger_owner)
            assert task.encrypted_credential is not None
            await session.delete(await session.get(User, trigger_owner))
    assert await run_cleanup_pass() == 1
    assert github_runtime.hooks == {}
    async with session_scope() as session:
        assert await session.get(TriggerCleanup, reservation.id) is None


async def test_retry_after_uncertain_create_promotes_same_reservation_without_duplicate(
    github_runtime, trigger_owner, owned_flow
):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    github_runtime.controls.fail_create_once = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="Source activation failed"):
            await TriggerService().enable_and_activate(session, row=row)
    reservation_id = (await pending_subscription(trigger.id)).id
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
    subscription = await pending_subscription(trigger.id)
    assert subscription.id == reservation_id
    assert subscription.state == "active"
    assert subscription.provider_subscription_id == "org/repo:44"
    assert len(github_runtime.hooks) == 1
    assert github_runtime.calls.count(("POST", "/repos/org/repo/hooks")) == 1
    assert ("PATCH", "/repos/org/repo/hooks/44") in github_runtime.calls


async def test_successful_create_then_local_rollback_is_still_cleaned_up(github_runtime, trigger_owner, owned_flow):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable(session, row=row)
    reservation_id = (await pending_subscription(trigger.id)).id

    async def failed_transaction():
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            result = await runtime.provision(session, row)
            assert result.id == reservation_id
            assert result.state == "active"
            msg = "local transaction failed"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="local transaction failed"):
        await failed_transaction()
    assert len(github_runtime.hooks) == 1
    assert (await pending_subscription(trigger.id)).state == "pending"
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
    assert await run_cleanup_pass() == 1
    assert github_runtime.hooks == {}


async def test_cleanup_never_deletes_hook_reassigned_to_foreign_callback(github_runtime, trigger_owner, owned_flow):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
    github_runtime.hooks[44]["config"]["url"] = "https://foreign.example/unrelated"
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
    before = len(github_runtime.calls)
    assert await run_cleanup_pass() == 0
    assert 44 in github_runtime.hooks
    assert ("GET", "/repos/org/repo/hooks/44") in github_runtime.calls[before:]
    assert ("DELETE", "/repos/org/repo/hooks/44") not in github_runtime.calls[before:]
    async with session_scope() as session:
        tasks = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).all()
        assert len(tasks) == 1
        assert tasks[0].attempt == 1


@pytest.mark.parametrize("remove", ["pause", "delete"])
async def test_cleanup_defers_until_inflight_create_settles(github_runtime, trigger_owner, owned_flow, remove):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    controls = github_runtime.controls
    controls.create_started = asyncio.Event()
    controls.create_release = asyncio.Event()

    async def activate():
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            await TriggerService().enable_and_activate(session, row=row)

    activation = asyncio.create_task(activate())
    try:
        await asyncio.wait_for(controls.create_started.wait(), timeout=10)
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            if remove == "pause":
                await TriggerService().disable(session, row=row)
            else:
                await TriggerService().delete(session, row=row)
        assert github_runtime.hooks == {}
        assert await run_cleanup_pass() == 0
        async with session_scope() as session:
            task = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).one()
            assert task.attempt == 1
            if remove == "pause":
                row = await session.get(Trigger, trigger.id)
                with pytest.raises(SourceConfigurationError, match="still being removed"):
                    await TriggerService().enable(session, row=row)
        assert github_runtime.hooks == {}
    finally:
        controls.create_release.set()
        with pytest.raises(ValueError, match=r"superseded|changed"):
            await activation
    async with session_scope() as session:
        task = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).one()
        task.available_at = datetime.now(timezone.utc)
        session.add(task)
    assert await run_cleanup_pass() == 1
    assert github_runtime.hooks == {}


async def test_flow_save_during_setup_records_retryable_error(github_runtime, trigger_owner, owned_flow):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    controls = github_runtime.controls
    controls.create_started = asyncio.Event()
    controls.create_release = asyncio.Event()

    async def activate():
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            await TriggerService().enable_and_activate(session, row=row)

    activation = asyncio.create_task(activate())
    try:
        await asyncio.wait_for(controls.create_started.wait(), timeout=10)
        await save_trigger(owned_flow, trigger_owner, actions=["closed"])
    finally:
        controls.create_release.set()
        with pytest.raises(ValueError, match="superseded"):
            await activation
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        assert row.state == "error"
        assert "Enable the trigger to retry" in row.last_error
        assert row.config["actions"] == ["closed"]
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
    assert set(github_runtime.hooks) == {44}
    assert github_runtime.calls.count(("POST", "/repos/org/repo/hooks")) == 1


@pytest.mark.parametrize("provisioned", [False, True])
@pytest.mark.parametrize("live_initializer", [False, True])
async def test_interrupted_setup_becomes_retryable_after_source_lease_expires(
    github_runtime, trigger_owner, owned_flow, provisioned, live_initializer
):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable(session, row=row)
    if provisioned:
        async with session_scope() as session:
            await runtime.provision(session, await session.get(Trigger, trigger.id))
    name = f"trigger-source:{trigger.id}"
    async with session_scope() as session:
        assert await leases.acquire(session, name=name, owner="stopped-process", ttl_s=3600)
        row = await session.get(Trigger, trigger.id)
        row.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
        session.add(row)
    if live_initializer:
        await dispatcher.reconcile_push_sources()
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            assert row.state == "pending"
            assert row.last_error is None
    async with session_scope() as session:
        lease = await session.get(TriggerLease, name)
        lease.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(lease)
    await dispatcher.reconcile_push_sources()
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        assert row.state == "error"
        assert "Enable the trigger to retry" in row.last_error
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
    assert set(github_runtime.hooks) == {44}
    assert github_runtime.calls.count(("POST", "/repos/org/repo/hooks")) == 1


async def test_maintenance_does_not_arm_a_saved_trigger(github_runtime, trigger_owner, owned_flow):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        row.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
        session.add(row)
    await dispatcher.reconcile_push_sources()
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        assert row.state == "pending"
        assert row.last_error is None
    assert github_runtime.hooks == {}


async def test_claimed_cleanup_blocks_replacement_until_delete_finishes(github_runtime, trigger_owner, owned_flow):
    await create_connection(trigger_owner)
    trigger = await save_trigger(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        await TriggerService().disable(session, row=row)
    controls = github_runtime.controls
    controls.delete_started = asyncio.Event()
    controls.delete_release = asyncio.Event()
    cleanup = asyncio.create_task(run_cleanup_pass())
    try:
        await asyncio.wait_for(controls.delete_started.wait(), timeout=10)
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            with pytest.raises(SourceConfigurationError, match="still being removed"):
                await TriggerService().enable(session, row=row)
        assert len(github_runtime.hooks) == 1
    finally:
        controls.delete_release.set()
        assert await cleanup == 1
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
    assert set(github_runtime.hooks) == {45}
    assert await run_cleanup_pass() == 0
    assert set(github_runtime.hooks) == {45}
