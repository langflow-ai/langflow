"""Every existing Project write path records what it did, through the real API and database."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.mcp_server.model import MCPServer
from langflow.services.deps import get_settings_service, session_scope
from sqlmodel import select

from .audit_helpers import enabled_audit, events_by_user, events_for, login, make_user

pytestmark = pytest.mark.usefixtures("audit_on")

GRAPH = {"nodes": [], "edges": []}


@pytest.fixture
def audit_on(client):  # noqa: ARG001
    yield from enabled_audit()


async def _create_flow(client, headers, **fields) -> dict:
    response = await client.post(
        "api/v1/flows/", json={"name": f"flow-{uuid4().hex}", "data": GRAPH, **fields}, headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _create_project(client, headers, **fields) -> dict:
    response = await client.post("api/v1/projects/", json={"name": f"project-{uuid4().hex}", **fields}, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def test_creating_a_project_records_its_description_and_the_flows_it_took(client, logged_in_headers):
    flows = [await _create_flow(client, logged_in_headers) for _ in range(2)]

    project = await _create_project(
        client,
        logged_in_headers,
        description="Routes customer questions",
        flows_list=[flow["id"] for flow in flows],
    )

    [event] = await events_for(project["id"], resource_type="project")
    assert (event.action, event.operation, event.event_type, event.result) == (
        "project:create",
        "create",
        "action",
        "succeeded",
    )
    assert event.resource_name == project["name"]
    assert event.details["description"] == "Routes customer questions"
    summary = event.details["flows"]
    assert (summary["before_count"], summary["after_count"], summary["updated_count"]) == (0, 2, 0)
    assert summary["truncated"] is False
    assert sorted((change["id"], change["name"], change["change"]) for change in summary["changes"]) == sorted(
        (flow["id"], flow["name"], "added") for flow in flows
    )


async def test_a_description_not_supplied_is_not_recorded_as_written(client, logged_in_headers):
    project = await _create_project(client, logged_in_headers)

    [event] = await events_for(project["id"])
    assert "description" not in event.details
    assert event.details["flows"] == {
        "before_count": 0,
        "after_count": 0,
        "updated_count": 0,
        "changes": [],
        "truncated": False,
    }


async def test_a_patch_records_only_what_it_wrote(client, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    new_name = f"renamed-{uuid4().hex}"

    described = await client.patch(
        f"api/v1/projects/{project['id']}", json={"description": "new text"}, headers=logged_in_headers
    )
    renamed = await client.patch(f"api/v1/projects/{project['id']}", json={"name": new_name}, headers=logged_in_headers)

    assert (described.status_code, renamed.status_code) == (200, 200)
    _create, description_patch, rename_patch = await events_for(project["id"])
    assert (description_patch.operation, description_patch.details) == (
        "patch",
        {"schema_version": 1, "description": "new text"},
    )
    assert (rename_patch.details, rename_patch.resource_name) == ({"schema_version": 1}, new_name)


async def _moves_for(flow_id) -> list:
    """Flow events that record a project move, which a create never is."""
    return [
        event
        for event in await events_for(flow_id, resource_type="flow")
        if event.operation == "patch" and "project" in event.details
    ]


async def test_a_project_create_records_the_move_on_each_flow_it_took(client, logged_in_headers):
    """A Flow's own history stays complete whichever route moved it."""
    source = await _create_project(client, logged_in_headers)
    flow = await _create_flow(client, logged_in_headers, folder_id=source["id"])

    destination = await _create_project(client, logged_in_headers, flows_list=[flow["id"]])

    [move] = await _moves_for(flow["id"])
    assert (move.action, move.result) == ("flow:write", "succeeded")
    assert move.details["project"] == {"before_id": source["id"], "after_id": destination["id"]}
    assert move.details["written_fields"] == ["folder_id"]


async def test_a_project_update_cannot_change_membership_so_records_none(client, logged_in_headers):
    """An update writes no membership.

    PATCH recomputes flows/components from the project itself, so a body naming
    other Flows moves nothing: no Flow records a move and the Project event
    claims no membership write.
    """
    kept = await _create_flow(client, logged_in_headers)
    project = await _create_project(client, logged_in_headers, flows_list=[kept["id"]])
    outsider = await _create_flow(client, logged_in_headers)

    updated = await client.patch(
        f"api/v1/projects/{project['id']}",
        json={"name": f"renamed-{uuid4().hex[:8]}", "flows": [outsider["id"]]},
        headers=logged_in_headers,
    )
    assert updated.status_code == status.HTTP_200_OK, updated.text

    [patch_event] = [
        event for event in await events_for(project["id"], resource_type="project") if event.operation == "patch"
    ]
    assert "flows" not in patch_event.details
    assert await _moves_for(outsider["id"]) == []
    # The one move on `kept` is the create that took it into the project.
    assert len(await _moves_for(kept["id"])) == 1


async def test_mcp_settings_record_the_flow_fields_they_write(client, logged_in_headers):
    """The same Flow fields PATCH /flows/{id} audits are audited on the MCP route."""
    flow = await _create_flow(client, logged_in_headers)
    project = await _create_project(client, logged_in_headers, flows_list=[flow["id"]])

    updated = await client.patch(
        f"api/v1/mcp/project/{project['id']}",
        json={
            "settings": [
                {
                    "id": flow["id"],
                    "action_name": "triage",
                    "action_description": "Route a ticket",
                    "mcp_enabled": True,
                }
            ]
        },
        headers=logged_in_headers,
    )
    assert updated.status_code == status.HTTP_200_OK, updated.text

    writes = [
        event
        for event in await events_for(flow["id"], resource_type="flow")
        if event.operation == "patch" and "mcp_enabled" in event.details.get("written_fields", [])
    ]
    assert [event.action for event in writes] == ["flow:write"]
    assert writes[0].details["written_fields"] == ["action_description", "action_name", "mcp_enabled"]
    assert "project" not in writes[0].details


