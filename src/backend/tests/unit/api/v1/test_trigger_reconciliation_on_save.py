"""Saving a flow with a trigger node produces a trigger, on every save path.

The three flow-save paths (POST create, PUT update, PATCH) each call the
reconciler. The ``webhook`` flag recompute is a cautionary tale here: it lives
in two of the three, so a flow created with a webhook node was not marked as
one. These tests pin all three.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster


def _schedule_node(node_id: str = "ScheduleTrigger-abc123", cron: str = "0 8 * * 1-5") -> dict[str, Any]:
    return {
        "id": node_id,
        "data": {
            "type": "ScheduleTrigger",
            "node": {
                "template": {
                    "cron_expression": {"value": cron},
                    "timezone": {"value": "Europe/Lisbon"},
                    "catchup_policy": {"value": "coalesce"},
                    "share_session": {"value": False},
                }
            },
        },
    }


def _flow_body(name: str, *nodes) -> dict[str, Any]:
    return {"name": name, "description": "trigger reconciliation", "data": {"nodes": list(nodes), "edges": []}}


async def _triggers(client: AsyncClient, headers: dict[str, str], flow_id: str) -> list[dict]:
    response = await client.get(f"api/v1/triggers?flow_id={flow_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_creating_a_flow_with_a_schedule_node_creates_a_pending_trigger(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    created = await client.post(
        "api/v1/flows/", json=_flow_body("digest flow", _schedule_node()), headers=logged_in_headers
    )
    assert created.status_code == 201, created.text
    flow_id = created.json()["id"]

    triggers = await _triggers(client, logged_in_headers, flow_id)
    assert len(triggers) == 1
    assert triggers[0]["kind"] == "schedule"
    assert triggers[0]["state"] == "pending"
    assert triggers[0]["node_id"] == "ScheduleTrigger-abc123"
    assert triggers[0]["config"]["cron"] == "0 8 * * 1-5"


async def test_patching_the_flow_updates_the_schedule_and_removing_it_pauses_the_trigger(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    created = await client.post(
        "api/v1/flows/", json=_flow_body("editable flow", _schedule_node()), headers=logged_in_headers
    )
    assert created.status_code == 201, created.text
    flow_id = created.json()["id"]

    patched = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"data": {"nodes": [_schedule_node(cron="*/15 * * * *")], "edges": []}},
        headers=logged_in_headers,
    )
    assert patched.status_code == 200, patched.text
    triggers = await _triggers(client, logged_in_headers, flow_id)
    assert len(triggers) == 1
    assert triggers[0]["config"]["cron"] == "*/15 * * * *"

    removed = await client.patch(
        f"api/v1/flows/{flow_id}", json={"data": {"nodes": [], "edges": []}}, headers=logged_in_headers
    )
    assert removed.status_code == 200, removed.text
    triggers = await _triggers(client, logged_in_headers, flow_id)
    assert len(triggers) == 1
    assert triggers[0]["state"] == "paused"


async def test_a_flow_without_trigger_nodes_gets_no_triggers(
    client: AsyncClient,
    logged_in_headers: dict[str, str],
) -> None:
    created = await client.post("api/v1/flows/", json=_flow_body("plain flow"), headers=logged_in_headers)
    assert created.status_code == 201, created.text
    assert await _triggers(client, logged_in_headers, created.json()["id"]) == []
