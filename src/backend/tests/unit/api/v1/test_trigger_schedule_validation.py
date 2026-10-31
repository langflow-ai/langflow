"""Schedule configuration is checked at every public write boundary."""

from datetime import datetime, timezone
from uuid import UUID

import pytest
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.deps import session_scope

from tests.unit.api.v1.test_triggers import _create, _payload

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("method", ["create", "patch"])
@pytest.mark.parametrize(
    "invalid",
    [
        {"timezone": 42},
        {"timezone": False},
        {"timezone": ""},
        {"timezone": None},
        {"cron": "* * * * * *"},
        {"cron": "0 0 31 2 *"},
        {"catchup_policy": "other"},
        {"catchup_policy": []},
        {"share_session": "false"},
    ],
)
async def test_api_rejects_invalid_schedule_config(client, logged_in_headers, flow, method, invalid):
    config = {"cron": "* * * * *", "timezone": "UTC", **invalid}
    if method == "create":
        response = await client.post(
            "api/v1/triggers", json=_payload(flow.id, config=config), headers=logged_in_headers
        )
    else:
        created = await _create(client, logged_in_headers, flow.id)
        url = f"api/v1/triggers/{created['id']}"
        response = await client.patch(url, json={"config": config}, headers=logged_in_headers)
        stored = await client.get(url, headers=logged_in_headers)
        assert stored.json() == created
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    ("change", "resets"),
    [
        ({"catchup_policy": "skip"}, False),
        ({"share_session": True}, False),
        ({"cron": "*/15 * * * *"}, True),
        ({"timezone": "UTC"}, True),
    ],
)
async def test_api_schedule_update_resets_only_a_changed_clock(client, logged_in_headers, flow, change, resets):
    created = await _create(client, logged_in_headers, flow.id)
    due = datetime(2026, 9, 14, 7, tzinfo=timezone.utc)
    async with session_scope() as session:
        trigger = await session.get(Trigger, UUID(created["id"]))
        trigger.next_fire_at = due
        session.add(trigger)
    response = await client.patch(
        f"api/v1/triggers/{created['id']}", json={"config": {**created["config"], **change}}, headers=logged_in_headers
    )
    assert response.status_code == 200, response.text
    if resets:
        assert response.json()["next_fire_at"] is None
    else:
        assert datetime.fromisoformat(response.json()["next_fire_at"]).replace(tzinfo=timezone.utc) == due


@pytest.mark.parametrize("state", ["active", "paused"])
async def test_enable_preserves_active_cursor_and_resets_paused_cursor(client, logged_in_headers, flow, state):
    created = await _create(client, logged_in_headers, flow.id)
    due = datetime(2026, 9, 14, 7, tzinfo=timezone.utc)
    async with session_scope() as session:
        trigger = await session.get(Trigger, UUID(created["id"]))
        trigger.state = state
        trigger.next_fire_at = due
        session.add(trigger)
    response = await client.post(f"api/v1/triggers/{created['id']}/enable", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "active"
    if state == "active":
        assert datetime.fromisoformat(response.json()["next_fire_at"]).replace(tzinfo=timezone.utc) == due
    else:
        assert response.json()["next_fire_at"] is None


async def test_api_schedule_fix_rearms_a_trigger_the_system_disabled(client, logged_in_headers, flow):
    """LE-2481, API path: a PATCH with a valid config clears the stale error."""
    created = await _create(client, logged_in_headers, flow.id)
    async with session_scope() as session:
        trigger = await session.get(Trigger, UUID(created["id"]))
        trigger.state = "error"
        trigger.last_error = "Invalid cron expression: a valid five-field cron expression is required."
        session.add(trigger)

    response = await client.patch(
        f"api/v1/triggers/{created['id']}",
        json={"config": {**created["config"], "cron": "* * * * *"}},
        headers=logged_in_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["state"], body["last_error"], body["next_fire_at"]) == ("active", None, None)


async def test_api_rename_does_not_rearm_a_trigger_in_error(client, logged_in_headers, flow):
    created = await _create(client, logged_in_headers, flow.id)
    async with session_scope() as session:
        trigger = await session.get(Trigger, UUID(created["id"]))
        trigger.state = "error"
        trigger.last_error = "boom"
        session.add(trigger)

    response = await client.patch(
        f"api/v1/triggers/{created['id']}", json={"name": "renamed"}, headers=logged_in_headers
    )

    assert response.status_code == 200, response.text
    assert (response.json()["state"], response.json()["last_error"]) == ("error", "boom")
