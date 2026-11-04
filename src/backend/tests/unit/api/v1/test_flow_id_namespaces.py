"""Persisted flow IDs must not claim a public execution's history namespace."""

import io
import json
import zipfile
from uuid import UUID, uuid4

import pytest
from langflow.api.utils.flow_utils import cascade_delete_flow, compute_virtual_flow_id
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


@pytest.fixture
def project_delete_foreign_keys(client):  # noqa: ARG001
    from langflow.services.deps import get_db_service
    from sqlalchemy import event

    engine = get_db_service().engine.sync_engine

    def enable_foreign_keys(connection, _record, _proxy):
        connection.execute("PRAGMA foreign_keys=ON")

    event.listen(engine, "checkout", enable_foreign_keys)
    try:
        yield
    finally:
        event.remove(engine, "checkout", enable_foreign_keys)


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
@pytest.mark.parametrize("collision_with_other_user", [False, True])
async def test_cannot_create_flow_with_a_user_storage_id(
    client, logged_in_headers, active_user, entry_point, collision_with_other_user
):
    """A new flow must not claim the legacy storage namespace of any user."""
    collision_id = active_user.id
    async with session_scope() as session:
        if collision_with_other_user:
            other_user = User(username=f"other-storage-user-{uuid4()}", password=uuid4().hex, is_active=True)
            session.add(other_user)
            await session.flush()
            collision_id = other_user.id

    response = await _create_with_id(client, logged_in_headers, collision_id, entry_point)

    assert response.status_code == 400, response.text
    assert "user id" in response.json()["detail"].lower()
    async with session_scope() as session:
        assert await session.get(Flow, collision_id) is None


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
    assert response.status_code == 400
    async with session_scope() as session:
        assert await session.get(Flow, flow_id) is not None
        assert (await session.get(MessageTable, message_id)).text == "private history"
        assert await session.get(TransactionTable, transaction_id) is not None


@pytest.mark.parametrize("different_owner", [False, True])
@pytest.mark.usefixtures("project_delete_foreign_keys")
async def test_project_delete_with_reserved_flow_returns_400_and_keeps_rows(
    client, logged_in_headers, active_user, different_owner
):
    project_id = uuid4()
    flow_id = compute_virtual_flow_id(uuid4(), uuid4(), principal_type="user")
    async with session_scope() as session:
        flow_owner_id = active_user.id
        if different_owner:
            contributor = User(username="project-contributor", password=uuid4().hex, is_active=True)
            session.add(contributor)
            await session.flush()
            flow_owner_id = contributor.id
        session.add(Folder(id=project_id, name="Legacy collision project", user_id=active_user.id))
        await session.flush()
        ordinary_flow = Flow(user_id=active_user.id, folder_id=project_id, name="Ordinary flow", data={})
        session.add(ordinary_flow)
        session.add(Flow(id=flow_id, user_id=flow_owner_id, folder_id=project_id, name="Existing collision", data={}))
        await session.flush()
        trace = TraceTable(flow_id=flow_id, name="Public history")
        session.add(trace)
        message = MessageTable(
            flow_id=flow_id,
            session_id="victim-session",
            sender="User",
            sender_name="User",
            text="private history",
            properties={},
        )
        session.add(message)
        await session.commit()
        message_id, trace_id, ordinary_flow_id = message.id, trace.id, ordinary_flow.id

    response = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)

    assert response.status_code == 400, response.text
    assert "reserved" in response.json()["detail"].lower()
    async with session_scope() as session:
        assert await session.get(Folder, project_id) is not None
        assert await session.get(Flow, flow_id) is not None
        assert await session.get(Flow, ordinary_flow_id) is not None
        assert await session.get(MessageTable, message_id) is not None
        assert await session.get(TraceTable, trace_id) is not None


async def test_reserved_flow_delete_preserves_foreign_key_histories():
    from fastapi import HTTPException
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel import SQLModel
    from sqlmodel.ext.asyncio.session import AsyncSession

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    flow_id = compute_virtual_flow_id(uuid4(), uuid4(), principal_type="user")
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(Flow(id=flow_id, name="Legacy UUID5 flow", data={}))
            await session.commit()
            trace = TraceTable(flow_id=flow_id, name="Public history")
            session.add(trace)
            await session.commit()
            span = SpanTable(trace_id=trace.id, name="Public span")
            session.add(span)
            await session.commit()
            trace_id, span_id = trace.id, span.id

            with pytest.raises(HTTPException) as error:
                await cascade_delete_flow(session, flow_id)
            assert error.value.status_code == 400
            await session.commit()
            assert await session.get(Flow, flow_id) is not None
            assert await session.get(TraceTable, trace_id) is not None
            assert await session.get(SpanTable, span_id) is not None
    finally:
        await engine.dispose()


@pytest.mark.parametrize("reserved", [True, False])
async def test_trace_history_requires_a_persisted_flow_namespace(client, logged_in_headers, active_user, reserved):
    flow_id = compute_virtual_flow_id(uuid4(), uuid4(), principal_type="user") if reserved else uuid4()
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name="Synthetic trace flow", user_id=active_user.id, data={}))
        await session.flush()
        trace = TraceTable(flow_id=flow_id, name="Synthetic trace")
        session.add(trace)
        await session.flush()
        span = SpanTable(trace_id=trace.id, name="Synthetic span")
        session.add(span)
        await session.commit()
        trace_id, span_id = trace.id, span.id

    for params in ({"flow_id": str(flow_id)}, {}):
        response = await client.get("api/v1/monitor/traces", params=params, headers=logged_in_headers)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == (0 if reserved else 1)
    response = await client.get(f"api/v1/monitor/traces/{trace_id}", headers=logged_in_headers)
    assert response.status_code == (404 if reserved else 200), response.text
    response = await client.delete(f"api/v1/monitor/traces/{trace_id}", headers=logged_in_headers)
    assert response.status_code == (404 if reserved else 204), response.text
    response = await client.delete("api/v1/monitor/traces", params={"flow_id": str(flow_id)}, headers=logged_in_headers)
    assert response.status_code == (404 if reserved else 204), response.text
    async with session_scope() as session:
        assert (await session.get(TraceTable, trace_id) is not None) is reserved
        assert (await session.get(SpanTable, span_id) is not None) is reserved
