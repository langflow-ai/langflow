"""Installed GitLab catalog ownership, delivery, dispatch, and durable cleanup."""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from functools import partial
from importlib import metadata
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langflow.services.connection.service import DatabaseConnectionResolverService
from langflow.services.data_subjects.stop import stop_builder
from langflow.services.database.models.connection.model import Connection, ConnectionSecret
from langflow.services.database.models.connection.schemas import ConnectionCreate
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerEvent, TriggerSubscription
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher, source_runtime
from langflow.services.triggers.providers import registry
from langflow.services.triggers.providers.gitlab import runtime
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from langflow.services.triggers.service import TriggerService
from langflow.services.triggers.source_cleanup import preserve_user_cleanup_credentials, run_cleanup_pass
from lfx.extension import bundle_registry
from lfx.extension.bundle_registry import BundleRecord, BundleRegistry
from lfx.extension.loader import load_installed_extensions
from lfx.integrations.errors import IntegrationPolicyBlockedError
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service
from lfx_gitlab.client import GitLabClient
from sqlmodel import select

from tests.unit.services.triggers.test_gitlab_provider import payload, signed

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def gitlab(monkeypatch, client):  # noqa: ARG001
    distribution = metadata.distribution("lfx-gitlab")
    monkeypatch.setattr(bundle_registry, "_default_registry", BundleRegistry())
    results = load_installed_extensions([distribution])
    assert len(results) == 1
    result = results[0]
    assert result.ok, result.errors
    assert len(result.components) == 11
    record = BundleRecord(
        bundle=result.bundle,
        extension_id=result.extension_id,
        extension_version=result.extension_version,
        slot=result.slot,
        components=tuple(result.components),
        integrations=tuple(result.integrations),
        distribution=result.distribution,
        source_path=result.source_path,
    )
    bundle_registry.get_default_registry().install_bundle(record)
    monkeypatch.setattr(registry, "_cache_key", None)
    monkeypatch.setattr(registry, "_cache_records", ())
    monkeypatch.setattr(registry, "_providers", {})
    assert registry.get_provider("gitlab") is runtime.PROVIDER
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    monkeypatch.delenv("LANGFLOW_GITLAB_ORIGIN", raising=False)
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_origin", "https://langflow.example")
    remote = SimpleNamespace(
        hooks={},
        requests=[],
        created=0,
        deleted=[],
        account_id=9,
        timeout_once=False,
        version="19.1.0",
        duplicate=False,
    )

    def handle(request):
        remote.requests.append(request)
        assert request.url.host == "gitlab.com"
        assert request.headers["private-token"] == "synthetic-gitlab-token"
        path = request.url.path.removeprefix("/api/v4")
        if path == "/personal_access_tokens/self":
            return httpx.Response(
                200,
                json={
                    "id": 5,
                    "user_id": 9,
                    "scopes": ["api"],
                    "active": True,
                    "revoked": False,
                    "expires_at": "2099-01-01",
                },
            )
        if path == "/user":
            return httpx.Response(
                200, json={"id": remote.account_id, "username": "owner", "bot": False, "state": "active"}
            )
        if path == "/version":
            return httpx.Response(200, json={"version": remote.version})
        if path == "/projects/80":
            return httpx.Response(200, json={"id": 80})
        if path == "/projects/80/hooks" and request.method == "GET":
            hooks = list(remote.hooks.values())
            return httpx.Response(
                200, json=hooks + [{**hook, "id": 999} for hook in hooks] if remote.duplicate else hooks
            )
        if path == "/projects/80/hooks" and request.method == "POST":
            body = json.loads(request.content)
            remote.created += 1
            body["id"] = remote.created
            assert body["signing_token"].startswith("whsec_")
            assert body["token"] == ""
            remote.hooks[remote.created] = body
            if remote.timeout_once:
                remote.timeout_once = False
                msg = "lost create response"
                raise httpx.ReadTimeout(msg, request=request)
            return httpx.Response(201, json=body)
        if path.startswith("/projects/80/hooks/"):
            hook_id = int(path.rsplit("/", 1)[-1])
            if hook_id not in remote.hooks:
                return httpx.Response(404)
            if request.method == "PUT":
                remote.hooks[hook_id] = {**json.loads(request.content), "id": hook_id}
            if request.method == "DELETE":
                remote.deleted.append(hook_id)
                del remote.hooks[hook_id]
                return httpx.Response(204)
            return httpx.Response(200, json=remote.hooks[hook_id])
        pytest.fail(f"Unexpected GitLab request {request.method} {path}")

    factory = partial(GitLabClient, transport=httpx.MockTransport(handle))
    monkeypatch.setattr(runtime, "GitLabClient", factory)
    monkeypatch.setattr("langflow.services.triggers.providers.gitlab.credentials.GitLabClient", factory)
    return remote


