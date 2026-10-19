"""With flow history off, graph writes behave as before history existed; turned on again, history resumes."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi import status
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.flow_history.replay import reconstruct_graph
from lfx.services.flow_operations import graphs_equal
from sqlmodel import col, select

if TYPE_CHECKING:
    from httpx import AsyncClient


def _node(node_id: str, value: str = "hi") -> dict:
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
                "outputs": [{"name": "out"}],
            },
        },
    }


def _graph(*nodes: dict) -> dict:
    return {"nodes": list(nodes), "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}


@pytest.fixture
def history():
    """The live settings, so a test can turn flow history off and on."""
    settings = get_settings_service().settings
    original = settings.flow_history_enabled
    yield settings
    settings.flow_history_enabled = original


async def _create_flow(client: AsyncClient, headers: dict, data: dict) -> dict:
    payload = {"name": f"history-off-{uuid4().hex[:8]}", "data": data}
    response = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _save(client: AsyncClient, headers: dict, flow_id: str, data: dict, token: str | None = None):
    extra = {"If-Match": token} if token else {}
    return await client.patch(f"api/v1/flows/{flow_id}", json={"data": data}, headers={**headers, **extra})


async def _flow(flow_id: str) -> Flow:
    async with session_scope() as session:
        return await session.get(Flow, UUID(flow_id))


async def _rows(flow_id: str) -> list[FlowOperation]:
    async with session_scope() as session:
        statement = (
            select(FlowOperation)
            .where(FlowOperation.flow_id == UUID(flow_id))
            .order_by(col(FlowOperation.start_revision))
        )
        return list((await session.exec(statement)).all())


async def _checkpoint_revisions(flow_id: str) -> list[int]:
    async with session_scope() as session:
        statement = select(FlowVersion.operation_revision).where(
            FlowVersion.flow_id == UUID(flow_id), col(FlowVersion.version_number).is_(None)
        )
        return sorted((await session.exec(statement)).all())


async def test_with_history_off_a_save_records_nothing_and_the_history_api_is_hidden(
    client: AsyncClient, logged_in_headers, history
):
    history.flow_history_enabled = False
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))

    saved = await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "x")), flow["version_token"])

    assert saved.status_code == status.HTTP_200_OK, saved.text
    assert saved.json()["history"] is None
    assert saved.json()["version_token"] != flow["version_token"]
    assert await _rows(flow["id"]) == []
    listed = await client.get(f"api/v1/flows/{flow['id']}/revisions", headers=logged_in_headers)
    assert listed.status_code == status.HTTP_404_NOT_FOUND
    config = await client.get("api/v1/config", headers=logged_in_headers)
    assert config.json()["flow_history_enabled"] is False


async def test_with_history_off_a_stale_token_is_refused_only_when_the_graph_changed(
    client: AsyncClient, logged_in_headers, history
):
    history.flow_history_enabled = False
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    first = await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "x")), flow["version_token"])
    assert first.status_code == status.HTTP_200_OK, first.text

    same = await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "x")), flow["version_token"])
    other = await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "y")), flow["version_token"])

    assert same.status_code == status.HTTP_200_OK, same.text
    assert other.status_code == status.HTTP_409_CONFLICT, other.text


async def test_with_history_off_an_overwrite_keeps_the_replaced_graph_as_a_version(
    client: AsyncClient, logged_in_headers, history
):
    history.flow_history_enabled = False
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    theirs = await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "theirs")))
    assert theirs.status_code == status.HTTP_200_OK, theirs.text

    overwritten = await client.post(
        f"api/v1/flows/{flow['id']}/overwrite",
        json={"data": _graph(_node("a", "mine"))},
        headers={**logged_in_headers, "If-Match": theirs.json()["version_token"]},
    )

    assert overwritten.status_code == status.HTTP_200_OK, overwritten.text
    async with session_scope() as session:
        versions = (await session.exec(select(FlowVersion).where(FlowVersion.flow_id == UUID(flow["id"])))).all()
    (archived,) = versions
    assert archived.description == "Replaced by a newer edit"
    assert graphs_equal(archived.data, _graph(_node("a", "theirs")))


async def test_a_flow_saved_while_history_was_off_resumes_its_history_from_a_new_checkpoint(
    client: AsyncClient, logged_in_headers, history
):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    recorded = await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "x")))
    assert recorded.json()["history"]["end_revision"] == 1

    history.flow_history_enabled = False
    await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "off")))
    assert (await _flow(flow["id"])).history_paused is True

    history.flow_history_enabled = True
    resumed = await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "on")))

    assert resumed.status_code == status.HTTP_200_OK, resumed.text
    assert (resumed.json()["history"]["start_revision"], resumed.json()["history"]["end_revision"]) == (3, 3)
    stored = await _flow(flow["id"])
    assert stored.history_paused is False
    assert stored.latest_revision == stored.current_revision == 3
    # The new checkpoint holds the graph saved while history was off.
    assert await _checkpoint_revisions(flow["id"]) == [0, 2]
    async with session_scope() as session:
        assert graphs_equal(await reconstruct_graph(session, stored.id, 1, latest_revision=3), _graph(_node("a", "x")))
        assert graphs_equal(
            await reconstruct_graph(session, stored.id, 2, latest_revision=3), _graph(_node("a", "off"))
        )
        assert graphs_equal(await reconstruct_graph(session, stored.id, 3, latest_revision=3), _graph(_node("a", "on")))
    entries = (await client.get(f"api/v1/flows/{flow['id']}/revisions", headers=logged_in_headers)).json()["entries"]
    assert [(entry["start_revision"], entry["end_revision"]) for entry in entries] == [(3, 3), (1, 1)]


async def test_purging_a_paused_flow_deletes_its_history_and_the_next_save_starts_it_again(
    client: AsyncClient, logged_in_headers, history
):
    flow = await _create_flow(client, logged_in_headers, _graph(_node("a")))
    await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "x")))
    history.flow_history_enabled = False
    await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "off")))
    history.flow_history_enabled = True

    purged = await client.post(f"api/v1/flows/{flow['id']}/revisions/purge", headers=logged_in_headers)

    assert purged.status_code < status.HTTP_300_MULTIPLE_CHOICES, purged.text
    assert await _rows(flow["id"]) == []
    assert await _checkpoint_revisions(flow["id"]) == []
    resumed = await _save(client, logged_in_headers, flow["id"], _graph(_node("a", "on")))
    assert resumed.json()["history"]["start_revision"] == 3
    assert await _checkpoint_revisions(flow["id"]) == [2]
