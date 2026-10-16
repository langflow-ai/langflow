"""Packaging a flow from a saved version (``flow_versions``), against a real database."""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.deployment_artifacts import (
    ProjectArtifactError,
    ProjectArtifactNotFoundError,
    build_project_artifact,
)

MODULE = "langflow.services.deployment_artifacts.builder"


def _graph(variable: str) -> dict:
    return {
        "nodes": [
            {"data": {"node": {"template": {"api_key": {"name": "api_key", "load_from_db": True, "value": variable}}}}}
        ],
        "edges": [],
    }


async def _project(session):
    owner_id = uuid4()
    project = Folder(id=uuid4(), name="Support", user_id=owner_id)
    picked = Flow(id=uuid4(), name="Echo", endpoint_name="echo", user_id=owner_id, folder_id=project.id)
    picked.data = _graph("DRAFT_KEY")
    other = Flow(id=uuid4(), name="FAQ", user_id=owner_id, folder_id=project.id, data=_graph("FAQ_KEY"))
    version = FlowVersion(flow_id=picked.id, user_id=owner_id, version_number=1, data=_graph("SAVED_KEY"))
    session.add_all([project, picked, other, version])
    await session.commit()
    return SimpleNamespace(id=owner_id, is_superuser=False), project, picked, other, version


async def _build(session, user, project, **kwargs):
    with (
        patch(f"{MODULE}.authorized_or_owner_scoped", new_callable=AsyncMock, return_value=project),
        patch(f"{MODULE}.ensure_project_permission", new_callable=AsyncMock),
        patch(f"{MODULE}.ensure_flows_permission", new_callable=AsyncMock),
    ):
        return await build_project_artifact(session, user, project.id, **kwargs)


@pytest.mark.asyncio
async def test_picked_flow_ships_its_version_graph_with_the_live_rows_fields(async_session) -> None:
    user, project, picked, other, version = await _project(async_session)

    artifact = await _build(async_session, user, project, flow_versions={picked.id: version.id})

    entries = {flow.flow_id: flow for flow in artifact.flows}
    assert entries[picked.id].version_id == version.id
    assert entries[other.id].version_id is None
    # Requirements come from the graph that ships, not the draft.
    assert entries[picked.id].required_variables == ("SAVED_KEY",)
    assert entries[other.id].required_variables == ("FAQ_KEY",)
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        exported = json.loads(archive.read(f"flows/{picked.id}.json"))
        manifest = json.loads(archive.read("manifest.json"))
    assert exported["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] == "SAVED_KEY"
    assert (exported["name"], exported["endpoint_name"]) == ("Echo", "echo")
    assert manifest["required_variables"] == ["FAQ_KEY", "SAVED_KEY"]
    assert all("version_id" not in flow for flow in manifest["flows"])
    # The draft is untouched.
    await async_session.refresh(picked)
    assert picked.data == _graph("DRAFT_KEY")


@pytest.mark.asyncio
async def test_without_a_pick_every_flow_ships_its_live_graph(async_session) -> None:
    user, project, picked, _other, _version = await _project(async_session)

    artifact = await _build(async_session, user, project)

    assert all(flow.version_id is None for flow in artifact.flows)
    assert {flow.flow_id: flow.required_variables for flow in artifact.flows}[picked.id] == ("DRAFT_KEY",)


@pytest.mark.asyncio
async def test_a_version_of_another_flow_is_refused(async_session) -> None:
    user, project, picked, other, version = await _project(async_session)

    with pytest.raises(ProjectArtifactNotFoundError, match="is not a version of flow"):
        await _build(async_session, user, project, flow_versions={other.id: version.id})
    with pytest.raises(ProjectArtifactNotFoundError, match="is not a version of flow"):
        await _build(async_session, user, project, flow_versions={picked.id: uuid4()})


@pytest.mark.asyncio
async def test_a_pick_for_a_flow_not_being_packaged_is_refused(async_session) -> None:
    user, project, picked, other, version = await _project(async_session)

    with pytest.raises(ProjectArtifactNotFoundError, match="not among the flows being packaged"):
        await _build(async_session, user, project, flow_ids=[other.id], flow_versions={picked.id: version.id})
    with pytest.raises(ProjectArtifactNotFoundError, match="not among the flows being packaged"):
        await _build(async_session, user, project, flow_versions={uuid4(): version.id})


@pytest.mark.asyncio
async def test_a_version_without_a_graph_is_refused(async_session) -> None:
    user, project, picked, _other, version = await _project(async_session)
    version.data = None
    async_session.add(version)
    await async_session.commit()

    with pytest.raises(ProjectArtifactError, match="has no graph data"):
        await _build(async_session, user, project, flow_versions={picked.id: version.id})
