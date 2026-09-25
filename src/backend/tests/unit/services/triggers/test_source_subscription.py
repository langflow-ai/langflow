"""Provider watch requests match the resource's subscription contract."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerSubscriptionState
from langflow.services.deps import session_scope
from langflow.services.triggers import source_subscription, subscriptions
from langflow.services.triggers.source_clients import SourceHTTP


async def test_graph_drive_subscription_uses_updated_only(monkeypatch) -> None:
    requests = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, method, path, *, body=None):
            requests.append((method, path, body))
            return {"id": "sub-1", "expirationDateTime": datetime.now(timezone.utc).isoformat()}

    async def lease(_session, _trigger, *, family):
        assert family == "trigger_push"
        return object()

    async def upsert(_session, **fields):
        return fields

    monkeypatch.setattr(source_subscription, "SourceHTTP", lambda *_args, **_kwargs: Client())
    monkeypatch.setattr(source_subscription, "source_lease", lease)
    monkeypatch.setattr(source_subscription, "upsert_subscription", upsert)

    trigger = Trigger(
        id=uuid4(),
        flow_id=uuid4(),
        user_id=uuid4(),
        name="drive",
        kind="microsoft.file",
        provider="microsoft",
        connection_id=uuid4(),
        config={},
    )
    result = await source_subscription._graph_create(object(), trigger, "https://example.com/ingress")
    assert result["provider_subscription_id"] == "sub-1"
    assert requests[0][0:2] == ("POST", "v1.0/subscriptions")
    assert requests[0][2]["resource"] == "me/drive/root"
    assert requests[0][2]["changeType"] == "updated"


async def test_graph_renewal_patches_the_existing_subscription(monkeypatch) -> None:
    requests = []
    provider_expiry = datetime.now(timezone.utc) + timedelta(hours=24)

    class Lease:
        async def get_token(self):
            return "test-token"

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"expirationDateTime": provider_expiry.isoformat()})

    async def lease(_session, _trigger, *, family):
        assert family == "trigger_push"
        return Lease()

    trigger = Trigger(id=uuid4(), flow_id=uuid4(), user_id=uuid4(), name="calendar", kind="microsoft.calendar")
    subscription = TriggerSubscription(
        trigger_id=trigger.id, provider="microsoft", provider_subscription_id="subscription-1"
    )

    class Session:
        async def get(self, _model, _identifier):
            return trigger

    monkeypatch.setattr(source_subscription, "source_lease", lease)
    monkeypatch.setattr(
        source_subscription,
        "SourceHTTP",
        lambda credential, *, origin: SourceHTTP(credential, origin=origin, transport=httpx.MockTransport(reply)),
    )
    renewed_until = await source_subscription.renew_source(Session(), subscription)

    assert renewed_until == provider_expiry
    assert requests[0][:2] == ("PATCH", "/v1.0/subscriptions/subscription-1")
    assert datetime.fromisoformat(requests[0][2]["expirationDateTime"]) > datetime.now(timezone.utc)


@pytest.mark.parametrize(
    ("kind", "expected_path"),
    [
        ("google.calendar", "/calendar/v3/calendars/primary/events/watch"),
        ("google.drive", "/drive/v3/changes/watch"),
    ],
)
async def test_google_watch_creates_a_verified_channel(kind, expected_path, monkeypatch) -> None:
    requests = []
    expiry_ms = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp() * 1000)

    class Lease:
        async def get_token(self):
            return "test-token"

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path, dict(request.url.params), json.loads(request.content)))
        return httpx.Response(200, json={"resourceId": "resource-1", "expiration": str(expiry_ms)})

    async def lease(_session, _trigger, *, family):
        assert family == "trigger_push"
        return Lease()

    trigger = Trigger(
        id=uuid4(),
        flow_id=uuid4(),
        user_id=uuid4(),
        name="source",
        kind=kind,
        provider="google",
        config={"calendar_id": "primary"},
        provider_state={"page_token": "start"},
    )
    monkeypatch.setattr(source_subscription, "source_lease", lease)
    monkeypatch.setattr(
        source_subscription,
        "SourceHTTP",
        lambda credential, *, origin: SourceHTTP(credential, origin=origin, transport=httpx.MockTransport(reply)),
    )
    channel_id, token, state, expires_at = await source_subscription._google_watch(
        object(), trigger, "https://example.com/ingress"
    )

    assert requests[0][:2] == ("POST", expected_path)
    assert requests[0][3]["id"] == channel_id
    assert requests[0][3]["address"] == "https://example.com/ingress"
    assert requests[0][3]["token"] == token
    assert state == {"channel_id": channel_id, "resource_id": "resource-1"}
    assert expires_at == datetime.fromtimestamp(expiry_ms / 1000, tz=timezone.utc)
    if kind == "google.drive":
        assert requests[0][2]["pageToken"] == "start"


@pytest.mark.parametrize(
    ("kind", "expected_path"),
    [
        ("google.calendar", "calendar/v3/channels/stop"),
        ("google.drive", "drive/v3/channels/stop"),
    ],
)
async def test_google_channel_stop_uses_its_own_api(kind, expected_path, monkeypatch) -> None:
    paths = []
    old_connection_id = uuid4()

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, method, path, *, body=None):
            paths.append((method, path, body))
            return {}

    class Session:
        async def get(self, _model, _identifier):
            return trigger

    async def lease(_session, _trigger, *, family):
        assert family == "trigger_push"
        assert _trigger.connection_id == old_connection_id
        return object()

    trigger = Trigger(
        id=uuid4(), flow_id=uuid4(), user_id=uuid4(), name="source", kind=kind, provider="google", connection_id=uuid4()
    )
    subscription = TriggerSubscription(
        trigger_id=trigger.id,
        connection_id=old_connection_id,
        provider="google",
        provider_subscription_id="channel-1",
        provider_state={"resource_id": "resource-1"},
    )
    monkeypatch.setattr(source_subscription, "SourceHTTP", lambda *_args, **_kwargs: Client())
    monkeypatch.setattr(source_subscription, "source_lease", lease)
    await source_subscription.revoke_source(Session(), subscription)
    assert paths == [("POST", expected_path, {"id": "channel-1", "resourceId": "resource-1"})]


async def test_connection_change_retires_old_watch_before_provisioning_new_one(
    make_trigger, trigger_owner, monkeypatch
) -> None:
    async with session_scope() as session:
        old_connection = Connection(
            provider_key="microsoft", name="old", display_name="Old", owner_id=trigger_owner, status="ready"
        )
        new_connection = Connection(
            provider_key="microsoft", name="new", display_name="New", owner_id=trigger_owner, status="ready"
        )
        session.add_all([old_connection, new_connection])
        await session.flush()
        old_connection_id, new_connection_id = old_connection.id, new_connection.id

    trigger_id = await make_trigger(kind="microsoft.calendar", provider="microsoft", connection_id=old_connection_id)
    expiry = datetime.now(timezone.utc) + timedelta(days=1)
    async with session_scope() as session:
        old_subscription = await subscriptions.upsert_subscription(
            session,
            trigger_id=trigger_id,
            connection_id=old_connection_id,
            provider="microsoft",
            provider_subscription_id=f"old-{uuid4()}",
            client_state_digest=None,
            expires_at=expiry,
        )
        old_subscription_id = old_subscription.id
        trigger = await session.get(Trigger, trigger_id)
        trigger.connection_id = new_connection_id
        session.add(trigger)

    revoked = []

    async def fake_revoke(_session, subscription):
        revoked.append(subscription.id)

    async def fake_ingress(_session, _trigger):
        return "https://example.com/ingress"

    async def fake_create(session, trigger, _address):
        return await subscriptions.upsert_subscription(
            session,
            trigger_id=trigger.id,
            connection_id=trigger.connection_id,
            provider="microsoft",
            provider_subscription_id=f"new-{uuid4()}",
            client_state_digest=None,
            expires_at=expiry,
        )

    monkeypatch.setattr(subscriptions, "_revoke_remote", fake_revoke)
    monkeypatch.setattr(source_subscription, "source_ingress_url", fake_ingress)
    monkeypatch.setattr(source_subscription, "_graph_create", fake_create)
    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        new_subscription = await source_subscription.provision_source(session, trigger)
        new_subscription_id = new_subscription.id

    async with session_scope() as session:
        old_subscription = await session.get(TriggerSubscription, old_subscription_id)
        new_subscription = await session.get(TriggerSubscription, new_subscription_id)
        assert old_subscription.state == TriggerSubscriptionState.EXPIRED.value
        assert old_subscription.renew_after is None
        assert new_subscription.state == TriggerSubscriptionState.ACTIVE.value
        assert new_subscription.connection_id == new_connection_id
    assert revoked == [old_subscription_id]
