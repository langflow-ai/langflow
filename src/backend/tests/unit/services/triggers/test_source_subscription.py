"""Provider watch requests match the resource's subscription contract."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerSubscription
from langflow.services.triggers import source_subscription


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
        return object()

    trigger = Trigger(id=uuid4(), flow_id=uuid4(), user_id=uuid4(), name="source", kind=kind, provider="google")
    subscription = TriggerSubscription(
        trigger_id=trigger.id,
        provider="google",
        provider_subscription_id="channel-1",
        provider_state={"resource_id": "resource-1"},
    )
    monkeypatch.setattr(source_subscription, "SourceHTTP", lambda *_args, **_kwargs: Client())
    monkeypatch.setattr(source_subscription, "source_lease", lease)
    await source_subscription.revoke_source(Session(), subscription)
    assert paths == [("POST", expected_path, {"id": "channel-1", "resourceId": "resource-1"})]
