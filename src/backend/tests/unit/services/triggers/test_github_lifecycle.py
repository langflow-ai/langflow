"""Run the real GitHub provider through connection, trigger, ledger, and cleanup services."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langflow.services.connection.service import DatabaseConnectionResolverService
from langflow.services.database.models.connection.schemas import ConnectionCreate
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerEvent, TriggerSubscription
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import dispatcher
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
    )

    async def handle(request):
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path == "/installation/repositories":
            return httpx.Response(200, json={"total_count": 1, "repositories": [{"id": 80, "full_name": "org/repo"}]})
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


async def create_connection(user_id, *, background=True):
    payload = json.loads((BUNDLE_ROOT / "tests/fixtures/manual-token-dialog.json").read_text())
    payload["allow_non_interactive"] = background
    async with session_scope() as session:
        owner = await session.get(User, user_id)
        return await DatabaseConnectionResolverService().create(
            session, user=owner, payload=ConnectionCreate.model_validate(payload)
        )


async def save_trigger(flow_id, owner_id, *, connection="github/work"):
    node = GitHubOnIssueTriggerComponent(connection=connection, repository="org/repo", actions=["opened"])
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


@pytest.mark.usefixtures("github_runtime")
async def test_dialog_payload_is_accepted_and_catalog_requires_expiration(trigger_owner, client, logged_in_headers):
    connection = await create_connection(trigger_owner)
    assert connection.executing_identity.identity == "service"
    assert connection.granted_scopes == []
    response = await client.get("/api/v1/integrations", headers=logged_in_headers)
    assert response.status_code == 200
    provider = next(item for item in response.json()["providers"] if item["provider_id"] == "github")
    assert provider["manual_token_profiles"] == [
        {"id": "github-installation", "identity": "service", "required_scopes": [], "requires_expiry": True}
    ]


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
