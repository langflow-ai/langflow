"""Flow writes reject extra canvas triggers without discarding graph content."""

from __future__ import annotations

import io
import json
import zipfile
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow, FlowCreate, FlowUpdate
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.deps import session_scope
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from sqlmodel import col, select

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster


def _schedule_node(node_id: str) -> dict:
    return {
        "id": node_id,
        "data": {
            "type": "ScheduleTrigger",
            "node": {
                "template": {
                    "cron_expression": {"value": "0 8 * * 1-5"},
                    "timezone": {"value": "UTC"},
                },
            },
        },
    }


def _graph(*nodes: dict) -> dict:
    return {"nodes": list(nodes), "edges": []}


def _payload(*nodes: dict) -> dict:
    return {"name": f"trigger-constraint-{uuid4().hex}", "data": _graph(*nodes)}


@pytest.mark.parametrize(
    "second_node",
    [
        _schedule_node("schedule-b"),
        {"id": "webhook-b", "data": {"type": "InboundWebhookTrigger"}},
        {"id": "slack-b", "data": {"type": "ext:slack:SlackOnMessageTriggerComponent@official"}},
    ],
    ids=["same-kind", "different-core-kind", "provider-kind"],
)
async def test_create_rejects_multiple_triggers_before_saving(
    client: AsyncClient, logged_in_headers: dict[str, str], second_node: dict
) -> None:
    payload = _payload(_schedule_node("schedule-a"), second_node)
    response = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)

    assert response.status_code == 422, response.text
    assert "only one trigger" in response.text
    async with session_scope() as session:
        assert (await session.exec(select(Flow).where(Flow.name == payload["name"]))).first() is None


@pytest.mark.parametrize("method", ["patch", "put"])
async def test_update_rejects_multiple_triggers_without_changing_the_flow(
    client: AsyncClient, logged_in_headers: dict[str, str], method: str
) -> None:
    payload = _payload(_schedule_node("schedule-a"))
    created = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert created.status_code == 201, created.text
    flow_id = created.json()["id"]

    response = await client.request(
        method,
        f"api/v1/flows/{flow_id}",
        json={**payload, "data": _graph(_schedule_node("schedule-a"), _schedule_node("schedule-b"))},
        headers=logged_in_headers,
    )

    assert response.status_code == 422, response.text
    assert "only one trigger" in response.text
    fetched = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["data"] == payload["data"]


@pytest.mark.parametrize("file_type", ["json", "zip", "batch", "project"])
async def test_import_rejects_multiple_triggers_before_saving_any_flows(
    client: AsyncClient, logged_in_headers: dict[str, str], file_type: str
) -> None:
    valid = _payload(_schedule_node("schedule-a"))
    invalid = _payload(_schedule_node("schedule-a"), _schedule_node("schedule-b"))
    if file_type == "batch":
        response = await client.post("api/v1/flows/batch/", json={"flows": [valid, invalid]}, headers=logged_in_headers)
    else:
        if file_type == "zip":
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("valid.json", json.dumps(valid))
                output.writestr("invalid.json", json.dumps(invalid))
            contents = archive.getvalue()
            content_type = "application/zip"
        else:
            body = {"flows": [valid, invalid]}
            if file_type == "project":
                body["folder_name"] = valid["name"]
            contents = json.dumps(body).encode()
            content_type = "application/json"
        response = await client.post(
            "api/v1/projects/upload/" if file_type == "project" else "api/v1/flows/upload/",
            files={"file": (f"flows.{file_type}", contents, content_type)},
            headers=logged_in_headers,
        )

    assert response.status_code == 422, response.text
    assert "only one trigger" in response.text
    async with session_scope() as session:
        assert not (await session.exec(select(Flow).where(col(Flow.name).in_([valid["name"], invalid["name"]])))).all()
        if file_type == "project":
            assert (await session.exec(select(Folder).where(Folder.name == valid["name"]))).first() is None


