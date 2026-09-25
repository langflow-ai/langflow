"""Provider watch requests match the resource's subscription contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.database.models.trigger.schemas import TriggerSubscriptionState
from langflow.services.deps import session_scope
from langflow.services.triggers import source_subscription, subscriptions


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
