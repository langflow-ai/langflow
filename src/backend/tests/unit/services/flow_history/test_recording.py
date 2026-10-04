"""Graph writes record ordered, attributed, gap-free operation history."""

from __future__ import annotations

import asyncio
import copy
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi import status
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.flow_history.envelope import decode_row
from langflow.services.flow_history.replay import reconstruct_graph
from lfx.services.flow_operations import graphs_equal
from sqlalchemy import Uuid, bindparam, text
from sqlmodel import col, select

if TYPE_CHECKING:
    from httpx import AsyncClient


def _node(node_id: str, value: str = "hi", **extra) -> dict:
    return {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "data": {
            "id": node_id,
            "type": "Prompt",
            "node": {
                "display_name": f"Prompt {node_id}",
                "template": {"text": {"name": "text", "type": "str", "value": value}},
            },
        },
        **extra,
    }


def _edge(edge_id: str, source: str, target: str) -> dict:
    return {"id": edge_id, "source": source, "target": target, "sourceHandle": "out", "targetHandle": "in"}


def _graph(*nodes: dict, edges: list[dict] | None = None) -> dict:
    return {"nodes": list(nodes), "edges": edges or [], "viewport": {"x": 0, "y": 0, "zoom": 1}}


async def _create_flow(client: AsyncClient, headers: dict, data: dict | None = None) -> dict:
    payload = {"name": f"history-{uuid4().hex[:8]}", "data": data if data is not None else _graph()}
    response = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _patch(client: AsyncClient, headers: dict, flow_id: str, **body):
    return await client.patch(f"api/v1/flows/{flow_id}", json=body, headers=headers)


async def _rows(flow_id: str) -> list[FlowOperation]:
    async with session_scope() as session:
        statement = (
            select(FlowOperation)
            .where(FlowOperation.flow_id == UUID(flow_id))
            .order_by(col(FlowOperation.start_revision))
        )
        return list((await session.exec(statement)).all())


async def _checkpoints(flow_id: str) -> list[FlowVersion]:
    async with session_scope() as session:
        statement = select(FlowVersion).where(
            FlowVersion.flow_id == UUID(flow_id), col(FlowVersion.version_number).is_(None)
        )
        return list((await session.exec(statement)).all())


async def _flow(flow_id: str) -> Flow:
    async with session_scope() as session:
        return await session.get(Flow, UUID(flow_id))


async def _reconstruct(flow_id: str, revision: int) -> dict:
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(flow_id))
        return copy.deepcopy(
            await reconstruct_graph(
                session, flow.id, revision, latest_revision=flow.latest_revision, verify_anchor=True
            )
        )


def _assert_contiguous(rows: list[FlowOperation]) -> None:
    expected = 1
    for row in rows:
        assert row.start_revision == expected
        operations = decode_row(row)
        assert [operation.revision for operation in operations] == list(range(row.start_revision, row.end_revision + 1))
        expected = row.end_revision + 1


@pytest.fixture
def row_limits():
    settings = get_settings_service().settings
    original = (settings.flow_op_log_row_ops_limit, settings.flow_op_log_row_bytes_limit)
    yield settings
    settings.flow_op_log_row_ops_limit, settings.flow_op_log_row_bytes_limit = original


async def test_first_graph_edit_starts_history_and_records_attributed_operations(
    client: AsyncClient, logged_in_headers, active_user
):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    target = _graph(_node("a", "hello"), _node("b"), edges=[_edge("e", "a", "b")])

    response = await _patch(client, logged_in_headers, flow["id"], data=target)

    assert response.status_code == status.HTTP_200_OK, response.text
    history = response.json()["history"]
    assert history["start_revision"] == 1
    assert history["end_revision"] == 3  # add_nodes, update_nodes, add_edges
    assert history["latest_revision"] == history["current_revision"] == 3
    assert response.json()["latest_revision"] == 3

    (checkpoint,) = await _checkpoints(flow["id"])
    assert checkpoint.operation_revision == 0
    assert graphs_equal(checkpoint.data, _graph(_node("a")))

    (row,) = await _rows(flow["id"])
    operations = decode_row(row)
    assert [operation.operation.type for operation in operations] == ["add_nodes", "update_nodes", "add_edges"]
    assert {operation.actor_user_id for operation in operations} == {active_user.id}
    assert {str(operation.request_id) for operation in operations} == {history["request_id"]}
    assert row.actor_user_ids == [str(active_user.id)]
    assert row.request_ids == [history["request_id"]]
    assert operations[1].labels == {"nodes": {"a": "Prompt a"}}
    assert operations[2].labels == {"nodes": {"a": "Prompt a", "b": "Prompt b"}}