async def connection(owner_id, *, allow=True):
    async with session_scope() as session:
        user = await session.get(User, owner_id)
        return await DatabaseConnectionResolverService().create(
            session,
            user=user,
            payload=ConnectionCreate(
                provider_key="gitlab",
                name="work",
                display_name="GitLab",
                executing_identity={"identity": "user_delegated"},
                allow_non_interactive=allow,
                credentials={"access_token": "synthetic-gitlab-token"},
            ),
        )


async def reconcile(flow_id, owner_id, *, kind="issue"):
    from lfx_gitlab.components.gitlab import GitLabOnIssueTriggerComponent, GitLabOnMergeRequestTriggerComponent

    cls = GitLabOnIssueTriggerComponent if kind == "issue" else GitLabOnMergeRequestTriggerComponent
    component = cls(connection="gitlab/work", project_id=80, actions=["open", "close"])
    # Persist the actual input values, including declared defaults, as the canvas saves them.
    values = {field.name: getattr(component, field.name, field.value) for field in cls.inputs}
    data = {
        "nodes": [
            {
                "id": "gitlab-source",
                "data": {
                    "type": f"ext:gitlab:{cls.__name__}@official",
                    "node": {"template": {name: {"value": value} for name, value in values.items()}},
                },
            }
        ],
        "edges": [],
    }
    async with session_scope() as session:
        await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=owner_id, flow_data=data)
    async with session_scope() as session:
        return (await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).one()


@pytest.mark.parametrize("kind", ["issue", "merge_request"])
async def test_installed_save_enable_ingress_dedupe_dispatch_pause_cleanup(
    gitlab, trigger_owner, owned_flow, client, fake_background_service, kind
):
    from langflow.services.auth.utils import decrypt_api_key

    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner, kind=kind)
    assert trigger.state == "pending"
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        secret = decrypt_api_key(row.signing_secret_encrypted)
        public_id = row.public_id
        await TriggerService().enable_and_activate(session, row=row)
        subscription = (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))
        ).one()
        assert subscription.expires_at is None
        assert subscription.renew_after is None
    assert gitlab.created == 1
    assert await source_runtime.sync_source(trigger.id) == 0
    assert await dispatcher.reconcile_push_sources() == 0
    url = f"/api/v1/triggers/ingress/gitlab/{public_id}"
    value = payload(f"gitlab.{kind}")
    for message_id in ["first-id", "different-id"]:
        request = signed(value, secret=secret, message_id=message_id)
        response = await client.post(url, content=request.body, headers=request.headers)
        assert response.status_code == 202, response.text
    forged = signed(value)
    assert (await client.post(url, content=forged.body, headers=forged.headers)).status_code == 404
    wrong = signed({**value, "project": {"id": 81}}, secret=secret)
    assert (await client.post(url, content=wrong.body, headers=wrong.headers)).status_code == 404
    async with session_scope() as session:
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).all()
        assert len(events) == 1
        assert events[0].payload["delivery"]["object_attributes"]["iid"] == 4
    assert await dispatcher.run_once(owner="gitlab-dispatch-test") == 1
    assert len(fake_background_service.submits) == 1
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
        assert len((await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == row.id))).all()) == 1
    assert await run_cleanup_pass() == 1
    assert gitlab.deleted == [1]
    assert (await client.post(url, content=request.body, headers=request.headers)).status_code == 404


async def test_uncertain_create_reconciles_existing_callback(gitlab, trigger_owner, owned_flow):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    gitlab.timeout_once = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="Source activation failed"):
            await TriggerService().enable_and_activate(session, row=row)
    assert gitlab.created == 1
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
    assert gitlab.created == 1
    assert len(gitlab.hooks) == 1
    assert sum(request.method == "PUT" for request in gitlab.requests) == 1


