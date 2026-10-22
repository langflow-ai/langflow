"""Installed Confluence adapter ownership, durable delivery and cleanup contracts."""

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langflow.services.connection.oauth.broker import store_tokens
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerEvent, TriggerSubscription
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher, source_runtime
from langflow.services.triggers.providers import registry
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from langflow.services.triggers.service import TriggerService
from langflow.services.triggers.source_cleanup import run_cleanup_pass
from langflow.services.triggers.source_poll import collect_source, commit_source
from lfx.extension import load_extension
from lfx.extension.bundle_registry import BundleRecord
from lfx.integrations.errors import IntegrationPolicyBlockedError, ProviderUnavailableError
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service
from lfx_confluence.client import ConfluenceClient
from sqlmodel import select

from tests.unit.services.triggers.confluence_testkit import SITE, page

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def confluence(monkeypatch, client):  # noqa: ARG001 - initialize application services
    import lfx_confluence
    from langflow.services.triggers.providers.confluence import PROVIDER, collector
    from lfx.extension import bundle_registry

    monkeypatch.setenv("LANGFLOW_CONFLUENCE_CLOUD_ID", SITE)
    monkeypatch.setenv("LANGFLOW_CONFLUENCE_SPACE_IDS", "10,20")
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    loaded = load_extension(Path(lfx_confluence.__file__).parent, distribution="lfx-confluence")
    assert loaded.ok, loaded.errors
    record = BundleRecord(
        bundle="confluence_integrations",
        extension_id="lfx-confluence",
        extension_version="0.1.0",
        slot="official",
        components=tuple(loaded.components),
        integrations=tuple(loaded.integrations),
    )
    monkeypatch.setattr(
        bundle_registry,
        "get_default_registry",
        lambda: SimpleNamespace(
            snapshot=lambda: {"confluence_integrations": record}, list_integrations=lambda: loaded.integrations
        ),
    )
    monkeypatch.setattr(registry, "_cache_key", None)
    monkeypatch.setattr(registry, "_providers", {})
    original = registry.metadata.entry_points
    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda **kwargs: [
            SimpleNamespace(
                name="confluence", dist=SimpleNamespace(metadata={"Name": "lfx-confluence"}), load=lambda: PROVIDER
            )
        ]
        if kwargs.get("group") == registry.ENTRY_POINT_GROUP
        else original(**kwargs),
    )
    state = SimpleNamespace(version=1, fail=False, calls=[])

    def handler(request):
        state.calls.append(request)
        assert request.url.host == "api.atlassian.com"
        assert request.url.path == f"/ex/confluence/{SITE}/wiki/api/v2/pages"
        return (
            httpx.Response(503) if state.fail else httpx.Response(200, json={"results": [page(version=state.version)]})
        )

    monkeypatch.setattr(
        collector, "ConfluenceClient", lambda lease: ConfluenceClient(lease, transport=httpx.MockTransport(handler))
    )
    return state


async def connection(owner_id, *, allow=True, identity="user_delegated"):
    async with session_scope() as session:
        row = Connection(
            provider_key="confluence",
            name="work",
            display_name="Confluence work",
            owner_id=owner_id,
            status="ready",
            ownership_mode="user",
            allow_non_interactive=allow,
            executing_identity={"identity": identity, "account": {"id": "user-1", "tenant_id": SITE}},
        )
        session.add(row)
        await session.flush()
        await store_tokens(
            session,
            row,
            {"version": 1, "access_token": "synthetic-confluence-access", "token_type": "Bearer"},
            ["read:page:confluence", "write:page:confluence", "read:confluence-user", "offline_access"],
        )
        return row.id


async def reconcile(flow_id, owner_id):
    data = {
        "nodes": [
            {
                "id": "confluence-source",
                "data": {
                    "type": "ext:confluence_integrations:ConfluenceOnPageUpdatedTriggerComponent@official",
                    "node": {
                        "template": {
                            name: {"value": value}
                            for name, value in {
                                "connection": "confluence/work",
                                "space_id": "10",
                            }.items()
                        }
                    },
                },
            }
        ],
        "edges": [],
    }
    async with session_scope() as session:
        await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=owner_id, flow_data=data)
    async with session_scope() as session:
        return (await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).one()


async def activate(trigger_id):
    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        assert row.config["mechanism_id"] == "confluence.page.poll"


