"""Validate pins and partial updates through every trigger write route."""

from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent, TriggerSubscription
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlmodel import select

from tests.unit.api.v1.test_triggers import _create, _payload

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("method", ["create", "patch", "pin"])
@pytest.mark.parametrize("version_kind", ["foreign", "missing"])
async def test_all_pin_writes_require_a_version_of_the_same_flow(client, logged_in_headers, flow, method, version_kind):
    version_id = uuid4()
    if version_kind == "foreign":
        async with session_scope() as session:
            other = User(username=f"pin-owner-{uuid4().hex}", password=str(uuid4()), is_active=True)
            session.add(other)
            await session.flush()
            other_flow = Flow(name="Private flow", user_id=other.id)
            session.add(other_flow)
            await session.flush()
            version = FlowVersion(flow_id=other_flow.id, user_id=other.id, version_number=1, data={"nodes": []})
            session.add(version)
            await session.flush()
            version_id = version.id
    if method == "create":
        response = await client.post(
            "api/v1/triggers",
            json=_payload(flow.id, flow_version_id=str(version_id)),
            headers=logged_in_headers,
        )
    else:
        created = await _create(client, logged_in_headers, flow.id)
        url = f"api/v1/triggers/{created['id']}"
        request = client.patch if method == "patch" else client.post
        response = await request(
            url if method == "patch" else f"{url}/pin",
            json={"flow_version_id": str(version_id)},
            headers=logged_in_headers,
        )
        stored = await client.get(url, headers=logged_in_headers)
        assert stored.json()["flow_version_id"] is None
    assert response.status_code == 404, response.text


@pytest.mark.parametrize(
    "field", ["name", "config", "binding_target", "session_policy", "concurrency_limit", "max_attempts"]
)
async def test_patch_rejects_null_required_fields(client, logged_in_headers, flow, field):
    created = await _create(client, logged_in_headers, flow.id)
    url = f"api/v1/triggers/{created['id']}"
    response = await client.patch(url, json={field: None}, headers=logged_in_headers)
    assert response.status_code == 422, response.text
    stored = await client.get(url, headers=logged_in_headers)
    assert stored.json() == created


async def test_create_patch_and_unpin_accept_valid_versions(client, logged_in_headers, flow):
    async with session_scope() as session:
        version = FlowVersion(flow_id=flow.id, user_id=flow.user_id, version_number=1, data={"nodes": []})
        session.add(version)
        await session.flush()
        version_id = str(version.id)
    created = await _create(client, logged_in_headers, flow.id, flow_version_id=version_id)
    url = f"api/v1/triggers/{created['id']}"
    unchanged = await client.patch(url, json={}, headers=logged_in_headers)
    assert unchanged.status_code == 200
    assert unchanged.json()["flow_version_id"] == version_id
    cleared = await client.patch(
        url,
        json={"flow_version_id": None, "connection_id": None, "deployment_id": None},
        headers=logged_in_headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["flow_version_id"] is None
    pinned = await client.patch(url, json={"flow_version_id": version_id}, headers=logged_in_headers)
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["flow_version_id"] == version_id
    deleted = await client.delete(f"api/v1/flows/{flow.id}/versions/{version_id}", headers=logged_in_headers)
    assert deleted.status_code == 409, deleted.text
    await client.post(f"{url}/pin", json={"flow_version_id": None}, headers=logged_in_headers)
    deleted = await client.delete(f"api/v1/flows/{flow.id}/versions/{version_id}", headers=logged_in_headers)
    assert deleted.status_code == 204, deleted.text


async def test_user_deletion_removes_owned_trigger_history(client, logged_in_headers_super_user):
    async with session_scope() as session:
        owner = User(username=f"deleted-owner-{uuid4().hex}", password=str(uuid4()), is_active=True)
        session.add(owner)
        await session.flush()
        flow = Flow(name="Deleted owner's flow", user_id=owner.id)
        session.add(flow)
        await session.flush()
        trigger = Trigger(flow_id=flow.id, user_id=owner.id, name="Delete", kind="schedule")
        session.add(trigger)
        await session.flush()
        session.add(TriggerEvent(trigger_id=trigger.id, dedupe_key="retained-payload", payload={"private": "data"}))
        session.add(TriggerSubscription(trigger_id=trigger.id, provider="test", provider_subscription_id=uuid4().hex))
        owner_id, trigger_id = owner.id, trigger.id
    response = await client.delete(f"api/v1/users/{owner_id}", headers=logged_in_headers_super_user)
    assert response.status_code == 200, response.text
    async with session_scope() as session:
        assert await session.get(Trigger, trigger_id) is None
        assert not (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
        assert not (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == trigger_id))
        ).all()
