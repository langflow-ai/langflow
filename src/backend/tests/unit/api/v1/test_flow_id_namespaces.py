"""Persisted flow IDs must not claim a public execution's history namespace."""

import io
import json
import zipfile
from uuid import UUID, uuid4

import pytest
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.deps import session_scope


async def _create_with_id(client, headers, flow_id, entry_point):
    payload = {"id": str(flow_id), "name": "Imported flow", "data": {"nodes": [], "edges": []}}
    if entry_point == "post":
        return await client.post("api/v1/flows/", json=payload, headers=headers)
    if entry_point == "put":
        payload.pop("id")  # The path ID also needs protection.
        return await client.put(f"api/v1/flows/{flow_id}", json=payload, headers=headers)
    if entry_point == "batch":
        return await client.post("api/v1/flows/batch/", json={"flows": [payload]}, headers=headers)
    contents = json.dumps(
        {"folder_name": "Imported project", "flows": [payload]} if entry_point == "project-json" else payload
    ).encode()
    filename = "flow.json"
    if entry_point in ("zip", "project-zip"):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr(filename, contents)
        filename, contents = "flows.zip", archive.getvalue()
    endpoint = "projects" if entry_point.startswith("project-") else "flows"
    return await client.post(f"api/v1/{endpoint}/upload/", files={"file": (filename, contents)}, headers=headers)


@pytest.mark.parametrize("entry_point", ["post", "put", "batch", "json", "zip", "project-json", "project-zip"])
async def test_cannot_create_flow_at_another_users_virtual_history(client, logged_in_headers, entry_point):
    virtual_id = compute_virtual_flow_id(uuid4(), uuid4(), principal_type="user")
    async with session_scope() as session:
        message = MessageTable(
            flow_id=virtual_id,
            session_id="victim-session",
            sender="User",
            sender_name="User",
            text="private history",
            properties={},
        )
        transaction = TransactionTable(flow_id=virtual_id, vertex_id="node", status="success")
        session.add_all([message, transaction])
        await session.commit()
        message_id, transaction_id = message.id, transaction.id

    response = await _create_with_id(client, logged_in_headers, virtual_id, entry_point)

    assert response.status_code == 400, response.text
    assert "reserved" in response.json()["detail"].lower()
    async with session_scope() as session:
        assert await session.get(Flow, virtual_id) is None
        assert await session.get(MessageTable, message_id) is not None
        assert await session.get(TransactionTable, transaction_id) is not None
    for endpoint in ("messages", "transactions"):
        monitor = await client.get(
            f"api/v1/monitor/{endpoint}", params={"flow_id": str(virtual_id)}, headers=logged_in_headers
        )
        assert monitor.status_code == 200
        result = monitor.json()
        assert (result["items"] if isinstance(result, dict) else result) == []
    deleted = await client.delete(f"api/v1/flows/{virtual_id}", headers=logged_in_headers)
    assert deleted.status_code == 404


@pytest.mark.parametrize("entry_point", ["post", "put", "batch", "json", "zip", "project-json", "project-zip"])
async def test_stable_imported_flow_id_is_preserved(client, logged_in_headers, entry_point):
    flow_id = uuid4()
    response = await _create_with_id(client, logged_in_headers, flow_id, entry_point)
    assert response.status_code in (200, 201), response.text
    payload = response.json()
    if isinstance(payload, dict) and "flows" in payload:
        payload = payload["flows"]
    if isinstance(payload, list):
        payload = payload[0]
    assert UUID(payload["id"]) == flow_id


async def test_existing_uuid5_flow_can_still_be_updated(client, logged_in_headers, active_user):
    flow_id = compute_virtual_flow_id(uuid4(), uuid4(), principal_type="client")
    async with session_scope() as session:
        session.add(
            Flow(id=flow_id, user_id=active_user.id, name="Legacy imported flow", data={"nodes": [], "edges": []})
        )
        await session.commit()
    response = await client.put(
        f"api/v1/flows/{flow_id}", json={"name": "Updated legacy flow"}, headers=logged_in_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Updated legacy flow"


async def test_preexisting_uuid5_flow_does_not_authorize_virtual_history(client, logged_in_headers, active_user):
    flow_id = compute_virtual_flow_id(uuid4(), uuid4(), principal_type="user")
    async with session_scope() as session:
        session.add(Flow(id=flow_id, user_id=active_user.id, name="Existing collision", data={}))
        message = MessageTable(
            flow_id=flow_id,
            session_id="victim-session",
            sender="User",
            sender_name="User",
            text="private history",
            properties={},
        )
        session.add(message)
        transaction = TransactionTable(flow_id=flow_id, vertex_id="node", status="success")
        session.add(transaction)
        await session.commit()
        message_id, transaction_id = message.id, transaction.id

    for params in ({"flow_id": str(flow_id)}, {}):
        response = await client.get("api/v1/monitor/messages", params=params, headers=logged_in_headers)
        assert response.status_code == 200, response.text
        assert all(item["text"] != "private history" for item in response.json())
    response = await client.get(
        "api/v1/monitor/transactions", params={"flow_id": str(flow_id)}, headers=logged_in_headers
    )
    assert response.json()["items"] == []
    response = await client.put(
        f"api/v1/monitor/messages/{message_id}", json={"text": "changed"}, headers=logged_in_headers
    )
    assert response.status_code == 404
    await client.request("DELETE", "api/v1/monitor/messages", json=[str(message_id)], headers=logged_in_headers)
    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert response.status_code == 200
    async with session_scope() as session:
        assert await session.get(Flow, flow_id) is None
        assert (await session.get(MessageTable, message_id)).text == "private history"
        assert await session.get(TransactionTable, transaction_id) is not None
