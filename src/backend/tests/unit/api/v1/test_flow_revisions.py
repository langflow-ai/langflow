"""The flow history API: the timeline, a revision's graph, and restoring one."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import langflow.initial_setup
from fastapi import status
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope
from lfx.services.flow_operations import graphs_equal
from lfx_docling.components.docling.docling_remote import DoclingRemoteComponent
from sqlmodel import select

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


AWS_KEY = "AKIAIOSFODNN7EXAMPLE"  # pragma: allowlist secret - AWS's documented example key


async def test_a_key_pasted_into_a_password_field_reads_back_as_null(client: AsyncClient, logged_in_headers):
    """The File component's ``aws_access_key_id`` is a password field whose name reads as ordinary."""
    starters = Path(langflow.initial_setup.__file__).parent / "starter_projects"
    starter = json.loads((starters / "Financial Report Parser.json").read_text())["data"]
    pasted = copy.deepcopy(starter)
    file_node = next(node for node in pasted["nodes"] if node["id"] == "File-NGW2N")
    file_node["data"]["node"]["template"]["aws_access_key_id"]["value"] = AWS_KEY
    flow = await _flow_with_history(client, logged_in_headers, starter, pasted)

    response = await client.get(f"api/v1/flows/{flow['id']}/revisions?include=operations", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    (entry,) = response.json()["entries"]
    (operation,) = entry["operations"]
    value_path = ["data", "node", "template", "aws_access_key_id", "value"]
    (update,) = [update for update in operation["operation"]["updates"] if update["path"] == value_path]
    assert update["id"] == "File-NGW2N"
    assert update["value"] is None
    # The secret parts the history stored with the write stay on the server.
    assert "secrets" not in update
    assert AWS_KEY not in response.text


PASTED_HEADER = "Bearer sk-docling-literal-0123456789"  # pragma: allowlist secret


async def test_header_rows_read_back_with_literal_tokens_nulled_and_variable_names_kept(
    client: AsyncClient, logged_in_headers
):
    """Docling Serve's ``api_headers`` is a table whose ``value`` column loads global variables."""
    variable = {"name": "DOCLING_HEADER", "value": "a-secret", "type": "Credential", "default_fields": []}
    created = await client.post("api/v1/variables/", json=variable, headers=logged_in_headers)
    assert created.status_code == status.HTTP_201_CREATED, created.text
    node = DoclingRemoteComponent().to_frontend_node()
    node["position"] = {"x": 0, "y": 0}
    before = _graph(node)
    after = copy.deepcopy(before)
    after["nodes"][0]["data"]["node"]["template"]["api_headers"]["value"] = [
        {"__id__": "r1", "__pos__": 1, "key": "Authorization", "value": PASTED_HEADER},
        {"__id__": "r2", "__pos__": 2, "key": "X-Api-Key", "value": "DOCLING_HEADER"},
    ]
    flow = await _flow_with_history(client, logged_in_headers, before, after)

    response = await client.get(f"api/v1/flows/{flow['id']}/revisions?include=operations", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    (entry,) = response.json()["entries"]
    (operation,) = entry["operations"]
    rows = {update["path"][-1]["key"]: update for update in operation["operation"]["updates"]}
    assert rows["r1"]["value"]["key"] == "Authorization"
    assert rows["r1"]["value"]["value"] is None
    assert rows["r2"]["value"]["value"] == "DOCLING_HEADER"
    assert all("secrets" not in update for update in rows.values())
    assert PASTED_HEADER not in response.text
    # The row keeps the token, and the parts that hide it.
    async with session_scope() as session:
        stored = (await session.exec(select(FlowOperation).where(FlowOperation.flow_id == UUID(flow["id"])))).one()
    stored_rows = {
        update["path"][-1]["key"]: update
        for update in stored.ops["batches"][0]["operations"][0]["operation"]["updates"]
    }
    assert stored_rows["r1"]["value"]["value"] == PASTED_HEADER
    assert stored_rows["r1"]["secrets"] == [{"path": ["value"], "kind": "literal"}]
    assert stored_rows["r2"]["secrets"] == [{"path": ["value"], "kind": "variable"}]


PASTED_GROUP_VALUE = "sk-group-literal-0123456789"  # pragma: allowlist secret


def _group(*inner: dict) -> dict:
    flow = {"data": {"nodes": list(inner), "edges": []}, "name": "Group"}
    return {
        "id": "g",
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "data": {"id": "g", "type": "GroupNode", "node": {"display_name": "Group", "template": {}, "flow": flow}},
    }


async def test_a_secret_inside_a_group_reads_back_as_null_and_nothing_else_changes(
    client: AsyncClient, logged_in_headers
):
    before = _graph(_group(_node("x"), _node("lm", api_key="")))
    after = _graph(_group(_node("x"), _node("lm", api_key=PASTED_GROUP_VALUE)))
    flow = await _flow_with_history(client, logged_in_headers, before, after)

    response = await client.get(f"api/v1/flows/{flow['id']}/revisions?include=operations", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    (entry,) = response.json()["entries"]
    (operation,) = entry["operations"]
    (update,) = operation["operation"]["updates"]
    assert update["path"] == ["data", "node", "flow"]
    expected = copy.deepcopy(after["nodes"][0]["data"]["node"]["flow"])
    expected["data"]["nodes"][1]["data"]["node"]["template"]["api_key"]["value"] = None
    assert update["value"] == expected
    assert "secrets" not in update
    assert PASTED_GROUP_VALUE not in response.text
    # The row keeps the secret, and names its part by the inner node's index.
    async with session_scope() as session:
        stored = (await session.exec(select(FlowOperation).where(FlowOperation.flow_id == UUID(flow["id"])))).one()
    (stored_update,) = stored.ops["batches"][0]["operations"][0]["operation"]["updates"]
    api_key = ["data", "node", "template", "api_key", "value"]
    assert stored_update["secrets"] == [{"path": ["data", "nodes", 1, *api_key], "kind": "literal"}]
    inner_template = stored_update["value"]["data"]["nodes"][1]["data"]["node"]["template"]
    assert inner_template["api_key"]["value"] == PASTED_GROUP_VALUE


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


async def test_a_restore_over_newer_work_is_a_conflict(client: AsyncClient, logged_in_headers):
    flow = await _flow_with_history(client, logged_in_headers, _graph(_node("a")), _graph(_node("a", "mine")))
    seen = (await client.get(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)).json()["version_token"]
    newer = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": _graph(_node("a", "theirs"))}, headers=logged_in_headers
    )
    assert newer.status_code == status.HTTP_200_OK, newer.text

    refused = await client.post(
        f"api/v1/flows/{flow['id']}/revisions/0/restore", headers={**logged_in_headers, "If-Match": seen}
    )

    assert refused.status_code == status.HTTP_409_CONFLICT, refused.text
    assert refused.json()["detail"]["code"] == "flow_version_conflict"
    async with session_scope() as session:
        stored = await session.get(Flow, UUID(flow["id"]))
        assert graphs_equal(stored.data, _graph(_node("a", "theirs")))

    current = newer.json()["version_token"]
    restored = await client.post(
        f"api/v1/flows/{flow['id']}/revisions/0/restore", headers={**logged_in_headers, "If-Match": current}
    )

    assert restored.status_code == status.HTTP_200_OK, restored.text


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


STORED_KEY = "sk-stored"  # pragma: allowlist secret


def _legacy_edge(source: str, target: str) -> dict:
    """An edge in a format older editors wrote: handle strings that are not JSON, and no data."""
    return {"id": "legacy-edge", "source": source, "target": target, "sourceHandle": "x|y", "targetHandle": "z|w"}


def _with_output(node: dict) -> dict:
    node["data"]["node"]["outputs"] = [{"name": "out", "types": ["Message"]}]
    return node


def _handle_fixes(edge: dict, output: str, field: str) -> list[dict]:
    """Fixes that delete an edge and add it back with both forms of other handles."""
    handles = {"sourceHandle": {"name": output}, "targetHandle": {"fieldName": field}}
    strings = {key: json.dumps(value).replace('"', "œ") for key, value in handles.items()}
    return [
        {"type": "delete_edges", "ids": [edge["id"]]},
        {"type": "add_edges", "edges": [{**edge, **strings, "data": handles}]},
    ]


async def _refused_legacy_flow(client: AsyncClient, headers: dict) -> tuple[dict, str]:
    """A flow whose revision 0 holds an old-format edge, and that revision's URL; restoring it is refused."""
    # A flow stored before history, with an old-format edge, becomes revision 0 on its first edit.
    stored = {"nodes": [_with_output(_node("a")), _node("b", api_key=STORED_KEY)], "edges": [_legacy_edge("a", "b")]}
    flow = await _flow_with_history(
        client, headers, stored, _graph(_with_output(_node("a")), _node("b", "edited", STORED_KEY))
    )
    url = f"api/v1/flows/{flow['id']}/revisions/0"
    refused = await client.post(f"{url}/restore", json={}, headers=headers)
    assert refused.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, refused.text
    assert {violation["resolution"] for violation in refused.json()["detail"]["violations"]} == {"manual"}
    return flow, url


async def _stored(flow: dict) -> dict:
    async with session_scope() as session:
        return (await session.get(Flow, UUID(flow["id"]))).data


async def _versions(client: AsyncClient, headers: dict, flow: dict) -> list[dict]:
    return (await client.get(f"api/v1/flows/{flow['id']}/versions/", headers=headers)).json()["entries"]


async def test_a_restore_with_the_clients_fixes_keeps_the_revisions_secrets(client: AsyncClient, logged_in_headers):
    flow, url = await _refused_legacy_flow(client, logged_in_headers)

    response = await client.post(
        f"{url}/restore",
        json={"fixes": [{"type": "delete_edges", "ids": ["legacy-edge"]}]},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    restored = await _stored(flow)
    node_b = next(node for node in restored["nodes"] if node["id"] == "b")
    assert node_b["data"]["node"]["template"]["api_key"]["value"] == STORED_KEY
    assert node_b["data"]["node"]["template"]["text"]["value"] == "hi"
    assert restored["edges"] == []
    versions = await _versions(client, logged_in_headers, flow)
    assert any("before the client fixed it" in (version.get("description") or "") for version in versions)


async def test_a_retried_restore_with_fixes_keeps_one_unfixed_copy(client: AsyncClient, logged_in_headers):
    flow, url = await _refused_legacy_flow(client, logged_in_headers)
    body = {"fixes": [{"type": "delete_edges", "ids": ["legacy-edge"]}]}
    first = await client.post(f"{url}/restore", json=body, headers=logged_in_headers)
    assert first.status_code == status.HTTP_200_OK, first.text

    # The retry of a restore whose response was lost changes nothing.
    retry = await client.post(f"{url}/restore", json=body, headers=logged_in_headers)

    assert retry.status_code == status.HTTP_200_OK, retry.text
    assert retry.json()["history"] is None
    versions = await _versions(client, logged_in_headers, flow)
    assert sum("before the client fixed it" in (version.get("description") or "") for version in versions) == 1


async def test_a_fix_can_reconnect_an_edge(client: AsyncClient, logged_in_headers):
    flow, url = await _refused_legacy_flow(client, logged_in_headers)

    response = await client.post(
        f"{url}/restore",
        json={"fixes": _handle_fixes(_legacy_edge("a", "b"), "out", "text")},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    [edge] = (await _stored(flow))["edges"]
    assert edge["data"] == {"sourceHandle": {"name": "out"}, "targetHandle": {"fieldName": "text"}}


async def test_a_fix_that_does_not_apply_is_refused_and_keeps_nothing(client: AsyncClient, logged_in_headers):
    flow, url = await _refused_legacy_flow(client, logged_in_headers)
    before = await _stored(flow)

    response = await client.post(
        f"{url}/restore",
        json={"fixes": _handle_fixes(_legacy_edge("a", "b"), "missing", "text")},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert response.json()["detail"]["code"] == "EDGE_HANDLE_NOT_FOUND"
    assert await _stored(flow) == before
    assert not await _versions(client, logged_in_headers, flow)


async def test_a_fix_that_addresses_no_violation_is_refused_and_keeps_nothing(client: AsyncClient, logged_in_headers):
    flow, url = await _refused_legacy_flow(client, logged_in_headers)
    before = await _stored(flow)

    response = await client.post(
        f"{url}/restore", json={"fixes": [{"type": "delete_edges", "ids": ["no-such-edge"]}]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert response.json()["detail"]["code"] == "RESTORE_FIX_NOT_ALLOWED"
    assert await _stored(flow) == before
    assert not await _versions(client, logged_in_headers, flow)


async def test_fixes_are_only_edge_deletes_and_handle_rewrites(client: AsyncClient, logged_in_headers):
    flow, url = await _refused_legacy_flow(client, logged_in_headers)

    response = await client.post(
        f"{url}/restore",
        json={"fixes": [{"type": "add_nodes", "nodes": [_node("c")]}]},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert not await _versions(client, logged_in_headers, flow)
