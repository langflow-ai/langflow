"""LANGFLOW_AUDIT_EXCLUDE_EVENTS through the real API: exactly the named actions go unrecorded, for every outcome."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from langflow.services.deps import get_settings_service

from .audit_helpers import enabled_audit, events_for

pytestmark = pytest.mark.usefixtures("audit_on")

GRAPH = {"nodes": [], "edges": []}


@pytest.fixture
def audit_on(client):  # noqa: ARG001
    yield from enabled_audit()


def _exclude(value: str) -> None:
    get_settings_service().settings.audit_exclude_events = value


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


async def _actions(resource_id) -> list[tuple[str, str]]:
    return [(event.action, event.result) for event in await events_for(resource_id)]


async def test_excluding_project_delete_keeps_the_create_and_every_flow_delete(client, logged_in_headers):
    _exclude("project:delete")
    project = await _create_project(client, logged_in_headers)
    flows = [await _create_flow(client, logged_in_headers, folder_id=project["id"]) for _ in range(2)]

    response = await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert await _actions(project["id"]) == [("project:create", "succeeded")]
    for flow in flows:
        assert await _actions(flow["id"]) == [("flow:create", "succeeded"), ("flow:delete", "succeeded")]


async def test_excluding_every_flow_action_leaves_project_events_intact(client, logged_in_headers):
    _exclude("flow:*")
    flow = await _create_flow(client, logged_in_headers)
    await client.patch(f"api/v1/flows/{flow['id']}", json={"name": f"renamed-{uuid4().hex}"}, headers=logged_in_headers)

    project = await _create_project(client, logged_in_headers, flows_list=[flow["id"]])
    await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)

    assert await _actions(flow["id"]) == []
    [event] = await events_for(project["id"])
    assert (event.action, event.details["flows"]["after_count"]) == ("project:create", 1)


async def test_an_action_wildcard_excludes_it_on_every_resource_and_nothing_else(client, logged_in_headers):
    _exclude("*:delete")
    project = await _create_project(client, logged_in_headers)
    flow = await _create_flow(client, logged_in_headers, folder_id=project["id"])

    await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)
    await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)

    assert await _actions(flow["id"]) == [("flow:create", "succeeded")]
    assert await _actions(project["id"]) == [("project:create", "succeeded")]


async def test_an_excluded_failure_answers_the_same_and_records_nothing(client, logged_in_headers):
    _exclude("project:write")
    taken = await _create_project(client, logged_in_headers)
    project = await _create_project(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/projects/{project['id']}", json={"name": taken["name"]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert await _actions(project["id"]) == [("project:create", "succeeded")]


async def test_an_excluded_refused_flow_write_answers_the_same_and_records_nothing(client, logged_in_headers):
    _exclude("flow:write")
    first = await _create_flow(client, logged_in_headers, endpoint_name=f"ep-{uuid4().hex[:8]}")
    second = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{second['id']}", json={"endpoint_name": first["endpoint_name"]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    assert await _actions(second["id"]) == [("flow:create", "succeeded")]


async def test_entries_that_name_nothing_are_ignored_and_the_valid_one_still_applies(client, logged_in_headers):
    _exclude("deployment:delete, *:*, flow:read, projects.delete, , nonsense, flow:write")
    project = await _create_project(client, logged_in_headers)
    flow = await _create_flow(client, logged_in_headers, folder_id=project["id"])

    await client.patch(f"api/v1/flows/{flow['id']}", json={"name": f"renamed-{uuid4().hex}"}, headers=logged_in_headers)
    await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)
    await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)

    assert await _actions(flow["id"]) == [("flow:create", "succeeded"), ("flow:delete", "succeeded")]
    assert await _actions(project["id"]) == [("project:create", "succeeded"), ("project:delete", "succeeded")]


async def test_a_list_made_only_of_unknown_entries_records_everything(client, logged_in_headers):
    _exclude("flows.write,project:read,*:*")
    flow = await _create_flow(client, logged_in_headers)

    await client.patch(f"api/v1/flows/{flow['id']}", json={"name": f"renamed-{uuid4().hex}"}, headers=logged_in_headers)

    assert await _actions(flow["id"]) == [("flow:create", "succeeded"), ("flow:write", "succeeded")]
