"""LANGFLOW_AUDIT_EXCLUDE_EVENTS through the real API: exactly the named actions go unrecorded, for every outcome."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID, uuid4

import pytest
from fastapi import status
from langflow.services.deps import get_settings_service, session_scope

from .audit_helpers import enabled_audit, events_by_user, events_for, login, make_user

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


async def _settled_run_events(flow_id, *, wait: float = 1.0) -> list:
    await asyncio.sleep(wait)
    return [event for event in await events_for(flow_id) if event.operation == "run"]


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


async def test_excluding_an_action_drops_its_denials_but_not_those_of_other_actions(client):
    from tests.unit.services.authorization._policy_double import create_user_share, install_policy_authz

    _exclude("flow:write")
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
    assert [(e.action, e.result) for e in await events_by_user(bob_id)] == [("flow:delete", "deny")]


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


async def test_an_excluded_api_run_answers_normally_and_records_nothing(client, simple_api_test, created_api_key):
    _exclude("flow:execute")

    response = await client.post(
        f"api/v1/run/{simple_api_test['id']}", headers={"x-api-key": created_api_key.api_key}, json={}
    )
    streamed = await client.post(
        f"api/v1/run/{simple_api_test['id']}?stream=true",
        headers={"x-api-key": created_api_key.api_key},
        json={"input_value": "hello"},
    )

    assert (response.status_code, streamed.status_code) == (status.HTTP_200_OK, status.HTTP_200_OK)
    assert await _settled_run_events(simple_api_test["id"]) == []


async def test_an_excluded_run_failure_answers_the_same_and_records_nothing(client, simple_api_test, created_api_key):
    _exclude("flow:execute")

    response = await client.post(
        f"api/v1/run/{simple_api_test['id']}",
        headers={"x-api-key": created_api_key.api_key},
        json={"input_type": "chat", "input_value": "a", "tweaks": {"Chat Input": {"input_value": "b"}}},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert await _settled_run_events(simple_api_test["id"]) == []


async def test_an_excluded_playground_build_records_no_run_but_keeps_the_flow_events(
    client, json_memory_chatbot_no_llm, logged_in_headers
):
    _exclude("flow:execute")
    created = await client.post("api/v1/flows/", json=json.loads(json_memory_chatbot_no_llm), headers=logged_in_headers)
    flow_id = created.json()["id"]

    started = await client.post(f"api/v1/build/{flow_id}/flow", json={}, headers=logged_in_headers)
    assert started.status_code == status.HTTP_200_OK, started.text
    events = await client.get(
        f"api/v1/build/{started.json()['job_id']}/events",
        headers={**logged_in_headers, "Accept": "application/x-ndjson"},
    )

    assert events.status_code == status.HTTP_200_OK
    assert await _settled_run_events(flow_id) == []
    assert await _actions(flow_id) == [("flow:create", "succeeded")]


async def test_a_misspelled_run_exclusion_never_hides_a_run(client, simple_api_test, created_api_key):
    _exclude("flows.execute")

    response = await client.post(
        f"api/v1/run/{simple_api_test['id']}", headers={"x-api-key": created_api_key.api_key}, json={}
    )

    assert response.status_code == status.HTTP_200_OK
    deadline = asyncio.get_running_loop().time() + 30
    runs: list = []
    while not runs and asyncio.get_running_loop().time() < deadline:
        runs = await _settled_run_events(simple_api_test["id"], wait=0.2)
    assert [(run.action, run.result) for run in runs] == [("flow:execute", "succeeded")]


async def test_an_excluded_refused_run_records_no_denial(client):
    from tests.unit.services.authorization._policy_double import create_user_share, install_policy_authz

    _exclude("flow:execute")
    alice_id, alice_name = await make_user("alice")
    bob_id, bob_name = await make_user("bob")
    alice, bob = await login(client, alice_name), await login(client, bob_name)
    flow = await client.post("api/v1/flows/", json={"name": f"f-{uuid4().hex}", "data": {}}, headers=alice)
    flow_id = flow.json()["id"]
    async with session_scope() as session:
        await create_user_share(
            session,
            resource_type="flow",
            resource_id=UUID(flow_id),
            target_user_id=bob_id,
            permission_level="read",
            created_by=alice_id,
        )

    with install_policy_authz(get_settings_service()):
        response = await client.post(f"api/v1/build/{flow_id}/flow", json={}, headers=bob)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert await events_by_user(bob_id) == []
