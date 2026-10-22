"""ServiceNow OAuth and actual adapter paths use the shared durable runtime."""

from __future__ import annotations

import asyncio
import importlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langflow.services.auth.utils import encrypt_api_key
from langflow.services.connection.oauth.config import OAuthError, OAuthRegistration
from langflow.services.database.models.connection.model import Connection, ConnectionSecret
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher
from langflow.services.triggers.providers import registry
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from langflow.services.triggers.service import TriggerService
from langflow.services.triggers.source_clients import source_lease
from langflow.services.triggers.source_poll import collect_source, commit_source
from lfx.extension.bundle_registry import BundleRecord
from lfx.extension.loader._types import LoadedIntegration
from lfx.integrations.errors import IntegrationPolicyBlockedError
from lfx.integrations.models import ConnectionAccount, ConnectionRef, ResolvedCredential
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service
from lfx_servicenow.client import ServiceNowClient
from lfx_servicenow.manifest import manifest
from lfx_servicenow.schema import READ_SCOPE, WRITE_SCOPE
from pydantic import SecretStr
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster
ROOT = "https://acme.service-now.com"
ID = "a" * 32
NOW = datetime(2026, 10, 22, 12, 0, 5, tzinfo=timezone.utc)


@pytest.fixture
def provider(monkeypatch, client):  # noqa: ARG001
    monkeypatch.setenv("LANGFLOW_SERVICENOW_ORIGIN", ROOT)
    monkeypatch.setenv("LANGFLOW_SERVICENOW_TABLES", "incident")
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    from langflow.services.triggers.providers.servicenow import oauth, runtime
    from lfx.extension import bundle_registry

    importlib.reload(oauth)
    importlib.reload(runtime)
    owner = LoadedIntegration(
        extension_id="lfx-servicenow",
        extension_version="0.1.0",
        bundle="servicenow",
        provider_id="servicenow",
        manifest_path=Path("capabilities.v1.json"),
        capability_manifest=manifest(),
        distribution="lfx-servicenow",
    )
    record = BundleRecord(
        bundle="servicenow",
        extension_id="lfx-servicenow",
        extension_version="0.1.0",
        slot="official",
        integrations=(owner,),
        components=tuple(SimpleNamespace(class_name=item.component_ref) for item in manifest().capabilities),
    )
    monkeypatch.setattr(
        bundle_registry,
        "get_default_registry",
        lambda: SimpleNamespace(
            snapshot=lambda: {"servicenow": record},
            list_integrations=lambda: [owner],
        ),
    )
    monkeypatch.setattr(registry, "_cache_key", None)
    monkeypatch.setattr(registry, "_cache_records", ())
    monkeypatch.setattr(registry, "_providers", {})
    original = registry.metadata.entry_points
    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda **kwargs: [
            SimpleNamespace(
                name="servicenow",
                dist=SimpleNamespace(metadata={"Name": "lfx-servicenow"}),
                load=lambda: runtime.PROVIDER,
            )
        ]
        if kwargs.get("group") == registry.ENTRY_POINT_GROUP
        else original(**kwargs),
    )
    monkeypatch.setattr(runtime, "_now", lambda: NOW)
    return SimpleNamespace(oauth=oauth, runtime=runtime)


def registration(**changes):
    return OAuthRegistration(
        provider="servicenow",
        client_id="client",
        client_secret=SecretStr("synthetic-secret"),
        redirect_uri="https://langflow.example/api/v1/connections/oauth/servicenow/callback",
        scopes=[READ_SCOPE, WRITE_SCOPE],
        tenant=ROOT,
        **changes,
    )


async def _connection(owner, *, consent=True, identity="user_delegated"):
    async with session_scope() as session:
        row = Connection(
            provider_key="servicenow",
            name="work",
            display_name="Work",
            owner_id=owner,
            status="ready",
            allow_non_interactive=consent,
            executing_identity={"identity": identity, "account": {"id": ROOT, "tenant_id": ROOT}},
            granted_scopes=[READ_SCOPE, WRITE_SCOPE],
        )
        session.add(row)
        await session.flush()
        payload = {"version": 1, "access_token": "synthetic-access", "token_type": "Bearer", "expires_at": None}
        session.add(ConnectionSecret(connection_id=row.id, encrypted_payload=encrypt_api_key(json.dumps(payload))))
        return row


