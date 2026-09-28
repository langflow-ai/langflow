"""Automatic checkpoints, compaction, and purge keep history bounded and every retained revision reachable."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi import status
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.flow_history import maintenance
from langflow.services.flow_history.errors import FlowRevisionNotRetainedError
from langflow.services.flow_history.replay import reconstruct_graph
from lfx.services.flow_operations import graphs_equal
from sqlalchemy import update
from sqlmodel import col, func, select

if TYPE_CHECKING:
    from httpx import AsyncClient

# Low thresholds make maintenance due within a few saves, and scheduled
# maintenance is recorded instead of run in the background, so each test runs
# it at the point it chooses.
pytestmark = pytest.mark.usefixtures("thresholds", "scheduled")


def _node(value: str) -> dict:
    return {"id": "a", "data": {"node": {"display_name": "A", "template": {"text": {"value": value}}}}}


def _graph(value: str) -> dict:
    return {"nodes": [_node(value)], "edges": []}


@pytest.fixture
def thresholds(client, monkeypatch):  # noqa: ARG001 -- the app's settings exist once the client does
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "flow_revision_checkpoint_cadence", 3)
    monkeypatch.setattr(settings, "flow_revision_retention_window", 5)
    return settings


@pytest.fixture
def scheduled(monkeypatch):
    """Record maintenance requests instead of running them in the background."""
    requested: list[UUID] = []

    async def run_later(flow_id):
        requested.append(flow_id)

    monkeypatch.setattr(maintenance, "run_maintenance", run_later)
    return requested


async def _flow(client: AsyncClient, headers: dict) -> str:
    response = await client.post(
        "api/v1/flows/", json={"name": f"maintained-{uuid4().hex[:8]}", "data": _graph("0")}, headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["id"]


async def _save(client: AsyncClient, headers: dict, flow_id: str, value: str) -> dict:
    response = await client.patch(f"api/v1/flows/{flow_id}", json={"data": _graph(value)}, headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["history"]


async def _system_checkpoints(flow_id: str) -> list[int]:
    async with session_scope() as session:
        rows = await session.exec(
            select(FlowVersion.operation_revision)
            .where(FlowVersion.flow_id == UUID(flow_id), col(FlowVersion.version_number).is_(None))
            .order_by(col(FlowVersion.operation_revision))
        )
        return list(rows.all())


async def _retained(flow_id: str) -> tuple[int | None, int | None]:
    async with session_scope() as session:
        return (
            await session.exec(
                select(func.min(FlowOperation.start_revision), func.min(FlowOperation.end_revision)).where(
                    FlowOperation.flow_id == UUID(flow_id)
                )
            )
        ).one()


async def _reconstruct(flow_id: str, revision: int) -> dict:
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(flow_id))
        return copy.deepcopy(await reconstruct_graph(session, flow.id, revision, latest_revision=flow.latest_revision))


async def test_crossing_the_cadence_schedules_maintenance_after_commit(
    client: AsyncClient, logged_in_headers, scheduled
):
    flow_id = await _flow(client, logged_in_headers)

    for value in ("1", "2"):
        await _save(client, logged_in_headers, flow_id, value)
    assert scheduled == []

    await _save(client, logged_in_headers, flow_id, "3")

    assert scheduled == [UUID(flow_id)]


async def test_maintenance_checkpoints_at_the_cadence(client: AsyncClient, logged_in_headers):
    flow_id = await _flow(client, logged_in_headers)
    for value in ("1", "2", "3"):
        await _save(client, logged_in_headers, flow_id, value)

    await _run(flow_id)

    assert await _system_checkpoints(flow_id) == [0, 3]
    assert graphs_equal(await _reconstruct(flow_id, 3), _graph("3"))


async def test_a_checkpoint_is_never_taken_from_data_edited_outside_the_api(client: AsyncClient, logged_in_headers):
    flow_id = await _flow(client, logged_in_headers)
    for value in ("1", "2", "3"):
        await _save(client, logged_in_headers, flow_id, value)
    async with session_scope() as session:
        await session.exec(update(Flow).where(Flow.id == UUID(flow_id)).values(data=_graph("tampered")))

    await _run(flow_id)

    assert await _system_checkpoints(flow_id) == [0]


async def test_compaction_keeps_the_window_and_the_row_that_produced_the_cutoff(
    client: AsyncClient, logged_in_headers, thresholds
):
    flow_id = await _flow(client, logged_in_headers)
    for value in range(1, 10):
        await _save(client, logged_in_headers, flow_id, str(value))
        await _run(flow_id)

    earliest_start, earliest_end = await _retained(flow_id)
    checkpoints = await _system_checkpoints(flow_id)
    # Nine revisions, a window of five: revisions up to the checkpoint at 3 were
    # compacted away, keeping the row that ends at it.
    assert earliest_end in checkpoints
    assert checkpoints[0] == earliest_end
    assert 9 - earliest_start + 1 >= thresholds.flow_revision_retention_window
    for revision in range(earliest_end, 10):
        assert graphs_equal(await _reconstruct(flow_id, revision), _graph(str(revision)))


async def test_revisions_before_the_cutoff_are_not_retained(client: AsyncClient, logged_in_headers):
    flow_id = await _flow(client, logged_in_headers)
    for value in range(1, 10):
        await _save(client, logged_in_headers, flow_id, str(value))
        await _run(flow_id)
    _, cutoff = await _retained(flow_id)

    with pytest.raises(FlowRevisionNotRetainedError):
        await _reconstruct(flow_id, cutoff - 1)
    response = await client.get(f"api/v1/flows/{flow_id}/revisions/{cutoff - 1}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_410_GONE
    assert response.json()["detail"]["code"] == "FLOW_REVISION_NOT_RETAINED"


async def test_a_saved_version_below_the_cutoff_stays_readable(client: AsyncClient, logged_in_headers):
    flow_id = await _flow(client, logged_in_headers)
    await _save(client, logged_in_headers, flow_id, "1")
    version = await client.post(f"api/v1/flows/{flow_id}/versions/", json={}, headers=logged_in_headers)
    assert version.json()["operation_revision"] == 1
    for value in range(2, 12):
        await _save(client, logged_in_headers, flow_id, str(value))
        await _run(flow_id)

    assert graphs_equal(await _reconstruct(flow_id, 1), _graph("1"))
    listed = (await client.get(f"api/v1/flows/{flow_id}/versions/", headers=logged_in_headers)).json()["entries"]
    assert [entry["id"] for entry in listed] == [version.json()["id"]]


async def test_purge_leaves_only_a_checkpoint_of_the_current_flow(client: AsyncClient, logged_in_headers):
    flow_id = await _flow(client, logged_in_headers)
    for value in ("1", "2"):
        await _save(client, logged_in_headers, flow_id, value)

    response = await client.post(f"api/v1/flows/{flow_id}/revisions/purge", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["earliest_revision"] is None
    assert await _retained(flow_id) == (None, None)
    assert await _system_checkpoints(flow_id) == [2]
    assert graphs_equal(await _reconstruct(flow_id, 2), _graph("2"))
    # History continues from the purged state.
    history = await _save(client, logged_in_headers, flow_id, "3")
    assert history["start_revision"] == 3
    assert graphs_equal(await _reconstruct(flow_id, 3), _graph("3"))


async def _run(flow_id: str) -> None:
    await maintenance.perform_maintenance(UUID(flow_id))
