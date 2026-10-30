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
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.variable.model import Variable
from langflow.services.deployment_artifacts import (
    ProjectArtifactError,
    ProjectArtifactLimits,
    ProjectArtifactNotFoundError,
    build_project_artifact,
)
from langflow.services.variable.constants import CREDENTIAL_TYPE

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
    variables = [
        Variable(name=name, value="test-value", type=CREDENTIAL_TYPE, user_id=owner_id)
        for name in ("DRAFT_KEY", "SAVED_KEY", "FAQ_KEY")
    ]
    session.add_all([project, picked, other, version, *variables])
    await session.commit()
    # Reload so updated_at matches what the packager's revision query returns.
    await session.refresh(picked)
    await session.refresh(other)
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


@pytest.mark.asyncio
async def test_a_version_graph_is_validated_like_a_live_one(async_session) -> None:
    user, project, picked, _other, version = await _project(async_session)
    version.data = {"foo": 1}
    async_session.add(version)
    await async_session.commit()

    with pytest.raises(ProjectArtifactError, match=r"is not a valid flow: .*Flow must have nodes"):
        await _build(async_session, user, project, flow_versions={picked.id: version.id})


@pytest.mark.asyncio
async def test_a_picked_flows_live_graph_is_neither_validated_nor_bounded(async_session) -> None:
    user, project, picked, _other, version = await _project(async_session)
    # A draft that fails validation and the size limit does not stop its version shipping.
    picked.data = {"nodes": [{"note": "x" * 4096}]}
    async_session.add(picked)
    await async_session.commit()
    await async_session.refresh(picked)

    artifact = await _build(
        async_session,
        user,
        project,
        flow_versions={picked.id: version.id},
        limits=ProjectArtifactLimits(max_flow_bytes=2048),
    )

    assert {flow.flow_id: flow.version_id for flow in artifact.flows}[picked.id] == version.id


@pytest.mark.asyncio
async def test_picks_resolve_on_every_page(async_session) -> None:
    user, project, _picked, _other, _version = await _project(async_session)
    flows = [
        Flow(id=uuid4(), name=f"Flow {index}", user_id=user.id, folder_id=project.id, data=_graph("DRAFT_KEY"))
        for index in range(9)
    ]
    versions = [
        FlowVersion(flow_id=flow.id, user_id=user.id, version_number=1, data=_graph(f"SAVED_{index}"))
        for index, flow in enumerate(flows)
    ]
    variables = [
        Variable(name=f"SAVED_{index}", value="test-value", type=CREDENTIAL_TYPE, user_id=user.id)
        for index in range(len(flows))
    ]
    async_session.add_all([*flows, *versions, *variables])
    await async_session.commit()
    for flow in flows:
        await async_session.refresh(flow)

    artifact = await _build(
        async_session,
        user,
        project,
        flow_versions={flow.id: version.id for flow, version in zip(flows, versions, strict=True)},
    )

    entries = {flow.flow_id: flow for flow in artifact.flows}
    for index, (flow, version) in enumerate(zip(flows, versions, strict=True)):
        assert entries[flow.id].version_id == version.id
        assert entries[flow.id].required_variables == (f"SAVED_{index}",)


@pytest.mark.asyncio
async def test_dependencies_resolve_from_the_version_graph(async_session) -> None:
    user, project, picked, _other, version = await _project(async_session)
    # The version still uses a Knowledge Base the live draft has dropped.
    kb = KnowledgeBaseRecord(
        name="docs",
        user_id=user.id,
        backend_type="opensearch",
        backend_config={"index_name": "d"},
        model_selection={"provider": "Ollama", "name": "nomic-embed-text"},
    )
    version.data = {"nodes": [{"data": {"node": {"template": {"knowledge_base": {"value": "docs"}}}}}], "edges": []}
    async_session.add_all([kb, version])
    await async_session.commit()

    with patch(f"{MODULE}.ensure_knowledge_base_permission", new_callable=AsyncMock):
        artifact = await _build(async_session, user, project, flow_versions={picked.id: version.id})
        live = await _build(async_session, user, project)

    assert [k["name"] for k in artifact.dependencies["knowledgeBases"]] == ["docs"]
    assert live.dependencies == {}


@pytest.mark.asyncio
async def test_an_invalid_live_graph_is_a_packaging_error(async_session) -> None:
    user, project, picked, _other, _version = await _project(async_session)
    picked.data = {"foo": 1}
    async_session.add(picked)
    await async_session.commit()
    await async_session.refresh(picked)

    with pytest.raises(ProjectArtifactError, match=rf"flow {picked.id} is not a valid flow: .*Flow must have nodes"):
        await _build(async_session, user, project)