async def test_legacy_multiple_triggers_can_be_read_and_repaired_before_enabling(
    client: AsyncClient, logged_in_headers: dict[str, str], active_user
) -> None:
    first_node = _schedule_node("schedule-a")
    async with session_scope() as session:
        flow = Flow(**_payload(first_node, _schedule_node("schedule-b")), user_id=active_user.id)
        session.add(flow)
        await session.flush()
        flow_id = flow.id
        await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=active_user.id, flow_data=flow.data)
        trigger = (
            await session.exec(select(Trigger).where(Trigger.flow_id == flow_id, Trigger.node_id == first_node["id"]))
        ).one()
        trigger_id = trigger.id

    fetched = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert fetched.status_code == 200, fetched.text
    assert len(fetched.json()["data"]["nodes"]) == 2

    metadata_update = await client.patch(
        f"api/v1/flows/{flow_id}", json={"description": "Ready to repair"}, headers=logged_in_headers
    )
    assert metadata_update.status_code == 200, metadata_update.text

    active_create = await client.post(
        "api/v1/triggers",
        json={
            "flow_id": str(flow_id),
            "name": "API schedule on legacy graph",
            "kind": "schedule",
            "config": {"cron": "0 8 * * 1-5", "timezone": "UTC"},
            "state": "active",
        },
        headers=logged_in_headers,
    )
    assert active_create.status_code == 422, active_create.text
    assert "only one trigger" in active_create.text

    rejected = await client.post(f"api/v1/triggers/{trigger_id}/enable", headers=logged_in_headers)
    assert rejected.status_code == 409, rejected.text
    assert "only one trigger" in rejected.text
    async with session_scope() as session:
        assert (await session.get(Trigger, trigger_id)).state == "pending"
        assert len((await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).all()) == 2

    repaired = await client.patch(
        f"api/v1/flows/{flow_id}", json={"data": _graph(first_node)}, headers=logged_in_headers
    )
    assert repaired.status_code == 200, repaired.text
    enabled = await client.post(f"api/v1/triggers/{trigger_id}/enable", headers=logged_in_headers)
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["state"] == "active"


async def test_node_less_schedule_api_remains_supported(
    client: AsyncClient, logged_in_headers: dict[str, str], flow
) -> None:
    for name in ("first API schedule", "second API schedule"):
        created = await client.post(
            "api/v1/triggers",
            json={
                "flow_id": str(flow.id),
                "name": name,
                "kind": "schedule",
                "config": {"cron": "0 8 * * 1-5", "timezone": "UTC"},
            },
            headers=logged_in_headers,
        )
        assert created.status_code == 201, created.text
        assert created.json()["node_id"] is None
        enabled = await client.post(f"api/v1/triggers/{created.json()['id']}/enable", headers=logged_in_headers)
        assert enabled.status_code == 200, enabled.text
        assert enabled.json()["state"] == "active"


@pytest.mark.parametrize("action", ["flow-metadata", "schedule-config"])
async def test_legacy_multiple_triggers_cannot_reactivate_implicitly(
    client: AsyncClient, logged_in_headers: dict[str, str], active_user, action: str
) -> None:
    async with session_scope() as session:
        flow = Flow(**_payload(_schedule_node("schedule-a"), _schedule_node("schedule-b")), user_id=active_user.id)
        session.add(flow)
        await session.flush()
        flow_id = flow.id
        await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=active_user.id, flow_data=flow.data)
        trigger = (
            await session.exec(select(Trigger).where(Trigger.flow_id == flow_id, Trigger.node_id == "schedule-a"))
        ).one()
        trigger.state = "error"
        trigger.last_error = "The schedule could not run."
        session.add(trigger)
        trigger_id = trigger.id
        original_config = dict(trigger.config)

    if action == "flow-metadata":
        response = await client.patch(
            f"api/v1/flows/{flow_id}", json={"description": "Ready to repair"}, headers=logged_in_headers
        )
        assert response.status_code == 200, response.text
    else:
        response = await client.patch(
            f"api/v1/triggers/{trigger_id}",
            json={"config": {"cron": "0 9 * * 1-5", "timezone": "UTC"}},
            headers=logged_in_headers,
        )
        assert response.status_code == 422, response.text
        assert "only one trigger" in response.text

    async with session_scope() as session:
        trigger = await session.get(Trigger, trigger_id)
        assert trigger.state == "error"
        assert trigger.config == original_config


@pytest.mark.parametrize("model", [FlowCreate, FlowUpdate])
def test_trigger_validation_tolerates_unrelated_malformed_nodes(model) -> None:
    graph = _graph(None, {"data": None}, {"data": []}, _schedule_node("schedule-a"))
    flow = model(name="tolerant trigger count", data=graph)

    assert flow.data == graph