@pytest.mark.parametrize("failure", ["foreign-owner", "consent", "identity", "policy"])
async def test_activation_denies_owner_consent_identity_and_policy(gitlab, trigger_owner, owned_flow, failure):
    owner_id = trigger_owner
    if failure == "foreign-owner":
        async with session_scope() as session:
            other = User(username=f"gitlab-other-{uuid4().hex}", password="not-a-login", is_active=True)  # noqa: S106
            session.add(other)
            await session.flush()
            owner_id = other.id
    created = await connection(owner_id, allow=failure != "consent")
    if failure == "identity":
        async with session_scope() as session:
            row = await session.get(Connection, created.id)
            row.executing_identity = {"identity": "service"}
            session.add(row)
    trigger = await reconcile(owned_flow, trigger_owner)
    policy = get_policy_bundle_service()
    before = policy.snapshot
    if failure == "policy":
        policy.publish(
            replace(
                before,
                revision=before.revision + 1,
                initialized=True,
                blocked_integration_action_keys=frozenset({"integrations.gitlab.trigger.issue"}),
            )
        )
        get_integration_policy_service().invalidate()
    try:
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            with pytest.raises((ValueError, IntegrationPolicyBlockedError)):
                await TriggerService().enable_and_activate(session, row=row)
        assert gitlab.created == 0
    finally:
        policy.publish(replace(before, revision=policy.snapshot.revision + 1))
        get_integration_policy_service().invalidate()


async def test_unsupported_gitlab_version_never_creates_unsigned_hook(gitlab, trigger_owner, owned_flow):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    gitlab.version = "18.11.0"
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match=r"19\.1"):
            await TriggerService().enable_and_activate(session, row=row)
    assert gitlab.created == 0


@pytest.mark.parametrize("missing", [False, True])
async def test_cleanup_checks_remote_callback_and_handles_already_removed_hooks(
    gitlab, trigger_owner, owned_flow, missing
):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        await TriggerService().disable(session, row=row)
    if missing:
        gitlab.hooks.clear()
        assert await run_cleanup_pass() == 1
    else:
        gitlab.hooks[1]["url"] = "https://other.example/callback"
        assert await run_cleanup_pass() == 0
        async with session_scope() as session:
            cleanup = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).one()
            assert cleanup.attempt == 1
            assert cleanup.last_error is not None
    assert gitlab.deleted == []


@pytest.mark.parametrize("fault", [None, "tampered-state", "expired", "other-account", "other-callback"])
async def test_sealed_cleanup_snapshot_survives_connection_removal(gitlab, trigger_owner, owned_flow, fault):
    created = await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        await TriggerService().disable(session, row=row)
        await preserve_user_cleanup_credentials(session, user_id=trigger_owner)
        cleanup = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == row.id))).one()
        assert cleanup.encrypted_credential is not None
        if fault == "tampered-state":
            cleanup.provider_state = {**cleanup.provider_state, "account_id": "10"}
        if fault == "expired":
            cleanup.credential_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(cleanup)
        secret = await session.get(ConnectionSecret, created.id)
        await session.delete(secret)
        stored = await session.get(Connection, created.id)
        await session.delete(stored)
    if fault == "other-account":
        gitlab.account_id = 10
    if fault == "other-callback":
        gitlab.hooks[1]["url"] = "https://other.example/callback"
    assert await run_cleanup_pass() == (1 if fault is None else 0)
    assert gitlab.deleted == ([1] if fault is None else [])


async def test_pause_reenable_waits_for_old_cleanup_before_replacing_hook(gitlab, trigger_owner, owned_flow):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        await TriggerService().disable(session, row=row)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="previous GitLab webhook cleanup"):
            await TriggerService().enable_and_activate(session, row=row)
    assert gitlab.created == 1
    assert gitlab.deleted == []
    assert await run_cleanup_pass() == 1
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
    assert gitlab.created == 2
    assert gitlab.deleted == [1]
    assert list(gitlab.hooks) == [2]
    assert await run_cleanup_pass() == 0
    assert list(gitlab.hooks) == [2]


async def test_duplicate_remote_callbacks_stop_recovery(gitlab, trigger_owner, owned_flow):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    gitlab.timeout_once = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="Source activation failed"):
            await TriggerService().enable_and_activate(session, row=row)
    gitlab.duplicate = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="Duplicate GitLab callbacks"):
            await TriggerService().enable_and_activate(session, row=row)
    assert gitlab.created == 1