async def _reconcile(flow_id, owner_id, *, status=False):
    component = "ServiceNowOnStatusChangeTriggerComponent" if status else "ServiceNowOnTicketCreatedTriggerComponent"
    data = {
        "nodes": [
            {
                "id": "servicenow-source",
                "data": {
                    "type": f"ext:servicenow:{component}@official",
                    "node": {
                        "template": {
                            key: {"value": value}
                            for key, value in {
                                "connection": "servicenow/work",
                                "table": "incident",
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


def install_transport(provider, monkeypatch, rows):
    seen = []

    def handler(request):
        seen.append(request)
        query = request.url.params["sysparm_query"]
        result = [] if "sys_id>" in query else rows
        return httpx.Response(200, json={"result": result}, headers={"X-Total-Count": str(len(result))})

    monkeypatch.setattr(
        provider.runtime, "ServiceNowClient", partial(ServiceNowClient, transport=httpx.MockTransport(handler))
    )
    return seen


async def test_oauth_initial_and_refresh_bind_issuing_instance(provider):
    reg = registration()
    token, account = await provider.oauth.parse_token(
        reg,
        {
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
            "token_type": "Bearer",
            "scope": f"{READ_SCOPE} {WRITE_SCOPE}",
            "expires_in": 1800,
        },
        refresh=False,
    )
    assert token["expires_in"] == 1800
    assert account == {"id": ROOT, "tenant_id": ROOT, "display": "ServiceNow instance"}
    assert provider.oauth.OAUTH.checked_endpoints(reg) == (ROOT + "/oauth_auth.do", ROOT + "/oauth_token.do")
    _, account = await provider.oauth.parse_token(
        reg, {"access_token": "new", "token_type": "Bearer", "expires_in": 1800}, refresh=True
    )
    assert account is None


@pytest.mark.parametrize("policy", ["all", "read", "write"])
async def test_dialog_scope_defaults_include_connection_prerequisite(provider, policy):
    import json
    from pathlib import Path
    from urllib.parse import parse_qs, urlsplit

    from langflow.services.connection.oauth import providers

    root = Path(__file__).resolve().parents[6]
    scenarios = json.loads((root / "src/bundles/servicenow/tests/fixtures/consent-scopes.json").read_text())
    scopes = next(item["scopes"] for item in scenarios if item["policy"] == policy)
    selected = registration()
    query = parse_qs(
        urlsplit(
            providers.authorization_url(
                selected,
                state="opaque",
                verifier="verifier",
                scopes=scopes,
            )
        ).query
    )
    assert set(query["scope"][0].split()) == set(scopes)
    token, _ = await provider.oauth.parse_token(
        selected,
        {
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
            "token_type": "Bearer",
            "expires_in": 1800,
            "scope": " ".join(scopes),
        },
        refresh=False,
    )
    assert set(token["scope"].split()) == set(scopes)
    assert READ_SCOPE in scopes
    assert (WRITE_SCOPE in scopes) == (policy != "read")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"access_token": "x", "token_type": "Bearer", "expires_in": 1800},
        {"access_token": "x", "refresh_token": "r", "token_type": "Bearer", "expires_in": 1800, "scope": "useraccount"},
    ],
)
async def test_oauth_invalid_grants_fail_without_echoing(provider, body):
    with pytest.raises(OAuthError, match="invalid credential") as exc:
        await provider.oauth.parse_token(registration(), body, refresh=False)
    assert "synthetic" not in str(exc.value)


@pytest.mark.parametrize(
    "changes",
    [{"context": "desktop", "client_type": "public"}, {"tenant": "https://evil.example"}, {"scopes": ["useraccount"]}],
)
@pytest.mark.usefixtures("provider")
def test_registration_rejects_unsupported_context_origin_scope(changes):
    values = registration().model_dump()
    values.update(changes)
    with pytest.raises((OAuthError, ValueError)):
        OAuthRegistration.model_validate(values)


async def test_creation_save_enable_poll_commit_replay_dispatch_pause(
    provider, trigger_owner, owned_flow, monkeypatch, fake_background_service
):
    await _connection(trigger_owner)
    row = await _reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.config["mechanism_id"] == "servicenow.poll"
        assert row.state == "active"
        row.provider_state = {"watermark": "2026-10-22 11:59:00", "baseline_complete": True}
        session.add(row)
    seen = install_transport(
        provider, monkeypatch, [{"sys_id": ID, "number": "INC001", "sys_created_on": "2026-10-22 11:59:40"}]
    )
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        lease = await source_lease(session, row, family="trigger_listener")
    collected = await collect_source(row, lease)
    assert row.provider_state["watermark"] == "2026-10-22 11:59:00"
    async with session_scope() as session:
        assert await commit_source(session, trigger_id=row.id, source_round=collected) == 1
    async with session_scope() as session:
        with pytest.raises(RuntimeError, match="cursor changed"):
            await commit_source(session, trigger_id=row.id, source_round=collected)
    async with session_scope() as session:
        current = await session.get(Trigger, row.id)
    replay = await collect_source(current, lease)
    async with session_scope() as session:
        assert await commit_source(session, trigger_id=row.id, source_round=replay) == 0
    assert len(seen) == 4
    assert await dispatcher.run_once(owner="servicenow-test-dispatch") == 1
    assert len(fake_background_service.submits) == 1
    async with session_scope() as session:
        current = await session.get(Trigger, row.id)
        await TriggerService().disable(session, row=current)
        assert current.state == "paused"


async def test_failed_transaction_keeps_cursor_and_redelivers(provider, trigger_owner, owned_flow, monkeypatch):
    await _connection(trigger_owner)
    row = await _reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        await TriggerService().enable_and_activate(session, row=row)
        row.provider_state = {"watermark": "2026-10-22 11:59:00", "baseline_complete": True}
        session.add(row)
    install_transport(provider, monkeypatch, [{"sys_id": ID, "sys_created_on": "2026-10-22 11:59:40"}])
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        lease = await source_lease(session, row, family="trigger_listener")
    result = await collect_source(row, lease)

    async def rollback():
        async with session_scope() as session:
            assert await commit_source(session, trigger_id=row.id, source_round=result) == 1
            msg = "forced rollback"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="forced rollback"):
        await rollback()
    async with session_scope() as session:
        saved = await session.get(Trigger, row.id)
        assert saved.provider_state == row.provider_state
        assert not (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == row.id))).all()
        assert await commit_source(session, trigger_id=row.id, source_round=result) == 1


async def test_status_baseline_unchanged_new_and_changed_records(provider, monkeypatch):
    class Lease:
        ref = ConnectionRef(provider="servicenow", name="work")

        async def get_credential(self):
            return ResolvedCredential(
                access_token=SecretStr("synthetic-access"),
                provider="servicenow",
                identity="user_delegated",
                account=ConnectionAccount(id=ROOT, tenant_id=ROOT),
                granted_scopes=frozenset({READ_SCOPE}),
                scopes_verified=True,
            )

    row = SimpleNamespace(
        kind="servicenow.status_changed", config={"table": "incident"}, provider_state={}, connection_id=uuid4()
    )
    record = {"sys_id": ID, "state": "1", "sys_updated_on": "2026-10-22 11:59:40", "sys_mod_count": "1"}
    install_transport(provider, monkeypatch, [record])
    baseline = await provider.runtime.collect(row, Lease())
    assert baseline.items == []
    assert baseline.cursor["observed_states"] == {ID: "1"}
    row.provider_state = baseline.cursor
    assert (await provider.runtime.collect(row, Lease())).items == []
    record["state"] = "2"
    record["sys_mod_count"] = "2"
    changed = await provider.runtime.collect(row, Lease())
    assert len(changed.items) == 1
    assert changed.items[0]["version"].endswith(":2:2")
    assert row.provider_state["observed_states"][ID] == "1"


@pytest.mark.parametrize("failure", ["foreign-owner", "consent", "identity", "policy", "wrong-tenant", "scope"])
@pytest.mark.usefixtures("provider")
async def test_activation_denies_invalid_authority(trigger_owner, owned_flow, failure):
    owner_id = trigger_owner
    if failure == "foreign-owner":
        async with session_scope() as session:
            other = User(username=f"servicenow-other-{uuid4().hex}", password="not-a-login", is_active=True)  # noqa: S106
            session.add(other)
            await session.flush()
            owner_id = other.id
    await _connection(
        owner_id, consent=failure != "consent", identity="service" if failure == "identity" else "user_delegated"
    )
    row = await _reconcile(owned_flow, trigger_owner)
    if failure in {"wrong-tenant", "scope"}:
        async with session_scope() as session:
            connection = (await session.exec(select(Connection).where(Connection.owner_id == owner_id))).one()
            if failure == "wrong-tenant":
                connection.executing_identity = {
                    "identity": "user_delegated",
                    "account": {"id": "other", "tenant_id": "https://other.service-now.com"},
                }
            else:
                connection.granted_scopes = []
            session.add(connection)
    policy = get_policy_bundle_service()
    original = policy.snapshot
    if failure == "policy":
        policy.publish(
            replace(
                original,
                revision=original.revision + 1,
                initialized=True,
                blocked_integration_action_keys=frozenset({"integrations.servicenow.trigger.ticket_created"}),
            )
        )
        get_integration_policy_service().invalidate()
    try:
        async with session_scope() as session:
            row = await session.get(Trigger, row.id)
            with pytest.raises((ValueError, IntegrationPolicyBlockedError)):
                await TriggerService().enable_and_activate(session, row=row)
    finally:
        policy.publish(replace(original, revision=policy.snapshot.revision + 1))
        get_integration_policy_service().invalidate()


async def test_installed_poll_adapter_runs_actual_servicenow_collector(
    provider, trigger_owner, owned_flow, monkeypatch
):
    from langflow.services.triggers.listeners import adapters
    from langflow.services.triggers.listeners.supervisor import ListenerSupervisor

    connection = await _connection(trigger_owner)
    row = await _reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, row.id)
        await TriggerService().enable_and_activate(session, row=row)
        row.provider_state = {"watermark": "2026-10-22 11:59:00", "baseline_complete": True}
        session.add(row)
    install_transport(provider, monkeypatch, [{"sys_id": ID, "sys_created_on": "2026-10-22 11:59:40"}])
    monkeypatch.setattr(adapters, "_REGISTRY", {})
    adapters.register_builtin_adapters()
    supervisor = ListenerSupervisor(holder="servicenow-provider-test")

    async def delivered():
        while True:
            async with session_scope() as session:
                events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == row.id))).all()
                if events:
                    assert len(events) == 1
                    assert events[0].payload["id"] == ID
                    return
            await asyncio.sleep(0.01)

    try:
        await supervisor.reconcile()
        assert connection.id in supervisor.workers
        assert isinstance(supervisor.workers[connection.id].adapter, adapters.ProviderSourcePollAdapter)
        await asyncio.wait_for(delivered(), timeout=5)
    finally:
        await supervisor.stop()


