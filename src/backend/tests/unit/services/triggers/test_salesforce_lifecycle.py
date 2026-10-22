"""Salesforce sources pass through real shared ownership, cursor, and cleanup paths."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
from lfx_salesforce.client import SalesforceClient
from lfx_salesforce.schema import FIELDS, SYSTEM_FIELDS, iso
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster
ORG = "https://example.my.salesforce.com"
RECORD = "001000000000001AAA"


@pytest.fixture
def salesforce(monkeypatch, client):  # noqa: ARG001
    import lfx_salesforce
    from lfx.extension import bundle_registry

    monkeypatch.setenv("LANGFLOW_SALESFORCE_ORIGIN", ORG)
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    from langflow.services.triggers.providers.salesforce import PROVIDER, collector

    loaded = load_extension(Path(lfx_salesforce.__file__).parent, distribution="lfx-salesforce")
    assert loaded.ok, loaded.errors
    record = BundleRecord(
        bundle="salesforce",
        extension_id="lfx-salesforce",
        extension_version="0.1.0",
        slot="official",
        components=tuple(loaded.components),
        integrations=tuple(loaded.integrations),
    )
    monkeypatch.setattr(
        bundle_registry,
        "get_default_registry",
        lambda: SimpleNamespace(snapshot=lambda: {"salesforce": record}, list_integrations=lambda: loaded.integrations),
    )
    monkeypatch.setattr(registry, "_cache_key", None)
    monkeypatch.setattr(registry, "_providers", {})
    original = registry.metadata.entry_points
    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda **kwargs: [
            SimpleNamespace(
                name="salesforce", dist=SimpleNamespace(metadata={"Name": "lfx-salesforce"}), load=lambda: PROVIDER
            )
        ]
        if kwargs.get("group") == registry.ENTRY_POINT_GROUP
        else original(**kwargs),
    )
    state = SimpleNamespace(version="2026-10-22T12:00:00.000Z", fail=False, requests=[])

    def handle(request):
        state.requests.append(request)
        if request.url.path.endswith("describe"):
            return httpx.Response(
                200,
                json={
                    "replicateable": True,
                    "fields": [{"name": field} for field in [*SYSTEM_FIELDS, *FIELDS["Account"]]],
                },
            )
        if request.url.path.endswith("updated/"):
            return httpx.Response(200, json={"ids": [RECORD], "latestDateCovered": request.url.params["end"]})
        if state.fail:
            return httpx.Response(503, json={"message": "synthetic-access"})
        return httpx.Response(200, json=[{"Id": RECORD, "Name": "Example", "SystemModstamp": state.version}])

    monkeypatch.setattr(
        collector, "SalesforceClient", lambda lease: SalesforceClient(lease, transport=httpx.MockTransport(handle))
    )
    return state


async def connection(owner_id, *, allow=True, identity="user_delegated", name="work"):
    async with session_scope() as session:
        row = Connection(
            provider_key="salesforce",
            name=name,
            display_name="Salesforce work",
            owner_id=owner_id,
            status="ready",
            ownership_mode="user",
            allow_non_interactive=allow,
            executing_identity={"identity": identity, "account": {"id": "org/user", "tenant_id": ORG}},
        )
        session.add(row)
        await session.flush()
        await store_tokens(
            session,
            row,
            {"version": 1, "access_token": "synthetic-access", "token_type": "Bearer"},
            ["api", "id", "refresh_token"],
        )
        return row.id


async def reconcile(flow_id, owner_id):
    data = {
        "nodes": [
            {
                "id": "salesforce-source",
                "data": {
                    "type": "ext:salesforce:SalesforceOnRecordTriggerComponent@official",
                    "node": {
                        "template": {
                            name: {"value": value}
                            for name, value in {
                                "connection": "salesforce/work",
                                "object_name": "Account",
                                "fields": "Name",
                                "delivery_mode": "poll",
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


async def set_due_cursor(trigger_id):
    async with session_scope() as session:
        row = await session.get(Trigger, trigger_id)
        row.provider_state = {
            "latest_date_covered": iso(datetime.now(timezone.utc) - timedelta(minutes=2)),
            "baseline_complete": True,
        }
        session.add(row)


async def test_save_enable_baseline_change_replay_dispatch_and_local_cleanup(
    salesforce, trigger_owner, owned_flow, fake_background_service
):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    assert trigger.last_error is None
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        assert row.config["mechanism_id"] == "salesforce.record.poll"
    assert await source_runtime.sync_source(trigger.id) == 0
    await set_due_cursor(trigger.id)
    salesforce.version = "2026-10-22T12:01:00.000Z"
    assert await source_runtime.sync_source(trigger.id) == 1
    await set_due_cursor(trigger.id)
    assert await source_runtime.sync_source(trigger.id) == 0
    async with session_scope() as session:
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).all()
        assert len(events) == 1
        assert "synthetic-access" not in repr(events[0].payload)
    assert await dispatcher.run_once(owner="salesforce-dispatch") == 1
    assert len(fake_background_service.submits) == 1
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
        assert (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))
        ).all() == []
        assert (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == row.id))).all() == []
    assert await run_cleanup_pass() == 0
    calls = len(salesforce.requests)
    assert await source_runtime.sync_source(trigger.id) == 0
    assert len(salesforce.requests) == calls


async def test_failed_fetch_and_stale_replica_cannot_advance_cursor(salesforce, trigger_owner, owned_flow):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable(session, row=row)
    await set_due_cursor(trigger.id)
    async with session_scope() as session:
        before = dict((await session.get(Trigger, trigger.id)).provider_state)
    salesforce.fail = True
    with pytest.raises(ProviderUnavailableError):
        await source_runtime.sync_source(trigger.id)
    async with session_scope() as session:
        assert (await session.get(Trigger, trigger.id)).provider_state == before
    salesforce.fail = False
    from langflow.services.triggers.source_clients import source_lease

    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        lease = await source_lease(session, row, family="trigger_listener")
        snapshot = Trigger(**row.model_dump())
    round_one = await collect_source(snapshot, lease)
    round_two = await collect_source(snapshot, lease)
    async with session_scope() as session:
        assert await commit_source(session, trigger_id=trigger.id, source_round=round_one) == 1
    with pytest.raises(RuntimeError, match="cursor changed"):
        async with session_scope() as session:
            await commit_source(session, trigger_id=trigger.id, source_round=round_two)


@pytest.mark.parametrize("failure", ["owner", "consent", "identity", "scope", "policy"])
async def test_activation_blocks_foreign_owner_missing_consent_identity_scopes_and_policy(
    salesforce, trigger_owner, owned_flow, failure
):
    owner_id = trigger_owner
    if failure == "owner":
        async with session_scope() as session:
            other = User(username=f"salesforce-{uuid4().hex}", password="not-a-login", is_active=True)  # noqa: S106
            session.add(other)
            await session.flush()
            owner_id = other.id
    connection_id = await connection(
        owner_id, allow=failure != "consent", identity="bot" if failure == "identity" else "user_delegated"
    )
    if failure == "scope":
        async with session_scope() as session:
            row = await session.get(Connection, connection_id)
            row.granted_scopes = ["api"]
            session.add(row)
    trigger = await reconcile(owned_flow, trigger_owner)
    bundle = get_policy_bundle_service()
    original = bundle.snapshot
    if failure == "policy":
        bundle.publish(
            replace(
                original,
                revision=original.revision + 1,
                initialized=True,
                blocked_integration_action_keys=frozenset({"integrations.salesforce.trigger.record"}),
            )
        )
        get_integration_policy_service().invalidate()
    try:
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            with pytest.raises((ValueError, IntegrationPolicyBlockedError)):
                await TriggerService().enable(session, row=row)
        assert salesforce.requests == []
    finally:
        bundle.publish(replace(original, revision=bundle.snapshot.revision + 1))
        get_integration_policy_service().invalidate()


@pytest.mark.usefixtures("salesforce")
async def test_resume_discards_paused_interval_and_starts_new_baseline(trigger_owner, owned_flow):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable(session, row=row)
    await set_due_cursor(trigger.id)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
        await TriggerService().enable(session, row=row)
        assert row.provider_state == {}
    assert await source_runtime.sync_source(trigger.id) == 0


async def test_registered_salesforce_poll_adapter_delivers_changes_and_rechecks_consent(
    salesforce, trigger_owner, owned_flow, monkeypatch
):
    import asyncio

    from langflow.services.triggers.listeners import adapters

    connection_id = await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable(session, row=row)
        snapshot = adapters.ListenerTrigger(
            id=row.id,
            flow_id=row.flow_id,
            user_id=row.user_id,
            kind=row.kind,
            provider=row.provider,
            mechanism_id=row.config["mechanism_id"],
            config=dict(row.config),
            provider_state=dict(row.provider_state),
        )
    monkeypatch.setattr(adapters, "_REGISTRY", {})
    adapters.register_builtin_adapters()
    adapter = adapters.build_adapter(snapshot)
    assert isinstance(adapter, adapters.ProviderSourcePollAdapter)

    async def unexpected_callback(*_args, **_kwargs):
        pytest.fail("The adapter bypassed shared source collection and cursor commits")

    context = adapters.ListenerContext(
        connection_id=connection_id,
        triggers=[snapshot],
        emit=unexpected_callback,
        save_cursor=unexpected_callback,
        resolve_credential=unexpected_callback,
        stopping=asyncio.Event(),
    )
    assert await adapter.poll(context) == 0
    assert len(salesforce.requests) == 3
    await set_due_cursor(trigger.id)
    salesforce.version = "2026-10-22T12:01:00.000Z"
    assert await adapter.poll(context) == 1
    await set_due_cursor(trigger.id)
    assert await adapter.poll(context) == 0
    async with session_scope() as session:
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).all()
        assert len(events) == 1
        row = await session.get(Connection, connection_id)
        row.allow_non_interactive = False
        session.add(row)
    requests_before = len(salesforce.requests)
    with pytest.raises(ValueError, match="background"):
        await adapter.poll(context)
    assert len(salesforce.requests) == requests_before