async def test_an_edge_changed_in_place_records_update_edges_with_its_endpoints(client: AsyncClient, logged_in_headers):
    edge = _edge("e", "a", "b")
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a"), _node("b"), edges=[edge]))
    changed = {**edge, "data": {"note": "rewired"}}

    response = await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a"), _node("b"), edges=[changed]))

    assert response.status_code == status.HTTP_200_OK, response.text
    (row,) = await _rows(flow["id"])
    (operation,) = decode_row(row)
    assert operation.operation.type == "update_edges"
    assert operation.labels == {
        "nodes": {"a": "Prompt a", "b": "Prompt b"},
        "edges": {"e": {"source": "a", "target": "b"}},
    }


async def test_every_revision_reconstructs_its_graph(client: AsyncClient, logged_in_headers):
    states = [
        _graph(_node("a")),
        _graph(_node("a"), _node("b")),
        _graph(_node("a"), _node("b"), edges=[_edge("e", "a", "b")]),
        _graph(_node("b", "changed")),
    ]
    flow = await _create_flow(client, logged_in_headers, states[0])
    revisions = [0]
    for state in states[1:]:
        response = await _patch(client, logged_in_headers, flow["id"], data=state)
        assert response.status_code == status.HTTP_200_OK, response.text
        revisions.append(response.json()["history"]["end_revision"])

    for revision, state in zip(revisions, states, strict=True):
        assert graphs_equal(await _reconstruct(flow["id"], revision), state)
    _assert_contiguous(await _rows(flow["id"]))