async def test_registered_listener_adapter_baselines_delivers_dedupes_and_pauses(
    confluence, trigger_owner, owned_flow, fake_background_service, monkeypatch
):
    from langflow.services.triggers.listeners import adapters
    from langflow.services.triggers.listeners.supervisor import ListenerSupervisor

    connection_id = await connection(trigger_owner)
    row = await reconcile(owned_flow, trigger_owner)
    assert row.last_error is None
    await activate(row.id)
    assert await source_runtime.sync_source(row.id) == 0
    confluence.version = 2
    monkeypatch.setattr(adapters, "_REGISTRY", {})
    adapters.register_builtin_adapters()
    supervisor = ListenerSupervisor(holder="confluence-listener-contract")

    async def wait_for_delivery():
        while True:
            async with session_scope() as session:
                events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == row.id))).all()
                if events:
                    assert len(events) == 1
                    assert events[0].payload["data"]["id"] == "1"
                    assert "synthetic-confluence-access" not in repr(events[0].payload)
                    return
            await asyncio.sleep(0.01)

    try:
        await supervisor.reconcile()
        assert isinstance(supervisor.workers[connection_id].adapter, adapters.ProviderSourcePollAdapter)
        await asyncio.wait_for(wait_for_delivery(), timeout=10)
    finally:
        await supervisor.stop()
    assert await source_runtime.sync_source(row.id) == 0
    assert await dispatcher.run_once(owner="confluence-dispatch") == 1
    assert len(fake_background_service.submits) == 1
    async with session_scope() as session:
        current = await session.get(Trigger, row.id)
        await TriggerService().disable(session, row=current)
        assert not (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))
        ).all()
        assert not (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == row.id))).all()
    assert await run_cleanup_pass() == 0
    calls = len(confluence.calls)
    assert await source_runtime.sync_source(row.id) == 0
    assert len(confluence.calls) == calls


async def test_failed_fetch_and_stale_replica_cannot_advance_cursor(confluence, trigger_owner, owned_flow):
    from langflow.services.triggers.source_clients import source_lease

    await connection(trigger_owner)
    row = await reconcile(owned_flow, trigger_owner)
    await activate(row.id)
    assert await source_runtime.sync_source(row.id) == 0
    async with session_scope() as session:
        original = dict((await session.get(Trigger, row.id)).provider_state)
    confluence.fail = True
    with pytest.raises(ProviderUnavailableError):
        await source_runtime.sync_source(row.id)
    async with session_scope() as session:
        assert (await session.get(Trigger, row.id)).provider_state == original
    confluence.fail = False
    confluence.version = 2
    async with session_scope() as session:
        current = await session.get(Trigger, row.id)
        lease = await source_lease(session, current, family="trigger_listener")
        snapshot = Trigger(**current.model_dump())
    first = await collect_source(snapshot, lease)
    second = await collect_source(snapshot, lease)
    async with session_scope() as session:
        assert await commit_source(session, trigger_id=row.id, source_round=first) == 1
    with pytest.raises(RuntimeError, match="cursor changed"):
        async with session_scope() as session:
            await commit_source(session, trigger_id=row.id, source_round=second)


@pytest.mark.parametrize("failure", ["owner", "consent", "identity", "scope", "policy"])
async def test_activation_enforces_owner_consent_identity_scopes_policy(confluence, trigger_owner, owned_flow, failure):
    owner = trigger_owner
    if failure == "owner":
        async with session_scope() as session:
            other = User(
                username=f"confluence-{uuid4().hex}",
                password="not-a-login",  # noqa: S106  # pragma: allowlist secret
                is_active=True,
            )
            session.add(other)
            await session.flush()
            owner = other.id
    identifier = await connection(
        owner, allow=failure != "consent", identity="bot" if failure == "identity" else "user_delegated"
    )
    if failure == "scope":
        async with session_scope() as session:
            row = await session.get(Connection, identifier)
            row.granted_scopes = []
            session.add(row)
    row = await reconcile(owned_flow, trigger_owner)
    bundle = get_policy_bundle_service()
    original = bundle.snapshot
    if failure == "policy":
        bundle.publish(
            replace(
                original,
                revision=original.revision + 1,
                initialized=True,
                blocked_integration_action_keys=frozenset({"integrations.confluence.trigger.updated"}),
            )
        )
        get_integration_policy_service().invalidate()
    try:
        async with session_scope() as session:
            current = await session.get(Trigger, row.id)
            with pytest.raises((ValueError, IntegrationPolicyBlockedError)):
                await TriggerService().enable_and_activate(session, row=current)
        assert not confluence.calls
    finally:
        bundle.publish(replace(original, revision=bundle.snapshot.revision + 1))
        get_integration_policy_service().invalidate()
