"""Project mutations, and the two families the trail keeps apart.

Projects are the resource the Control Plane consumes. What it needs from a row
is not only that something happened, but whether it worked and whether the
attempt was permitted at all — so these assert the outcome, not just the event.
"""

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.deps import get_settings_service


@pytest.fixture
def audit_on():
    settings = get_settings_service().settings
    original = settings.audit_enabled
    settings.audit_enabled = True
    yield
    settings.audit_enabled = original


async def _create_project(client: AsyncClient, headers) -> dict:
    response = await client.post(
        "api/v1/projects/",
        json={"name": f"audit-{uuid.uuid4()}", "description": ""},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _trail(client: AsyncClient, headers, project_id: str) -> list[dict]:
    response = await client.get(f"api/v1/audit/project/{project_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["entries"]


async def test_creating_a_project_is_recorded_as_an_action_that_succeeded(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    project = await _create_project(client, logged_in_headers)

    entries = await _trail(client, logged_in_headers, project["id"])
    created = [e for e in entries if e["event"] == "langflow.audit.project.create"]

    assert len(created) == 1
    assert created[0]["family"] == "action"
    assert created[0]["result"] == "succeeded"
    assert created[0]["resource_type"] == "project"
    assert created[0]["username"]


async def test_updating_a_project_is_recorded_against_that_project(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    project = await _create_project(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/projects/{project['id']}",
        json={"name": f"renamed-{uuid.uuid4()}"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    entries = await _trail(client, logged_in_headers, project["id"])
    updates = [e for e in entries if e["event"] == "langflow.audit.project.update"]

    assert len(updates) == 1
    assert updates[0]["family"] == "action"
    assert updates[0]["result"] == "succeeded"


async def test_a_failed_mutation_is_recorded_as_failed_not_missing(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """A mutation that raises is the row an investigation needs most.

    It is also the row the request's own rollback would erase, so it is written
    in its own transaction; this proves it survived.
    """
    project = await _create_project(client, logged_in_headers)
    other = await _create_project(client, logged_in_headers)

    # A name collision fails loud on this path, giving a real failure rather
    # than one staged with a mock.
    response = await client.patch(
        f"api/v1/projects/{project['id']}",
        json={"name": other["name"]},
        headers=logged_in_headers,
    )
    assert response.status_code >= status.HTTP_400_BAD_REQUEST, response.text

    entries = await _trail(client, logged_in_headers, project["id"])
    failures = [e for e in entries if e["result"] == "failed"]

    assert len(failures) == 1
    assert failures[0]["event"] == "langflow.audit.project.update"
    assert failures[0]["family"] == "action"
    # The class is named so a reader can tell a validation refusal from a bug,
    # without the row carrying a message that might quote user data.
    assert failures[0]["payload"]["error_class"]


async def test_deleting_a_project_is_recorded_before_it_stops_being_readable(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    project = await _create_project(client, logged_in_headers)

    response = await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

    # The trail outlives the resource: a deleted project is exactly the one
    # somebody asks about later.
    entries = await _trail(client, logged_in_headers, project["id"])
    deleted = [e for e in entries if e["event"] == "langflow.audit.project.delete"]

    assert len(deleted) == 1
    assert deleted[0]["result"] == "succeeded"


async def test_a_row_never_carries_the_projects_contents(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    project = await _create_project(client, logged_in_headers)

    entries = await _trail(client, logged_in_headers, project["id"])

    assert entries
    body = str(entries)
    assert "nodes" not in body, "no graph fragment may be stored"
    assert "description" not in body, "no field value may be stored"


async def test_creating_a_project_with_its_flows_records_one_row_for_the_whole_act(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """The caller performed one act, so the trail carries one row.

    A row per flow underneath would answer a question nobody asked and bury the
    one they did.
    """
    response = await client.post(
        "api/v1/projects/with-flows",
        json={
            "name": f"atomic-{uuid.uuid4()}",
            "description": "",
            "flows": [
                {"name": f"one-{uuid.uuid4()}", "data": {"nodes": [], "edges": []}},
                {"name": f"two-{uuid.uuid4()}", "data": {"nodes": [], "edges": []}},
            ],
        },
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    project = response.json()

    entries = await _trail(client, logged_in_headers, project["id"])
    created = [e for e in entries if e["event"] == "langflow.audit.project.create"]

    assert len(created) == 1
    assert created[0]["result"] == "succeeded"
    assert created[0]["payload"]["flows_total"] == 2


async def test_replacing_a_projects_contents_records_one_row_and_no_flow_rows(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    created = await client.post(
        "api/v1/projects/with-flows",
        json={
            "name": f"atomic-{uuid.uuid4()}",
            "description": "",
            "flows": [{"name": f"before-{uuid.uuid4()}", "data": {"nodes": [], "edges": []}}],
        },
        headers=logged_in_headers,
    )
    assert created.status_code == status.HTTP_201_CREATED, created.text
    project_id = created.json()["id"]

    response = await client.put(
        f"api/v1/projects/{project_id}/flows",
        json={"flows": [{"name": f"after-{uuid.uuid4()}", "data": {"nodes": [], "edges": []}}]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    entries = await _trail(client, logged_in_headers, project_id)
    replaced = [e for e in entries if e["event"] == "langflow.audit.project.replace"]

    assert len(replaced) == 1
    assert replaced[0]["payload"]["flows_total"] == 1
    assert replaced[0]["payload"]["flows_removed"] == 1
    # The contents the caller sent are the contents it ends up with.
    listed = await client.get(f"api/v1/flows/?folder_id={project_id}", headers=logged_in_headers)
    assert listed.status_code == status.HTTP_200_OK, listed.text
    assert [flow["name"].startswith("after-") for flow in listed.json()] == [True]