async def test_writes_that_change_no_graph_record_nothing(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    reordered_with_view_state = _graph(_node("a", selected=True))
    reordered_with_view_state["viewport"] = {"x": 9, "y": 9, "zoom": 2}

    renamed = await _patch(client, logged_in_headers, flow["id"], name="renamed")
    unchanged = await _patch(client, logged_in_headers, flow["id"], data=reordered_with_view_state)

    assert renamed.json()["history"] is None
    assert unchanged.json()["history"] is None
    assert await _rows(flow["id"]) == []
    # No revision was recorded, so history has not started either.
    assert await _checkpoints(flow["id"]) == []
    assert (await _flow(flow["id"])).latest_revision == 0


async def test_a_retry_with_the_same_request_id_records_once(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    request_id = str(uuid4())
    body = {"data": _graph(_node("a", "hello")), "request_id": request_id}

    first = await _patch(client, logged_in_headers, flow["id"], **body)
    retry = await _patch(client, logged_in_headers, flow["id"], **body)

    assert first.json()["history"]["deduplicated"] is False
    assert retry.json()["history"]["deduplicated"] is True
    assert retry.json()["history"]["start_revision"] == first.json()["history"]["start_revision"]
    assert retry.json()["history"]["end_revision"] == first.json()["history"]["end_revision"]
    assert len(await _rows(flow["id"])) == 1


async def test_a_write_without_request_id_gets_one(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))

    response = await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", "x")))

    request_id = response.json()["history"]["request_id"]
    assert UUID(request_id)
    (row,) = await _rows(flow["id"])
    assert row.request_ids == [request_id]


async def test_rows_respect_the_operation_count_limit(client: AsyncClient, logged_in_headers, row_limits):
    row_limits.flow_op_log_row_ops_limit = 2
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a"), _node("gone")))
    target = _graph(_node("a", "changed"), _node("b"), edges=[_edge("e", "a", "b")])
    target["description"] = "now described"

    response = await _patch(client, logged_in_headers, flow["id"], data=target)

    rows = await _rows(flow["id"])
    assert [(row.start_revision, row.end_revision) for row in rows] == [(1, 2), (3, 4), (5, 5)]
    _assert_contiguous(rows)
    request_id = response.json()["history"]["request_id"]
    assert all(row.request_ids == [request_id] for row in rows)
    assert graphs_equal(await _reconstruct(flow["id"], 5), target)


async def test_a_large_paste_is_split_across_rows_by_size(client: AsyncClient, logged_in_headers, row_limits):
    row_limits.flow_op_log_row_bytes_limit = 2048
    flow = await _create_flow(client, logged_in_headers, _graph())
    pasted = [_node(f"n{index}", "x" * 300) for index in range(6)]

    response = await _patch(client, logged_in_headers, flow["id"], data=_graph(*pasted))

    history = response.json()["history"]
    rows = await _rows(flow["id"])
    assert len(rows) > 1
    _assert_contiguous(rows)
    operations = [operation for row in rows for operation in decode_row(row)]
    assert {operation.operation.type for operation in operations} == {"add_nodes"}
    assert sum(len(operation.operation.nodes) for operation in operations) == len(pasted)
    assert history["end_revision"] - history["start_revision"] + 1 == len(operations)
    assert graphs_equal(await _reconstruct(flow["id"], history["end_revision"]), _graph(*pasted))


async def test_an_out_of_band_edit_is_refused_until_repair_is_requested(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", "recorded")))
    async with session_scope() as session:
        stored = await session.get(Flow, UUID(flow["id"]))
        stored.data = _graph(_node("a", "edited behind the API's back"))
        session.add(stored)

    refused = await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", "next")))

    assert refused.status_code == status.HTTP_409_CONFLICT
    assert refused.json()["detail"]["code"] == "FLOW_REVISION_MISMATCH"
    assert refused.json()["detail"]["current_revision"] == 1
    assert len(await _rows(flow["id"])) == 1

    repaired = await _patch(
        client, logged_in_headers, flow["id"], data=_graph(_node("a", "next")), repair_revision_mismatch=True
    )

    assert repaired.status_code == status.HTTP_200_OK, repaired.text
    assert repaired.json()["history"]["flow_repaired"] is True
    assert repaired.json()["history"]["start_revision"] == 2
    # The write was applied to the recorded graph, not to the out-of-band edit.
    (_, second) = await _rows(flow["id"])
    (update,) = decode_row(second)
    assert update.operation.updates[0].value == "next"
    assert graphs_equal(await _reconstruct(flow["id"], 2), _graph(_node("a", "next")))


async def test_a_submitted_graph_that_breaks_the_rules_is_refused_or_repaired(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    broken = _graph(_node("a"), _node("a"), edges=[_edge("e", "a", "missing")])

    refused = await _patch(client, logged_in_headers, flow["id"], data=broken)

    assert refused.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = refused.json()["detail"]
    assert detail["code"] == "FLOW_GRAPH_INVALID"
    assert detail["graph"] == "submitted"
    assert {violation["code"] for violation in detail["violations"]} == {"NODE_ID_DUPLICATE", "EDGE_ENDPOINT_INVALID"}
    assert await _rows(flow["id"]) == []

    repaired = await _patch(client, logged_in_headers, flow["id"], data=broken, repair_invalid_graph=True)

    assert repaired.status_code == status.HTTP_200_OK, repaired.text
    fixes = repaired.json()["history"]["graph_repairs"]
    assert {(fix["graph"], fix["code"]) for fix in fixes} == {
        ("submitted", "NODE_ID_DUPLICATE"),
        ("submitted", "EDGE_ENDPOINT_INVALID"),
    }
    stored = await _flow(flow["id"])
    assert len(stored.data["nodes"]) == 2
    assert stored.data["edges"] == []


async def test_a_stored_graph_that_breaks_the_rules_is_repaired_keeping_the_original(
    client: AsyncClient, logged_in_headers
):
    legacy = _graph(_node("a"), edges=[_edge("dangling", "a", "gone")])
    flow = await _create_flow(client, logged_in_headers, legacy)

    refused = await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", "edited")))

    assert refused.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert refused.json()["detail"]["graph"] == "stored"

    repaired = await _patch(
        client, logged_in_headers, flow["id"], data=_graph(_node("a", "edited")), repair_invalid_graph=True
    )

    assert repaired.status_code == status.HTTP_200_OK, repaired.text
    assert [fix["graph"] for fix in repaired.json()["history"]["graph_repairs"]] == ["stored"]
    (checkpoint,) = await _checkpoints(flow["id"])
    assert checkpoint.data["edges"] == []

    versions = (await client.get(f"api/v1/flows/{flow['id']}/versions/", headers=logged_in_headers)).json()["entries"]
    (original,) = versions
    assert original["view_only"] is True
    detail = (
        await client.get(f"api/v1/flows/{flow['id']}/versions/{original['id']}", headers=logged_in_headers)
    ).json()
    assert graphs_equal(detail["data"], legacy)

    restore = await client.post(
        f"api/v1/flows/{flow['id']}/versions/{original['id']}/activate", headers=logged_in_headers
    )
    assert restore.status_code == status.HTTP_409_CONFLICT


async def test_a_flow_without_data_starts_history_from_an_empty_graph(client: AsyncClient, logged_in_headers):
    response = await client.post("api/v1/flows/", json={"name": f"empty-{uuid4().hex[:6]}"}, headers=logged_in_headers)
    flow = response.json()

    written = await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a")))

    assert written.status_code == status.HTTP_200_OK, written.text
    assert graphs_equal(await _reconstruct(flow["id"], 0), {"nodes": [], "edges": []})


async def test_put_upsert_records_history(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))

    response = await client.put(
        f"api/v1/flows/{flow['id']}",
        json={"name": flow["name"], "data": _graph(_node("a", "via put"))},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["history"]["end_revision"] == 1
    assert graphs_equal(await _reconstruct(flow["id"], 1), _graph(_node("a", "via put")))


async def test_restoring_a_version_records_the_change_as_new_revisions(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", "v1")))
    snapshot = await client.post(f"api/v1/flows/{flow['id']}/versions/", json={}, headers=logged_in_headers)
    assert snapshot.json()["operation_revision"] == 1
    await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", "v2"), _node("b")))

    restored = await client.post(
        f"api/v1/flows/{flow['id']}/versions/{snapshot.json()['id']}/activate",
        params={"save_draft": "false"},
        headers=logged_in_headers,
    )

    assert restored.status_code == status.HTTP_200_OK, restored.text
    history = restored.json()["history"]
    assert history["start_revision"] == 4
    assert graphs_equal(await _reconstruct(flow["id"], history["end_revision"]), _graph(_node("a", "v1")))
    _assert_contiguous(await _rows(flow["id"]))


async def test_system_checkpoints_stay_out_of_the_version_list(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", "x")))

    versions = (await client.get(f"api/v1/flows/{flow['id']}/versions/", headers=logged_in_headers)).json()

    assert versions["entries"] == []
    (checkpoint,) = await _checkpoints(flow["id"])
    missing = await client.get(f"api/v1/flows/{flow['id']}/versions/{checkpoint.id}", headers=logged_in_headers)
    assert missing.status_code == status.HTTP_404_NOT_FOUND


async def test_concurrent_writes_form_one_gap_free_history(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))

    responses = await asyncio.gather(
        *(
            _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", f"writer {index}")))
            for index in range(4)
        )
    )

    assert all(response.status_code == status.HTTP_200_OK for response in responses), [r.text for r in responses]
    rows = await _rows(flow["id"])
    _assert_contiguous(rows)
    final = await _flow(flow["id"])
    assert final.latest_revision == final.current_revision == rows[-1].end_revision
    assert graphs_equal(await _reconstruct(flow["id"], final.latest_revision), final.data)


async def test_history_rows_are_append_only(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", "x")))
    (row,) = await _rows(flow["id"])

    for statement in (
        "UPDATE flow_operation SET end_revision = end_revision WHERE id = :id",
        "DELETE FROM flow_operation WHERE id = :id",
    ):
        with pytest.raises(Exception, match="flow_operation rows"):
            async with session_scope() as session:
                await session.exec(text(statement).bindparams(bindparam("id", value=row.id, type_=Uuid())))
    assert len(await _rows(flow["id"])) == 1


async def test_deleting_a_flow_deletes_its_history(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", "x")))

    response = await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert await _rows(flow["id"]) == []
    assert await _checkpoints(flow["id"]) == []


async def test_an_overwrite_records_the_merge_and_keeps_the_replaced_graph_on_its_revision(
    client: AsyncClient, logged_in_headers
):
    """The conflict dialog's overwrite is a graph write like any other, and what it replaced stays on its entry."""
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    saved = await _patch(client, logged_in_headers, flow["id"], data=_graph(_node("a", "theirs")))
    assert saved.status_code == status.HTTP_200_OK, saved.text
    replaced_revision = saved.json()["history"]["end_revision"]

    response = await client.post(
        f"api/v1/flows/{flow['id']}/overwrite",
        json={"data": _graph(_node("a", "merged"))},
        headers={**logged_in_headers, "If-Match": saved.json()["version_token"]},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["history"]["end_revision"] == replaced_revision + 1
    versions = await client.get(f"api/v1/flows/{flow['id']}/versions/", headers=logged_in_headers)
    (archived,) = [entry for entry in versions.json()["entries"] if entry["description"] == "Replaced by a newer edit"]
    assert archived["operation_revision"] == replaced_revision
