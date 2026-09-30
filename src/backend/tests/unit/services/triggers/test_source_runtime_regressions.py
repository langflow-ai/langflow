"""Real-database regressions for activation, recovery, cleanup and lease loss."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from langflow.services.connection.oauth.locking import lock_connection
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import (
    Trigger,
    TriggerCleanup,
    TriggerLease,
    TriggerSourceVersion,
    TriggerSubscription,
)
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import (
    leases,
    source_cleanup,
    source_clients,
    source_poll,
    source_runtime,
    source_subscription,
)
from langflow.services.triggers.cleanup import delete_triggers
from langflow.services.triggers.lease_guard import LeaseLostError, run_guarded
from langflow.services.triggers.source_arming import public_ingress_origin
from langflow.services.triggers.source_delivery import append_and_advance
from lfx.integrations.errors import ConnectionUnresolvedError
from lfx.integrations.models import ResolvedCredential
from pydantic import SecretStr
from sqlmodel import select, update

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize(
    "uri",
    [
        "http://localhost:7860/callback",
        "https://localhost/callback",
        "https://127.0.0.1/callback",
        "https://[::1]/callback",
        "https://10.0.0.1/callback",
        "https://host.internal/callback",
    ],
)
def test_local_callbacks_cannot_select_push(uri):
    assert public_ingress_origin(uri) is None


@pytest.fixture
async def source_connection(trigger_owner):
    async with session_scope() as session:
        connection = Connection(
            provider_key="microsoft",
            name=f"source_{uuid4().hex}",
            display_name="Source",
            owner_id=trigger_owner,
            status="ready",
            allow_non_interactive=True,
            granted_scopes=["Mail.Read"],
        )
        session.add(connection)
        await session.flush()
        return connection.id


@pytest.fixture
def provider_http(source_connection, monkeypatch):
    calls = []

    class Resolver:
        async def resolve(self, request):
            # The production OAuth resolver acquires this same independent
            # write lock. A caller holding a SQLite writer would self-block.
            async with session_scope() as session:
                assert await lock_connection(session, source_connection) is not None
            return ResolvedCredential(access_token=SecretStr("fixture-token"), provider=request.ref.provider)

    monkeypatch.setattr(source_clients, "get_connection_resolver_service", Resolver)
    monkeypatch.setattr(source_cleanup, "get_connection_resolver_service", Resolver)

    def reply(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "fixture@example.test", "historyId": "1"})
        if request.method == "POST" and request.url.path == "/v1.0/subscriptions":
            return httpx.Response(
                201,
                json={
                    "id": str(uuid4()),
                    "expirationDateTime": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                },
            )
        if request.method == "PATCH" and request.url.path.startswith("/v1.0/subscriptions/"):
            return httpx.Response(
                200, json={"expirationDateTime": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
            )
        if request.method == "POST" and request.url.path.endswith("/watch"):
            return httpx.Response(
                200,
                json={
                    "resourceId": "new-resource",
                    "expiration": str(int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp() * 1000)),
                },
            )
        if request.method in {"DELETE", "POST"}:
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"value": [], "@odata.deltaLink": "https://graph.microsoft.com/v1.0/delta"})

    transport = httpx.MockTransport(reply)
    original = source_clients.SourceHTTP

    def client(lease, *, origin):
        return original(lease, origin=origin, transport=transport)

    monkeypatch.setattr(source_clients, "SourceHTTP", client)
    monkeypatch.setattr(source_poll, "SourceHTTP", client)
    monkeypatch.setattr(source_subscription, "SourceHTTP", client)

    async def ingress(_session, _trigger):
        return "https://example.test/api/v1/triggers/ingress/microsoft/test"

    monkeypatch.setattr(source_subscription, "source_ingress_url", ingress)
    return calls


async def test_push_activation_does_not_hold_a_writer_during_token_resolution(
    make_trigger, source_connection, provider_http
):
    trigger_id = await make_trigger(
        kind="microsoft.mail",
        provider="microsoft",
        connection_id=source_connection,
        state="pending",
        config={"mechanism_id": "microsoft.graph_change_notifications"},
    )
    await asyncio.wait_for(source_runtime.initialize_source(trigger_id), timeout=10)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert trigger.state == "active"
        assert trigger.provider_state["baseline_complete"]
        watches = (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == trigger_id))
        ).all()
        assert len(watches) == 1
        assert watches[0].state == "active"
    assert provider_http.count(("POST", "/v1.0/subscriptions")) == 1


async def test_source_commit_refuses_a_pause_during_collection(make_trigger):
    trigger_id = await make_trigger(kind="google.calendar", provider="google", config={"calendar_id": "primary"})
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.state = "paused"
        session.add(trigger)
    async with session_scope() as session:
        with pytest.raises(RuntimeError, match="settings or state changed"):
            await append_and_advance(
                session,
                trigger_id=trigger_id,
                items=[],
                cursor={"sync_token": "late"},
                expected_config={"calendar_id": "primary"},
            )


async def test_deletion_preserves_remote_cleanup_and_removes_source_versions(make_trigger, source_connection):
    trigger_id = await make_trigger(kind="microsoft.mail", provider="microsoft", connection_id=source_connection)
    async with session_scope() as session:
        session.add(
            TriggerSubscription(
                trigger_id=trigger_id,
                connection_id=source_connection,
                provider="microsoft",
                provider_subscription_id="remote-watch",
                state="active",
            )
        )
        session.add(
            TriggerSourceVersion(
                trigger_id=trigger_id,
                item_key="item",
                provider="microsoft",
                resource="mail:inbox",
                provider_item_id="item",
                version="one",
            )
        )
    async with session_scope() as session:
        await delete_triggers(session, trigger_ids=[trigger_id])
    async with session_scope() as session:
        assert await session.get(Trigger, trigger_id) is None
        assert not (
            await session.exec(select(TriggerSourceVersion).where(TriggerSourceVersion.trigger_id == trigger_id))
        ).all()
        cleanup = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger_id))).one()
        assert cleanup.provider_subscription_id == "remote-watch"


@pytest.mark.parametrize("separate_connection", [False, True])
async def test_gmail_cleanup_preserves_sibling_watch_even_after_opt_out(
    make_trigger, source_connection, provider_http, trigger_owner, separate_connection
):
    key = hashlib.sha256(b"fixture@example.test").hexdigest()
    connection_ids = [source_connection, source_connection]
    async with session_scope() as session:
        connection = await session.get(Connection, source_connection)
        connection.provider_key = "google"
        connection.allow_non_interactive = False
        session.add(connection)
        if separate_connection:
            other = Connection(
                provider_key="google",
                name=f"other_{uuid4().hex}",
                display_name="Other",
                owner_id=trigger_owner,
                status="ready",
                allow_non_interactive=False,
            )
            session.add(other)
            await session.flush()
            connection_ids[1] = other.id
    ids = [
        await make_trigger(kind="google.gmail", provider="google", connection_id=identifier)
        for identifier in connection_ids
    ]
    async with session_scope() as session:
        for trigger_id, connection_id in zip(ids, connection_ids, strict=True):
            session.add(
                TriggerSubscription(
                    trigger_id=trigger_id,
                    connection_id=connection_id,
                    provider="google",
                    provider_subscription_id=str(uuid4()),
                    state="active",
                    provider_state={"kind": "gmail", "mailbox_key": key},
                )
            )
    async with session_scope() as session:
        await delete_triggers(session, trigger_ids=[ids[0]])
    assert await source_cleanup.run_cleanup_pass() == 1
    assert ("POST", "/gmail/v1/users/me/stop") not in provider_http
    async with session_scope() as session:
        await delete_triggers(session, trigger_ids=[ids[1]])
    assert await source_cleanup.run_cleanup_pass() == 1
    assert provider_http.count(("POST", "/gmail/v1/users/me/stop")) == 1


@pytest.mark.usefixtures("client")
async def test_heartbeat_keeps_long_work_owned():
    name = f"long-work-{uuid4()}"
    async with session_scope() as session:
        assert await leases.acquire(session, name=name, owner="first", ttl_s=0.9)
    task = asyncio.create_task(run_guarded(asyncio.sleep(2), name=name, owner="first", ttl_s=0.9))
    await asyncio.sleep(1.3)
    async with session_scope() as session:
        assert not await leases.acquire(session, name=name, owner="second", ttl_s=10)
    await task


@pytest.mark.usefixtures("client")
async def test_lost_lease_cancels_inflight_work():
    name = f"lost-work-{uuid4()}"
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def work():
        started.set()
        try:
            await asyncio.sleep(30)
        finally:
            cancelled.set()

    async with session_scope() as session:
        assert await leases.acquire(session, name=name, owner="first", ttl_s=0.9)
    task = asyncio.create_task(run_guarded(work(), name=name, owner="first", ttl_s=0.9))
    await started.wait()
    async with session_scope() as session:
        await session.exec(update(TriggerLease).where(TriggerLease.name == name).values(owner="replacement"))
    with pytest.raises(LeaseLostError):
        await asyncio.wait_for(task, timeout=5)
    assert cancelled.is_set()


async def test_expired_watch_recovers_without_a_live_hint(make_trigger, source_connection, provider_http):
    from langflow.services.triggers.dispatcher import reconcile_push_sources

    trigger_id = await make_trigger(
        kind="microsoft.mail",
        provider="microsoft",
        connection_id=source_connection,
        config={"mechanism_id": "microsoft.graph_change_notifications"},
    )
    async with session_scope() as session:
        session.add(
            TriggerSubscription(
                trigger_id=trigger_id,
                connection_id=source_connection,
                provider="microsoft",
                provider_subscription_id="removed",
                state="expired",
            )
        )
    assert await reconcile_push_sources() == 1
    async with session_scope() as session:
        watches = (
            await session.exec(
                select(TriggerSubscription).where(
                    TriggerSubscription.trigger_id == trigger_id, TriggerSubscription.state == "active"
                )
            )
        ).all()
        assert len(watches) == 1
        assert watches[0].provider_subscription_id != "removed"
    assert provider_http.count(("POST", "/v1.0/subscriptions")) == 1


async def test_slow_source_maintenance_does_not_block_unrelated_dispatch(
    make_trigger, fake_background_service, monkeypatch
):
    from langflow.services.triggers import dispatcher, ledger

    trigger_id = await make_trigger()
    async with session_scope() as session:
        await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="ordinary")
    started, release = asyncio.Event(), asyncio.Event()

    async def slow_sources():
        started.set()
        await release.wait()
        return 0

    monkeypatch.setattr(dispatcher, "reconcile_push_sources", slow_sources)
    worker = dispatcher.TriggerDispatcher()
    maintenance = asyncio.create_task(worker.source_tick())
    try:
        await asyncio.wait_for(started.wait(), timeout=10)
        assert await asyncio.wait_for(worker.tick(), timeout=5) == 1
        assert len(fake_background_service.submits) == 1
        assert not maintenance.done()
    finally:
        release.set()
        await maintenance
        await worker.stop()


async def test_pending_source_events_wait_for_activation(make_trigger):
    from langflow.services.triggers import dispatcher, ledger

    trigger_id = await make_trigger(kind="microsoft.mail", provider="microsoft", state="pending")
    async with session_scope() as session:
        await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="early", payload={"_source_hint": True})
    async with session_scope() as session:
        assert await dispatcher.claim_batch(session, owner="worker", limit=25, lease_ttl_s=30) == []
        trigger = await session.get(Trigger, trigger_id)
        trigger.state = "active"
        session.add(trigger)
    async with session_scope() as session:
        assert (
            await dispatcher.claim_batch(session, owner="ordinary", limit=25, lease_ttl_s=30, source_hints=False) == []
        )
        assert (
            len(await dispatcher.claim_batch(session, owner="source", limit=25, lease_ttl_s=30, source_hints=True)) == 1
        )


@pytest.mark.parametrize("initialize", [False, True], ids=["provision", "activate"])
async def test_gmail_conflicting_topic_is_rejected_before_watch(
    make_trigger, source_connection, provider_http, initialize
):
    key = hashlib.sha256(b"fixture@example.test").hexdigest()
    async with session_scope() as session:
        connection = await session.get(Connection, source_connection)
        connection.provider_key = "google"
        connection.granted_scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
        session.add(connection)
    first = await make_trigger(kind="google.gmail", provider="google", connection_id=source_connection)
    second = await make_trigger(
        kind="google.gmail",
        provider="google",
        connection_id=source_connection,
        state="pending",
        config={"pubsub_topic": "projects/customer/topics/second"},
    )
    async with session_scope() as session:
        session.add(
            TriggerSubscription(
                trigger_id=first,
                connection_id=source_connection,
                provider="google",
                provider_subscription_id="first",
                state="active",
                provider_state={"mailbox_key": key, "pubsub_topic": "projects/customer/topics/first"},
            )
        )
    activate = source_runtime.initialize_source if initialize else source_runtime.ensure_subscription
    with pytest.raises(ValueError, match="same Pub/Sub topic"):
        await activate(second)
    if initialize:
        async with session_scope() as session:
            trigger = await session.get(Trigger, second)
            assert trigger.state == "error"
            assert "All Gmail triggers for one mailbox must use the same Pub/Sub topic." in trigger.last_error
    assert ("POST", "/gmail/v1/users/me/watch") not in provider_http


@pytest.mark.usefixtures("provider_http")
async def test_cleanup_retries_and_accepts_an_already_removed_watch(make_trigger, source_connection, monkeypatch):
    trigger_id = await make_trigger(kind="microsoft.mail", provider="microsoft", connection_id=source_connection)
    async with session_scope() as session:
        subscription = TriggerSubscription(
            trigger_id=trigger_id,
            connection_id=source_connection,
            provider="microsoft",
            provider_subscription_id="deleted-watch",
            state="active",
        )
        session.add(subscription)
        await session.flush()
        cleanup_id = subscription.id
        await delete_triggers(session, trigger_ids=[trigger_id])
    original = source_clients.SourceHTTP
    failures = [503, 404]

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, *_args, **_kwargs):
            httpx.Response(
                failures.pop(0),
                request=httpx.Request("DELETE", "https://graph.microsoft.com/v1.0/subscriptions/deleted-watch"),
            ).raise_for_status()

    monkeypatch.setattr(source_clients, "SourceHTTP", lambda *_args, **_kwargs: Client())
    assert await source_cleanup.run_cleanup_pass() == 0
    async with session_scope() as session:
        task = await session.get(TriggerCleanup, cleanup_id)
        assert task.attempt == 1
        task.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(task)
    assert await source_cleanup.run_cleanup_pass() == 1
    async with session_scope() as session:
        assert await session.get(TriggerCleanup, cleanup_id) is None
    monkeypatch.setattr(source_clients, "SourceHTTP", original)


@pytest.fixture
async def registered_source(source_connection, trigger_owner, monkeypatch):
    import json

    from langflow.services.database.models.connection.oauth import ConnectionOAuth
    from langflow.services.triggers import source_arming

    monkeypatch.setattr(source_arming, "deployment_context", lambda: "self_managed")
    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_enabled", True)
    monkeypatch.setenv(
        "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS",
        json.dumps(
            {
                "source-test": {
                    "provider": "microsoft",
                    "tenant": str(uuid4()),
                    "client_id": "fixture",
                    "client_secret": "fixture",  # pragma: allowlist secret - mock OAuth registration
                    "redirect_uri": "https://example.test/api/v1/connections/oauth/microsoft/callback",
                    "scopes": ["Mail.Read"],
                }
            }
        ),
    )
    async with session_scope() as session:
        connection = await session.get(Connection, source_connection)
        session.add(
            ConnectionOAuth(
                connection_id=source_connection,
                user_id=trigger_owner,
                registration_id="source-test",
                config_digest="d" * 64,
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
        )
        return f"microsoft/{connection.name}"


async def test_source_mode_can_choose_polling_with_ingress_enabled(registered_source, trigger_owner):
    from langflow.services.triggers.constants import MECHANISM_GRAPH_DELTA, MECHANISM_GRAPH_NOTIFICATIONS
    from langflow.services.triggers.source_arming import normalize_source_config, resolve_arming

    async with session_scope() as session:
        automatic = await resolve_arming(
            session, kind="microsoft.mail", owner_id=trigger_owner, config={"connection": registered_source}
        )
        polling = await resolve_arming(
            session,
            kind="microsoft.mail",
            owner_id=trigger_owner,
            config=normalize_source_config(
                "microsoft.mail", {"connection": registered_source, "delivery_mode": "poll"}
            ),
        )
    assert automatic.mechanism_id == MECHANISM_GRAPH_NOTIFICATIONS
    assert polling.mechanism_id == MECHANISM_GRAPH_DELTA


async def test_saved_source_exposes_ingress_before_enable_and_route_can_activate(
    registered_source, trigger_owner, owned_flow, provider_http
):
    from langflow.api.v1.triggers import enable_trigger, get_trigger_ingress
    from langflow.services.database.models.user.model import User, UserRead
    from langflow.services.triggers.reconciliation import reconcile_flow_triggers
    from langflow.services.triggers.service import TriggerService
    from starlette.requests import Request

    node = {
        "id": "MicrosoftOnMailTrigger-source",
        "data": {
            "type": "ext:microsoft:MicrosoftOnMailTriggerComponent@official",
            "node": {"template": {"connection": {"value": registered_source}}},
        },
    }
    async with session_scope() as session:
        await reconcile_flow_triggers(
            session, flow_id=owned_flow, owner_id=trigger_owner, flow_data={"nodes": [node], "edges": []}
        )
    async with session_scope() as session:
        row = (await session.exec(select(Trigger).where(Trigger.flow_id == owned_flow))).one()
        assert row.state == "pending"
        assert row.public_id
        trigger_id, public_id = row.id, row.public_id
        user = UserRead.model_validate(await session.get(User, trigger_owner))
        result = await get_trigger_ingress(
            trigger_id, Request({"type": "http", "headers": []}), session, user, TriggerService()
        )
        assert result.public_id == public_id
    async with session_scope() as session:
        enabled = await asyncio.wait_for(enable_trigger(trigger_id, session, user, TriggerService()), timeout=10)
        assert enabled.state == "active"
        assert (await session.get(Trigger, trigger_id)).public_id == public_id
    assert provider_http.count(("POST", "/v1.0/subscriptions")) == 1


@pytest.mark.usefixtures("client")
async def test_dispatcher_heartbeats_during_a_pass_longer_than_its_ttl(monkeypatch):
    from langflow.services.triggers import dispatcher

    monkeypatch.setattr(get_settings_service().settings, "trigger_lease_ttl_s", 0.9)
    started, finish = asyncio.Event(), asyncio.Event()
    entered = []

    async def slow_pass(*, owner, source_hints):
        assert source_hints is False
        entered.append(owner)
        started.set()
        await finish.wait()
        return 0

    monkeypatch.setattr(dispatcher, "run_once", slow_pass)
    first, second = dispatcher.TriggerDispatcher(), dispatcher.TriggerDispatcher()
    task = asyncio.create_task(first.tick())
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        await asyncio.sleep(1.3)
        assert await second.tick() == 0
        assert entered == [first.owner]
    finally:
        finish.set()
        await task
        await first.stop()
        await second.stop()


async def test_dead_replacement_hint_keeps_visible_error_and_periodic_repair(
    make_trigger, source_connection, provider_http, monkeypatch
):
    from langflow.services.database.models.trigger.model import TriggerEvent
    from langflow.services.triggers import dispatcher, ledger

    trigger_id = await make_trigger(
        kind="microsoft.mail",
        provider="microsoft",
        connection_id=source_connection,
        config={"mechanism_id": "microsoft.graph_change_notifications"},
        max_attempts=1,
    )
    async with session_scope() as session:
        session.add(
            TriggerSubscription(
                trigger_id=trigger_id,
                connection_id=source_connection,
                provider="microsoft",
                provider_subscription_id="removed",
                state="expired",
            )
        )
        event, _ = await ledger.append_event(
            session,
            trigger_id=trigger_id,
            dedupe_key="removed-hint",
            payload={"_source_hint": True, "delivery": {"lifecycleEvent": "subscriptionRemoved"}},
        )
        event_id = event.id
    original = source_runtime.reconcile_source

    async def unavailable(*_args, **_kwargs):
        msg = "Provider unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr(source_runtime, "reconcile_source", unavailable)
    await dispatcher.run_once(owner="failed-expansion", source_hints=True)
    async with session_scope() as session:
        assert (await session.get(TriggerEvent, event_id)).state == "dead"
        trigger = await session.get(Trigger, trigger_id)
        assert trigger.last_error == "Source reconciliation failed: RuntimeError"
        trigger.next_fire_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(trigger)
    monkeypatch.setattr(source_runtime, "reconcile_source", original)
    assert await dispatcher.reconcile_push_sources() == 1
    async with session_scope() as session:
        assert (await session.get(Trigger, trigger_id)).last_error is None
    assert provider_http.count(("POST", "/v1.0/subscriptions")) == 1


@pytest.mark.parametrize(
    ("provider", "kind", "scope"),
    [
        ("microsoft", "microsoft.mail", "Mail.Read"),
        ("google", "google.calendar", "https://www.googleapis.com/auth/calendar.events.readonly"),
    ],
)
async def test_renewal_resolves_credentials_without_holding_a_sqlite_writer(
    make_trigger, source_connection, provider_http, provider, kind, scope
):
    from langflow.services.triggers import subscriptions

    async with session_scope() as session:
        connection = await session.get(Connection, source_connection)
        connection.provider_key = provider
        connection.granted_scopes = [scope]
        session.add(connection)
    trigger_id = await make_trigger(kind=kind, provider=provider, connection_id=source_connection)
    async with session_scope() as session:
        subscription = TriggerSubscription(
            trigger_id=trigger_id,
            connection_id=source_connection,
            provider=provider,
            provider_subscription_id="old-watch",
            state="active",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            renew_after=datetime.now(timezone.utc) - timedelta(seconds=1),
            provider_state={"resource_id": "old-resource"},
        )
        session.add(subscription)
        await session.flush()
        subscription_id = subscription.id
    assert await asyncio.wait_for(subscriptions.run_renewal_pass(owner=f"renew-{uuid4()}"), timeout=10) == 1
    async with session_scope() as session:
        renewed = await session.get(TriggerSubscription, subscription_id)
        assert renewed.state == "active"
        assert renewed.lease_owner is None
        if provider == "google":
            cleanup = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger_id))).one()
            assert cleanup.provider_subscription_id == "old-watch"
            assert renewed.provider_subscription_id != "old-watch"
    assert provider_http


async def test_activation_cannot_publish_state_after_another_replica_takes_its_lease(make_trigger, monkeypatch):
    trigger_id = await make_trigger(kind="microsoft.mail", provider="microsoft", state="pending")
    name = f"trigger-source:{trigger_id}"

    async def take_over(_identifier):
        async with session_scope() as session:
            await session.exec(update(TriggerLease).where(TriggerLease.name == name).values(owner="replacement"))
        return 0

    async def no_watch(_identifier):
        return None

    monkeypatch.setattr(source_runtime, "sync_source", take_over)
    monkeypatch.setattr(source_runtime, "ensure_subscription", no_watch)
    with pytest.raises(ValueError, match="Source activation failed"):
        await source_runtime.initialize_source(trigger_id)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert trigger.state == "pending"
        assert trigger.last_error is None
        assert (await session.get(TriggerLease, name)).owner == "replacement"


@pytest.mark.parametrize("reason", ["credential-undecryptable", "registration-unavailable", None])
async def test_activation_error_preserves_safe_local_configuration_guidance(make_trigger, monkeypatch, reason):
    trigger_id = await make_trigger(kind="microsoft.mail", provider="microsoft", state="pending")
    failure = (
        ConnectionUnresolvedError("connection:microsoft/fixture-secret", provider="microsoft", reason=reason)
        if reason is not None
        else RuntimeError("Provider rejected fixture-secret")
    )

    async def unavailable(_identifier):
        raise failure

    monkeypatch.setattr(source_runtime, "sync_source", unavailable)
    with pytest.raises(ValueError, match="Source activation failed"):
        await source_runtime.initialize_source(trigger_id)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert trigger.state == "error"
        assert "fixture-secret" not in trigger.last_error
        if reason is None:
            assert trigger.last_error == "Source activation failed: RuntimeError. Enable the trigger to retry."
        else:
            assert reason in trigger.last_error
            assert "LANGFLOW_SECRET_KEY" in trigger.last_error
            assert "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS" in trigger.last_error


async def test_reconciliation_cannot_clear_error_after_another_replica_takes_its_lease(make_trigger, monkeypatch):
    trigger_id = await make_trigger(kind="microsoft.mail", provider="microsoft")
    name = f"trigger-source:{trigger_id}"
    error = "Source reconciliation failed: HTTPStatusError"
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        trigger.last_error = error
        session.add(trigger)

    async def take_over(_identifier):
        async with session_scope() as session:
            await session.exec(update(TriggerLease).where(TriggerLease.name == name).values(owner="replacement"))
        return 0

    monkeypatch.setattr(source_runtime, "sync_source", take_over)
    with pytest.raises(LeaseLostError, match="Source reconciliation lost its lease"):
        await source_runtime.reconcile_source(trigger_id)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert trigger.state == "active"
        assert trigger.last_error == error
        assert (await session.get(TriggerLease, name)).owner == "replacement"
