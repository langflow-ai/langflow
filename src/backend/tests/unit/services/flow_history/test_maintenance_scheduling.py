"""A write that crosses the checkpoint cadence starts maintenance once its transaction commits."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import status
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.flow_history import maintenance
from sqlmodel import col, select

if TYPE_CHECKING:
    from httpx import AsyncClient


def _graph(value: str) -> dict:
    return {"nodes": [{"id": "a", "data": {"node": {"template": {"t": {"value": value}}}}}], "edges": []}


async def test_crossing_the_cadence_checkpoints_in_the_background(client: AsyncClient, logged_in_headers, monkeypatch):
    monkeypatch.setattr(get_settings_service().settings, "flow_revision_checkpoint_cadence", 2)
    response = await client.post(
        "api/v1/flows/", json={"name": f"bg-{uuid4().hex[:8]}", "data": _graph("0")}, headers=logged_in_headers
    )
    flow_id = response.json()["id"]

    for value in ("1", "2"):
        saved = await client.patch(f"api/v1/flows/{flow_id}", json={"data": _graph(value)}, headers=logged_in_headers)
        assert saved.status_code == status.HTTP_200_OK

    # The save returned without waiting; the task it scheduled runs on its own.
    await asyncio.gather(*list(maintenance._tasks))

    async with session_scope() as session:
        revisions = (
            await session.exec(
                select(FlowVersion.operation_revision).where(
                    FlowVersion.flow_id == UUID(flow_id), col(FlowVersion.version_number).is_(None)
                )
            )
        ).all()
    assert sorted(revisions) == [0, 2]