class FixedLease:
    ref = ConnectionRef(provider="servicenow", name="work")

    async def get_credential(self):
        return ResolvedCredential(
            access_token=SecretStr("synthetic-access"),
            provider="servicenow",
            identity="user_delegated",
            account=ConnectionAccount(id=ROOT, tenant_id=ROOT),
            granted_scopes=frozenset({READ_SCOPE}),
            scopes_verified=True,
        )


@pytest.mark.parametrize("record_count", [10000, 10001])
async def test_status_record_limit_allows_an_exhaustion_probe(provider, monkeypatch, record_count):
    row = SimpleNamespace(
        kind="servicenow.status_changed", config={"table": "incident"}, provider_state={}, connection_id=uuid4()
    )
    requests = []

    def handler(request):
        query = request.url.params["sysparm_query"]
        requests.append(query)
        after = int(query.split("sys_id>", 1)[1].split("^", 1)[0], 16) if "sys_id>" in query else 0
        rows = [
            {
                "sys_id": f"{index:032x}",
                "state": "1",
                "sys_mod_count": "1",
                "sys_updated_on": "2026-10-22 11:59:40",
            }
            for index in range(after + 1, min(after + 100, record_count) + 1)
        ]
        return httpx.Response(200, json={"result": rows}, headers={"X-Total-Count": str(len(rows))})

    monkeypatch.setattr(
        provider.runtime, "ServiceNowClient", partial(ServiceNowClient, transport=httpx.MockTransport(handler))
    )
    if record_count == 10000:
        result = await provider.runtime.collect(row, FixedLease())
        assert len(result.cursor["observed_states"]) == 10000
        assert result.cursor["baseline_complete"] is True
        assert result.items == []
    else:
        with pytest.raises(ValueError, match="page limit"):
            await provider.runtime.collect(row, FixedLease())
    assert len(requests) == 101
    assert row.provider_state == {}