async def test_a_rename_collision_records_a_failure_under_the_known_name(client, logged_in_headers):
    taken = await _create_project(client, logged_in_headers)
    project = await _create_project(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/projects/{project['id']}", json={"name": taken["name"]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    _create, failed = await events_for(project["id"])
    assert (failed.event_type, failed.result, failed.error_code) == ("action", "failed", "PROJECT_NAME_CONFLICT")
    assert failed.details == {"schema_version": 1, "attempted_fields": ["name"]}
    assert failed.resource_name == project["name"]


async def test_put_creates_at_the_requested_id_and_patches_an_existing_one(client, logged_in_headers):
    project_id = uuid4()
    body = {"name": f"put-{uuid4().hex}", "description": "d"}

    created = await client.put(f"api/v1/projects/{project_id}", json=body, headers=logged_in_headers)
    updated = await client.put(
        f"api/v1/projects/{project_id}", json={**body, "description": "e"}, headers=logged_in_headers
    )
    refused = await client.put(
        f"api/v1/projects/{project_id}", json={**body, "flows_list": [str(uuid4())]}, headers=logged_in_headers
    )

    assert (created.status_code, updated.status_code, refused.status_code) == (201, 200, 400)
    create, patch, failed = await events_for(project_id)
    assert (create.action, create.operation) == ("project:create", "create")
    assert (patch.action, patch.operation, patch.details["description"]) == ("project:write", "patch", "e")
    assert (failed.result, failed.error_code, failed.details["requested_flow_count"]) == (
        "failed",
        "INVALID_CONTENT",
        1,
    )
    assert "flows" in failed.details["attempted_fields"]


async def test_deleting_a_project_records_the_flows_it_removed_and_survives_the_project(client, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    flows = [await _create_flow(client, logged_in_headers, folder_id=project["id"]) for _ in range(2)]

    response = await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    _create, delete = await events_for(project["id"], resource_type="project")
    assert (delete.action, delete.operation, delete.result) == ("project:delete", "delete", "succeeded")
    assert delete.resource_name == project["name"]
    assert "description" not in delete.details
    summary = delete.details["flows"]
    assert (summary["before_count"], summary["after_count"], summary["updated_count"]) == (2, 0, 0)
    assert {(change["id"], change["change"]) for change in summary["changes"]} == {
        (flow["id"], "removed") for flow in flows
    }
    for flow in flows:
        assert [e.operation for e in await events_for(flow["id"])] == ["create", "delete"]


async def test_deleting_a_protected_project_records_a_constraint_failure(client, logged_in_headers):
    from langflow.initial_setup.constants import ASSISTANT_FOLDER_NAME

    async with session_scope() as session:
        owner = (await session.exec(select(Folder).where(Folder.name == ASSISTANT_FOLDER_NAME))).first()
    if owner is None:
        project = await _create_project(client, logged_in_headers, name=ASSISTANT_FOLDER_NAME)
    else:
        project = {"id": str(owner.id), "name": owner.name}

    response = await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    failed = (await events_for(project["id"]))[-1]
    assert (failed.event_type, failed.result, failed.error_code) == ("action", "failed", "CONSTRAINT_VIOLATION")


async def test_uploading_a_project_records_one_create_with_its_flows(client, logged_in_headers):
    payload = {
        "folder_name": f"uploaded-{uuid4().hex}",
        "folder_description": "imported",
        "flows": [{"name": f"up-{index}-{uuid4().hex}", "data": GRAPH} for index in range(2)],
    }
    files = {"file": ("project.json", json.dumps(payload), "application/json")}

    response = await client.post("api/v1/projects/upload/", files=files, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED, response.text
    created_flows = response.json()
    project_id = created_flows[0]["folder_id"]
    [event] = await events_for(project_id, resource_type="project")
    assert (event.operation, event.details["description"], event.details["flows"]["after_count"]) == (
        "create",
        "imported",
        2,
    )


async def test_a_failed_create_leaves_neither_project_nor_mcp_server_behind(client, logged_in_headers, monkeypatch):
    from langflow.api.v1 import projects as projects_module

    flow = await _create_flow(client, logged_in_headers)

    async def guard_refuses(*_args, **_kwargs):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Flow is attached to a deployment")

    monkeypatch.setattr(projects_module, "ensure_flow_moves_allowed", guard_refuses)
    name = f"atomic-{uuid4().hex}"

    response = await client.post(
        "api/v1/projects/", json={"name": name, "flows_list": [flow["id"]]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    async with session_scope() as session:
        assert (await session.exec(select(Folder).where(Folder.name == name))).first() is None
        servers = (await session.exec(select(MCPServer))).all()
    assert not [server for server in servers if name.lower().replace("-", "_") in server.name.lower().replace("-", "_")]


async def test_a_plugin_denial_is_not_duplicated_into_action_audit_events(client):
    from tests.unit.services.authorization._policy_double import create_user_share, install_policy_authz

    alice_id, alice_name = await make_user("alice")
    bob_id, bob_name = await make_user("bob")
    alice_headers, bob_headers = await login(client, alice_name), await login(client, bob_name)
    project = await _create_project(client, alice_headers)
    async with session_scope() as session:
        await create_user_share(
            session,
            resource_type="project",
            resource_id=UUID(project["id"]),
            target_user_id=bob_id,
            permission_level="read",
            created_by=alice_id,
        )

    with install_policy_authz(get_settings_service()):
        response = await client.patch(
            f"api/v1/projects/{project['id']}", json={"description": "nope"}, headers=bob_headers
        )

    assert response.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}
    assert await events_by_user(bob_id) == []