@pytest.mark.parametrize("operation", ["pause", "delete", "owner-delete"])
async def test_unknown_remote_id_still_has_durable_cleanup_after_timeout(gitlab, trigger_owner, owned_flow, operation):
    created = await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    gitlab.timeout_once = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="Source activation failed"):
            await TriggerService().enable_and_activate(session, row=row)
    assert gitlab.created == 1
    async with session_scope() as session:
        reservation = (
            await session.exec(
                select(TriggerSubscription).where(
                    TriggerSubscription.trigger_id == trigger.id,
                    TriggerSubscription.state == "pending",
                )
            )
        ).one()
        assert reservation.provider_subscription_id == f"pending:{trigger.id}"
        assert reservation.provider_state["hook_id"] is None
        assert "synthetic-gitlab-token" not in json.dumps(reservation.provider_state)
        row = await session.get(Trigger, trigger.id)
        if operation == "pause":
            await TriggerService().disable(session, row=row)
        elif operation == "owner-delete":
            user = await session.get(User, trigger_owner)
            await stop_builder(session, user)
            assert user.is_active is False
        else:
            await TriggerService().delete(session, row=row)
        task = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).one()
        assert task.provider_subscription_id == f"pending:{trigger.id}"
        if operation == "owner-delete":
            assert task.encrypted_credential is not None
            secret = await session.get(ConnectionSecret, created.id)
            await session.delete(secret)
            stored = await session.get(Connection, created.id)
            await session.delete(stored)
    assert await run_cleanup_pass() == 1
    assert gitlab.deleted == [1]
    assert gitlab.hooks == {}


@pytest.mark.parametrize("fault", ["foreign-url", "foreign-proof", "wrong-account"])
async def test_unknown_id_cleanup_leaves_unrelated_hooks_unchanged(gitlab, trigger_owner, owned_flow, fault):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    gitlab.timeout_once = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="Source activation failed"):
            await TriggerService().enable_and_activate(session, row=row)
    gitlab.hooks[77] = {**gitlab.hooks[1], "id": 77, "url": "https://unrelated.example/callback"}
    if fault == "foreign-url":
        gitlab.hooks[1]["url"] = "https://other.example/callback"
    elif fault == "foreign-proof":
        gitlab.hooks[1]["description"] = "foreign-owned-hook"
    else:
        gitlab.account_id = 10
    before = json.loads(json.dumps(gitlab.hooks))
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
    assert await run_cleanup_pass() == (1 if fault == "foreign-url" else 0)
    assert gitlab.deleted == []
    assert json.loads(json.dumps(gitlab.hooks)) == before


async def test_pending_intent_blocks_reenable_until_cleanup_finishes(gitlab, trigger_owner, owned_flow):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    gitlab.timeout_once = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="Source activation failed"):
            await TriggerService().enable_and_activate(session, row=row)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="previous GitLab webhook cleanup"):
            await TriggerService().enable_and_activate(session, row=row)
    assert await run_cleanup_pass() == 1
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
    assert gitlab.created == 2
    assert gitlab.deleted == [1]
    assert list(gitlab.hooks) == [2]


async def test_unproven_callback_cannot_be_adopted_during_retry(gitlab, trigger_owner, owned_flow):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    gitlab.timeout_once = True
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="Source activation failed"):
            await TriggerService().enable_and_activate(session, row=row)
    gitlab.hooks[1]["description"] = "foreign-owned-hook"
    before = json.loads(json.dumps(gitlab.hooks))
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="ownership proof"):
            await TriggerService().enable_and_activate(session, row=row)
    assert json.loads(json.dumps(gitlab.hooks)) == before
    assert gitlab.created == 1
    assert not any(request.method == "PUT" for request in gitlab.requests)


async def test_callback_reservation_is_durable_before_provider_creation(gitlab, trigger_owner, owned_flow):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable(session, row=row)
    assert gitlab.created == 0
    async with session_scope() as session:
        reservation = (
            await session.exec(
                select(TriggerSubscription).where(
                    TriggerSubscription.trigger_id == trigger.id,
                )
            )
        ).one()
        assert reservation.state == "pending"
        reservation_id = reservation.id
        assert reservation.provider_state["callback"].endswith(row.public_id)
        assert reservation.provider_state["ownership_tag"].startswith("langflow-owner-v1-")
        row = await session.get(Trigger, trigger.id)
        await TriggerService().activate_push_source(session, row=row)
    async with session_scope() as session:
        reservation = await session.get(TriggerSubscription, reservation_id)
        assert reservation.state == "active"
        assert reservation.provider_subscription_id == "80:1"
    assert gitlab.created == 1