@pytest.mark.parametrize(
    "failure", ["empty-acl", "missing-count", "unsorted", "wrong-time", "page-budget", "record-budget"]
)
async def test_incomplete_rounds_preserve_cursor(provider, monkeypatch, failure):
    prior = {"watermark": "2026-10-22 11:59:00", "baseline_complete": True, "observed_states": {ID: "1"}}
    row = SimpleNamespace(
        kind="servicenow.status_changed", config={"table": "incident"}, provider_state=prior, connection_id=uuid4()
    )
    record = {"sys_id": ID, "state": "2", "sys_mod_count": "2", "sys_updated_on": "2026-10-22 11:59:40"}
    if failure == "record-budget":
        monkeypatch.setattr(provider.runtime, "_MAX_TRACKED", 0)
    if failure == "page-budget":
        monkeypatch.setattr(provider.runtime, "_MAX_PAGES", 1)
    if failure == "wrong-time":
        record["sys_updated_on"] = "2026-10-22 12:30:00"

    def handler(request):
        query = request.url.params["sysparm_query"]
        if failure in {"empty-acl", "missing-count"}:
            return httpx.Response(
                200, json={"result": []}, headers={} if failure == "missing-count" else {"X-Total-Count": "2"}
            )
        rows = [record] if failure in {"unsorted", "page-budget"} or "sys_id>" not in query else []
        return httpx.Response(200, json={"result": rows}, headers={"X-Total-Count": str(len(rows))})

    monkeypatch.setattr(
        provider.runtime, "ServiceNowClient", partial(ServiceNowClient, transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ValueError, match="ServiceNow"):
        await provider.runtime.collect(row, FixedLease())
    assert row.provider_state == prior
    assert row.provider_state["observed_states"] == {ID: "1"}


async def test_creation_overlap_never_replays_before_activation(provider, monkeypatch):
    row = SimpleNamespace(
        kind="servicenow.ticket_created",
        config={"table": "incident"},
        provider_state={
            "watermark": "2026-10-22 11:59:50",
            "started_at": "2026-10-22 11:59:45",
            "baseline_complete": True,
        },
        connection_id=uuid4(),
    )
    seen = install_transport(provider, monkeypatch, [])
    result = await provider.runtime.collect(row, FixedLease())
    assert "sys_created_on>=2026-10-22 11:59:45" in seen[0].url.params["sysparm_query"]
    assert result.cursor["started_at"] == "2026-10-22 11:59:45"


async def test_initial_creation_watermark_does_not_fetch_history(provider, monkeypatch):
    row = SimpleNamespace(
        kind="servicenow.ticket_created", config={"table": "incident"}, provider_state={}, connection_id=uuid4()
    )
    monkeypatch.setattr(provider.runtime, "ServiceNowClient", lambda *_: pytest.fail("baseline requested history"))
    result = await provider.runtime.collect(row, FixedLease())
    assert result.items == []
    assert result.baseline is True


async def test_status_return_to_previous_value_has_new_delivery_identity(provider, monkeypatch):
    prior = {"watermark": "2026-10-22 11:59:00", "baseline_complete": True, "observed_states": {ID: "1"}}
    row = SimpleNamespace(
        kind="servicenow.status_changed", config={"table": "incident"}, provider_state=prior, connection_id=uuid4()
    )
    record = {"sys_id": ID, "state": "2", "sys_updated_on": "2026-10-22 11:59:40", "sys_mod_count": "2"}
    install_transport(provider, monkeypatch, [record])
    changed = await provider.runtime.collect(row, FixedLease())
    row.provider_state = changed.cursor
    record.update(state="1", sys_mod_count="3")
    returned = await provider.runtime.collect(row, FixedLease())
    assert returned.items[0]["version"] != changed.items[0]["version"]
    assert returned.items[0]["data"]["state"] == "1"


async def test_creation_keyset_round_includes_rows_after_a_short_page(provider, monkeypatch):
    row = SimpleNamespace(
        kind="servicenow.ticket_created",
        config={"table": "incident"},
        provider_state={"watermark": "2026-10-22 11:59:00", "baseline_complete": True},
        connection_id=uuid4(),
    )
    ids = ["a" * 32, "b" * 32]
    seen = []

    def handler(request):
        query = request.url.params["sysparm_query"]
        seen.append(query)
        index = 0 if "sys_id>" not in query else 1 if ids[0] in query else 2
        rows = [{"sys_id": ids[index], "sys_created_on": "2026-10-22 11:59:40"}] if index < 2 else []
        return httpx.Response(200, json={"result": rows}, headers={"X-Total-Count": str(2 - index)})

    monkeypatch.setattr(
        provider.runtime, "ServiceNowClient", partial(ServiceNowClient, transport=httpx.MockTransport(handler))
    )
    result = await provider.runtime.collect(row, FixedLease())
    assert [item["id"] for item in result.items] == ids
    assert len(seen) == 3
    assert f"sys_id>{ids[0]}" in seen[1]
    assert row.provider_state["watermark"] == "2026-10-22 11:59:00"
