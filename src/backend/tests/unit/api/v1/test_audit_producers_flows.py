"""Every existing Flow write path records what it did, through the real API and database."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from fastapi import status
from langflow.services.deps import get_settings_service, session_scope
from sqlmodel import select

from .audit_helpers import enabled_audit, events_by_user, events_for, login, make_user

pytestmark = pytest.mark.usefixtures("audit_on")

GRAPH = {"nodes": [], "edges": []}


@pytest.fixture
def audit_on(client):  # noqa: ARG001
    yield from enabled_audit()


async def _create_flow(client, headers, **fields) -> dict:
    body = {"name": f"flow-{uuid4().hex}", "data": GRAPH, **fields}
    response = await client.post("api/v1/flows/", json=body, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _create_project(client, headers, name: str | None = None) -> dict:
    response = await client.post("api/v1/projects/", json={"name": name or f"project-{uuid4().hex}"}, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def test_creating_a_flow_records_one_succeeded_create(client, logged_in_headers, active_user):
    flow = await _create_flow(client, logged_in_headers, description="never stored")

    [event] = await events_for(flow["id"])
    assert (event.resource_type, event.action, event.operation) == ("flow", "flow:create", "create")
    assert (event.event_type, event.result, event.error_code) == ("action", "succeeded", None)
    assert event.resource_name == flow["name"]
    assert (event.user_id, event.actor_type, event.actor_id) == (active_user.id, "user", active_user.id)
    assert event.acting_issuer is None
    assert event.acting_subject is None
    assert {"name", "data", "description"} <= set(event.details["written_fields"])
    assert event.details["project"] == {"before_id": None, "after_id": flow["folder_id"]}
    assert "never stored" not in json.dumps(event.details)


@pytest.fixture
def racing_authz_audit_writer(client, monkeypatch):  # noqa: ARG001
    """Turn on the authorization audit and let its writer reach the database mid-request.

    The writer commits each decision on its own connection. Yielding after every
    submission lets it take the SQLite write lock while the request still holds
    its read snapshot, which is the interleaving production hits under load.
    """
    import asyncio

    from langflow.services.authorization import audit as authz_audit

    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_AUDIT_ENABLED", True)
    submit = authz_audit.audit_decision

    async def submit_then_yield(**decision):
        await submit(**decision)
        await asyncio.sleep(0.05)

    monkeypatch.setattr(authz_audit, "audit_decision", submit_then_yield)


@pytest.mark.usefixtures("racing_authz_audit_writer")
async def test_moving_a_flow_succeeds_while_the_authorization_audit_writes(client, logged_in_headers):
    source = await _create_project(client, logged_in_headers)
    target = await _create_project(client, logged_in_headers)
    flow = await _create_flow(client, logged_in_headers, folder_id=source["id"])

    response = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"folder_id": target["id"]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["folder_id"] == target["id"]
    move = (await events_for(flow["id"]))[-1]
    assert move.details["project"] == {"before_id": source["id"], "after_id": target["id"]}


@pytest.mark.usefixtures("racing_authz_audit_writer")
async def test_activating_a_version_succeeds_while_the_authorization_audit_writes(client, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    version = await client.post(f"api/v1/flows/{flow['id']}/versions/", json={}, headers=logged_in_headers)
    assert version.status_code == status.HTTP_201_CREATED, version.text

    response = await client.post(
        f"api/v1/flows/{flow['id']}/versions/{version.json()['id']}/activate", headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK, response.text


async def test_a_rename_records_the_field_name_and_never_the_value(client, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"name": "renamed-secret-value"}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    _create, patch = await events_for(flow["id"])
    assert (patch.action, patch.operation, patch.result) == ("flow:write", "patch", "succeeded")
    assert patch.details == {"schema_version": 1, "written_fields": ["name"]}
    assert patch.resource_name == "renamed-secret-value"


async def test_moving_a_flow_records_both_projects(client, logged_in_headers):
    source = await _create_project(client, logged_in_headers)
    target = await _create_project(client, logged_in_headers)
    flow = await _create_flow(client, logged_in_headers, folder_id=source["id"])

    response = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"folder_id": target["id"]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    move = (await events_for(flow["id"]))[-1]
    assert move.details["project"] == {"before_id": source["id"], "after_id": target["id"]}


async def test_put_on_an_existing_flow_is_a_replace_and_on_a_new_id_a_create(client, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    replaced = await client.put(
        f"api/v1/flows/{flow['id']}", json={"name": flow["name"], "data": GRAPH}, headers=logged_in_headers
    )
    new_id = uuid4()
    created = await client.put(
        f"api/v1/flows/{new_id}", json={"name": f"put-{uuid4().hex}", "data": GRAPH}, headers=logged_in_headers
    )

    assert (replaced.status_code, created.status_code) == (200, 201)
    assert [(e.action, e.operation) for e in await events_for(flow["id"])][-1] == ("flow:write", "replace")
    [put_create] = await events_for(new_id)
    assert (put_create.action, put_create.operation, put_create.result) == ("flow:create", "create", "succeeded")


async def test_a_deleted_flow_keeps_its_history_and_its_last_name(client, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    response = await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    create, delete = await events_for(flow["id"])
    assert (delete.action, delete.operation, delete.result) == ("flow:delete", "delete", "succeeded")
    assert delete.resource_name == flow["name"]
    assert delete.details == {"schema_version": 1, "project": {"before_id": flow["folder_id"], "after_id": None}}
    assert create.timestamp <= delete.timestamp


async def test_bulk_create_and_bulk_delete_record_one_event_per_flow(client, logged_in_headers):
    body = {"flows": [{"name": f"batch-{index}-{uuid4().hex}", "data": GRAPH} for index in range(3)]}
    created = await client.post("api/v1/flows/batch/", json=body, headers=logged_in_headers)
    assert created.status_code == status.HTTP_201_CREATED, created.text
    ids = [flow["id"] for flow in created.json()]

    deleted = await client.request("DELETE", "api/v1/flows/", json=ids, headers=logged_in_headers)

    assert deleted.status_code == status.HTTP_200_OK, deleted.text
    for flow_id in ids:
        assert [(e.operation, e.result) for e in await events_for(flow_id)] == [
            ("create", "succeeded"),
            ("delete", "succeeded"),
        ]


async def test_uploading_flows_records_creates_and_replaces(client, logged_in_headers):
    existing = await _create_flow(client, logged_in_headers)
    new_id = str(uuid4())
    payload = {
        "flows": [
            {"id": existing["id"], "name": existing["name"], "data": GRAPH},
            {"id": new_id, "name": f"uploaded-{uuid4().hex}", "data": GRAPH},
        ]
    }
    files = {"file": ("flows.json", json.dumps(payload), "application/json")}

    response = await client.post("api/v1/flows/upload/", files=files, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert (await events_for(existing["id"]))[-1].operation == "replace"
    assert [e.operation for e in await events_for(new_id)] == ["create"]


async def test_restoring_a_version_records_a_data_patch(client, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    version = await client.post(f"api/v1/flows/{flow['id']}/versions/", json={}, headers=logged_in_headers)
    assert version.status_code == status.HTTP_201_CREATED, version.text

    response = await client.post(
        f"api/v1/flows/{flow['id']}/versions/{version.json()['id']}/activate", headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    restore = (await events_for(flow["id"]))[-1]
    assert (restore.action, restore.operation, restore.details) == (
        "flow:write",
        "patch",
        {"schema_version": 1, "written_fields": ["data"]},
    )


async def test_a_create_at_a_taken_id_is_an_id_conflict_not_a_name_conflict(client, logged_in_headers):
    existing = await _create_flow(client, logged_in_headers)
    attempted_name = f"reused-id-{uuid4().hex[:8]}"

    response = await client.post(
        "api/v1/flows/",
        json={"id": existing["id"], "name": attempted_name, "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    owner_id = UUID(existing["user_id"])
    failed = [event for event in await events_by_user(owner_id) if event.result == "failed"]
    assert [(event.action, event.error_code) for event in failed] == [("flow:create", "FLOW_ID_CONFLICT")]


async def test_a_refused_write_records_one_failure_and_no_change(client, logged_in_headers):
    first = await _create_flow(client, logged_in_headers, endpoint_name=f"ep-{uuid4().hex[:8]}")
    second = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{second['id']}", json={"endpoint_name": first["endpoint_name"]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    create, failed = await events_for(second["id"])
    assert (failed.event_type, failed.result, failed.error_code) == ("action", "failed", "FLOW_NAME_CONFLICT")
    assert failed.details == {"schema_version": 1, "attempted_fields": ["endpoint_name"]}
    assert failed.resource_name == second["name"]
    assert create.request_id != failed.request_id


async def test_a_put_create_that_conflicts_keeps_the_requested_identity(client, logged_in_headers):
    first = await _create_flow(client, logged_in_headers, endpoint_name=f"ep-{uuid4().hex[:8]}")
    requested = uuid4()

    response = await client.put(
        f"api/v1/flows/{requested}",
        json={"name": f"dup-{uuid4().hex}", "data": GRAPH, "endpoint_name": first["endpoint_name"]},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    [failed] = await events_for(requested)
    assert (failed.action, failed.operation, failed.result) == ("flow:create", "create", "failed")


async def test_a_failed_replace_names_the_flow_that_is_there(client, logged_in_headers):
    """A replace that fails names the Flow at that id, not the one the body asked for.

    The event's ``resource_id`` is the existing Flow's, so taking the name from
    the body would file another Flow's name under it and make the trail unreadable.
    """
    taken = await _create_flow(client, logged_in_headers, endpoint_name=f"ep-{uuid4().hex[:8]}")
    target = await _create_flow(client, logged_in_headers)

    response = await client.put(
        f"api/v1/flows/{target['id']}",
        json={"name": taken["name"], "data": GRAPH, "endpoint_name": taken["endpoint_name"]},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    _create, failed = await events_for(target["id"])
    assert (failed.action, failed.operation, failed.result) == ("flow:write", "replace", "failed")
    assert failed.resource_name == target["name"]


async def test_a_request_for_someone_elses_flow_records_nothing(client, logged_in_headers):
    _owner_id, owner_name = await make_user("owner")
    owner_headers = await login(client, owner_name)
    flow = await _create_flow(client, owner_headers)
    before = len(await events_for(flow["id"]))

    patch = await client.patch(f"api/v1/flows/{flow['id']}", json={"name": "x"}, headers=logged_in_headers)
    delete = await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)

    assert (patch.status_code, delete.status_code) == (404, 404)
    assert len(await events_for(flow["id"])) == before


async def test_a_plugin_denial_is_not_duplicated_into_action_audit_events(client):
    from tests.unit.services.authorization._policy_double import create_user_share, install_policy_authz

    alice_id, alice_name = await make_user("alice")
    bob_id, bob_name = await make_user("bob")
    alice_headers, bob_headers = await login(client, alice_name), await login(client, bob_name)
    flow = await _create_flow(client, alice_headers)
    async with session_scope() as session:
        await create_user_share(
            session,
            resource_type="flow",
            resource_id=UUID(flow["id"]),
            target_user_id=bob_id,
            permission_level="read",
            created_by=alice_id,
        )

    with install_policy_authz(get_settings_service()):
        patch = await client.patch(f"api/v1/flows/{flow['id']}", json={"name": "nope"}, headers=bob_headers)
        delete = await client.delete(f"api/v1/flows/{flow['id']}", headers=bob_headers)

    assert (patch.status_code, delete.status_code) == (403, 403)
    assert await events_by_user(bob_id) == []


async def test_nothing_is_recorded_when_auditing_is_off(client, logged_in_headers, active_user):
    settings = get_settings_service().settings
    settings.audit_enabled = False
    before = len(await events_by_user(active_user.id))

    flow = await _create_flow(client, logged_in_headers)
    await client.patch(f"api/v1/flows/{flow['id']}", json={"name": f"off-{uuid4().hex}"}, headers=logged_in_headers)
    await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)

    assert len(await events_by_user(active_user.id)) == before


async def test_an_event_the_database_refuses_rolls_the_flow_back(client, logged_in_headers, monkeypatch):
    from langflow.services.audit import writer
    from langflow.services.database.models.flow.model import Flow

    real_build = writer.build_audit_event

    def refused_by_the_database(draft):
        event = real_build(draft)
        event.result = "not-a-result"
        return event

    monkeypatch.setattr(writer, "build_audit_event", refused_by_the_database)
    name = f"atomic-{uuid4().hex}"

    response = await client.post("api/v1/flows/", json={"name": name, "data": GRAPH}, headers=logged_in_headers)

    assert response.status_code >= status.HTTP_400_BAD_REQUEST
    async with session_scope() as session:
        assert (await session.exec(select(Flow).where(Flow.name == name))).first() is None
