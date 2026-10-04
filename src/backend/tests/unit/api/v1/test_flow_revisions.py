"""The flow history API: the timeline, a revision's graph, and restoring one."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import status
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope
from lfx.services.flow_operations import graphs_equal

if TYPE_CHECKING:
    from httpx import AsyncClient


def _node(node_id: str, value: str = "hi", api_key: str | None = None) -> dict:
    template = {"text": {"name": "text", "type": "str", "value": value}}
    if api_key is not None:
        template["api_key"] = {"name": "api_key", "type": "str", "password": True, "value": api_key}
    return {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "data": {"id": node_id, "type": "Prompt", "node": {"display_name": f"Prompt {node_id}", "template": template}},
    }


def _graph(*nodes: dict) -> dict:
    return {"nodes": list(nodes), "edges": []}


async def _flow_with_history(client: AsyncClient, headers: dict, *states: dict) -> dict:
    response = await client.post(
        "api/v1/flows/", json={"name": f"revisions-{uuid4().hex[:8]}", "data": states[0]}, headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    flow = response.json()
    for state in states[1:]:
        saved = await client.patch(f"api/v1/flows/{flow['id']}", json={"data": state}, headers=headers)
        assert saved.status_code == status.HTTP_200_OK, saved.text
    return flow


async def test_the_timeline_lists_entries_newest_first_with_authors(
    client: AsyncClient, logged_in_headers, active_user
):
    flow = await _flow_with_history(
        client, logged_in_headers, _graph(_node("a")), _graph(_node("a", "one")), _graph(_node("a", "two"), _node("b"))
    )

    response = await client.get(f"api/v1/flows/{flow['id']}/revisions", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    page = response.json()
    assert page["latest_revision"] == page["current_revision"] == 3
    assert page["earliest_revision"] == 1
    assert [(entry["start_revision"], entry["end_revision"]) for entry in page["entries"]] == [(2, 3), (1, 1)]
    assert page["entries"][0]["actors"] == [{"id": str(active_user.id), "username": active_user.username}]
    assert page["entries"][0]["operations"] is None
    assert page["next_before"] is None


async def test_the_timeline_pages_by_revision(client: AsyncClient, logged_in_headers):
    flow = await _flow_with_history(
        client, logged_in_headers, *(_graph(_node("a", f"state {index}")) for index in range(5))
    )

    first = (await client.get(f"api/v1/flows/{flow['id']}/revisions?limit=2", headers=logged_in_headers)).json()
    second = (
        await client.get(
            f"api/v1/flows/{flow['id']}/revisions?limit=2&before={first['next_before']}", headers=logged_in_headers
        )
    ).json()

    assert [entry["end_revision"] for entry in first["entries"]] == [4, 3]
    assert [entry["end_revision"] for entry in second["entries"]] == [2, 1]
    assert second["next_before"] is None


async def test_operations_are_included_on_request_without_secrets(client: AsyncClient, logged_in_headers):
    flow = await _flow_with_history(
        client,
        logged_in_headers,
        _graph(_node("a")),
        _graph(_node("a", "changed", api_key="sk-literal-secret")),  # pragma: allowlist secret
    )

    response = await client.get(f"api/v1/flows/{flow['id']}/revisions?include=operations", headers=logged_in_headers)

    (entry,) = response.json()["entries"]
    (operation,) = entry["operations"]
    assert operation["revision"] == 1
    assert "labels" not in operation
    assert operation["cause"] is None
    values = {tuple(update["path"]): update["value"] for update in operation["operation"]["updates"]}
    assert values[("data", "node", "template", "text", "value")] == "changed"
    assert values[("data", "node", "template", "api_key")]["value"] is None
    assert "sk-literal-secret" not in response.text


async def test_operations_carry_the_cause_of_their_write(client: AsyncClient, logged_in_headers):
    flow = await _flow_with_history(client, logged_in_headers, _graph(_node("a")), _graph(_node("a", "one")))
    caused = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph(_node("a", "two"), _node("b")), "cause": "upgrade_component"},
        headers=logged_in_headers,
    )
    assert caused.status_code == status.HTTP_200_OK, caused.text

    response = await client.get(f"api/v1/flows/{flow['id']}/revisions?include=operations", headers=logged_in_headers)

    causes = {
        operation["revision"]: operation["cause"]
        for entry in response.json()["entries"]
        for operation in entry["operations"]
    }
    assert causes == {1: None, 2: "upgrade_component", 3: "upgrade_component"}


async def test_unknown_include_values_are_rejected(client: AsyncClient, logged_in_headers):
    flow = await _flow_with_history(client, logged_in_headers, _graph(_node("a")))

    response = await client.get(f"api/v1/flows/{flow['id']}/revisions?include=everything", headers=logged_in_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_saved_versions_are_pinned_to_their_entry(client: AsyncClient, logged_in_headers, active_user):
    flow = await _flow_with_history(client, logged_in_headers, _graph(_node("a")), _graph(_node("a", "one")))
    version = await client.post(
        f"api/v1/flows/{flow['id']}/versions/", json={"description": "before demo"}, headers=logged_in_headers
    )
    await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": _graph(_node("a", "two"))}, headers=logged_in_headers
    )

    page = (await client.get(f"api/v1/flows/{flow['id']}/revisions", headers=logged_in_headers)).json()

    newest, oldest = page["entries"]
    assert newest["versions"] == []
    (pinned,) = oldest["versions"]
    assert pinned["id"] == version.json()["id"]
    assert pinned["version_tag"] == "v1"
    assert pinned["description"] == "before demo"
    assert pinned["operation_revision"] == 1
    assert pinned["saved_by"] == {"id": str(active_user.id), "username": active_user.username}


async def test_a_revision_returns_its_graph_without_secrets(client: AsyncClient, logged_in_headers):
    first = _graph(_node("a", api_key="sk-literal-secret"))
    flow = await _flow_with_history(client, logged_in_headers, first, _graph(_node("a", "later")))

    response = await client.get(f"api/v1/flows/{flow['id']}/revisions/0", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    assert body["revision"] == 0
    expected = copy.deepcopy(first)
    expected["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] = None
    assert graphs_equal(body["data"], expected)


async def test_an_unrecorded_revision_is_not_found(client: AsyncClient, logged_in_headers):
    flow = await _flow_with_history(client, logged_in_headers, _graph(_node("a")), _graph(_node("a", "x")))

    response = await client.get(f"api/v1/flows/{flow['id']}/revisions/7", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"]["code"] == "FLOW_REVISION_NOT_FOUND"


async def test_restoring_a_revision_keeps_its_secrets_and_records_new_revisions(client: AsyncClient, logged_in_headers):
    first = _graph(_node("a", api_key="sk-literal-secret"))
    flow = await _flow_with_history(client, logged_in_headers, first, _graph(_node("a", "later")))

    restored = await client.post(f"api/v1/flows/{flow['id']}/revisions/0/restore", headers=logged_in_headers)

    assert restored.status_code == status.HTTP_200_OK, restored.text
    assert restored.json()["history"]["start_revision"] == 2
    # Replayed on the server, so the stored secret comes back rather than a blank.
    async with session_scope() as session:
        stored = await session.get(Flow, UUID(flow["id"]))
        assert graphs_equal(stored.data, first)
    entries = (
        await client.get(f"api/v1/flows/{flow['id']}/revisions?include=operations", headers=logged_in_headers)
    ).json()["entries"]
    assert entries[0]["start_revision"] == 2
    assert {operation["cause"] for operation in entries[0]["operations"]} == {"restore"}
    assert {operation["cause"] for operation in entries[1]["operations"]} == {None}


async def test_another_users_flow_history_is_not_found(client: AsyncClient, logged_in_headers):
    flow = await _flow_with_history(client, logged_in_headers, _graph(_node("a")), _graph(_node("a", "x")))
    username = f"other-{uuid4().hex[:8]}"
    async with session_scope() as session:
        session.add(
            User(username=username, password=get_auth_service().get_password_hash("testpassword"), is_active=True)
        )
    login = await client.post(
        "api/v1/login",
        data={"username": username, "password": "testpassword"},  # pragma: allowlist secret
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get(f"api/v1/flows/{flow['id']}/revisions", headers=other_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
