"""Reviewed cross-project tools execute snapshots and fail closed when references change."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.helpers.flow import get_tool_pack_flow
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.projects.bindings import flow_revision
from lfx.projects.tool_packs import ToolPackToolBinding
from lfx.projects.tools import TOOL_ORIGIN

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    echo_flow_data,
    save_config,
    stored_flow,
)


@pytest.fixture
async def pack_harness(client, logged_in_headers, active_user):
    pack = await create_project(client, logged_in_headers, name="Shared tools", project_type="tool-pack")
    source = await create_flow(active_user, folder_id=pack, name="Reusable lookup", data=echo_flow_data())
    await save_config(client, logged_in_headers, pack, {"tools": [source]})
    manifest = (await client.get(f"/api/v1/projects/{pack}/tool-pack", headers=logged_in_headers)).json()
    project = await create_project(client, logged_in_headers, name="Consumer")
    agent = await create_flow(active_user, folder_id=project, name="Consumer agent", data=agent_flow_data())
    config = {"agent_flow_id": agent, "tools": [], "tool_packs": [manifest["reference"]]}
    await save_config(client, logged_in_headers, project, config)
    return project, agent, pack, source, config


def pack_node(flow):
    return next(node for node in flow.data["nodes"] if node["data"].get(TOOL_ORIGIN, {}).get("tool_pack"))


async def test_pack_save_snapshots_exports_keeps_local_tools_and_clears_generated_nodes(
    client, logged_in_headers, active_user, pack_harness
):
    project, agent, _pack, source, config = pack_harness
    local = await create_flow(active_user, folder_id=project, name="Local lookup", data=echo_flow_data())
    await save_config(client, logged_in_headers, project, {**config, "tools": [local]})
    saved = await stored_flow(agent)
    origins = [node["data"][TOOL_ORIGIN] for node in saved.data["nodes"] if TOOL_ORIGIN in node["data"]]
    assert {origin["flow_id"] for origin in origins} == {source, local}
    binding = ToolPackToolBinding.model_validate(pack_node(saved)["data"][TOOL_ORIGIN]["tool_pack"])
    async with session_scope() as session:
        version = await session.get(FlowVersion, binding.version_id)
        assert version.flow_id == UUID(source)
        assert flow_revision(version.data) == binding.tool.revision
    definition = await get_tool_pack_flow(user_id=str(active_user.id), binding=binding)
    assert definition.data["data"] == (await stored_flow(source)).data
    await save_config(client, logged_in_headers, project, None)
    assert not any(TOOL_ORIGIN in node["data"] for node in (await stored_flow(agent)).data["nodes"])


async def test_stale_pack_fails_before_execution_and_review_refresh_preserves_layout(
    client, logged_in_headers, active_user, pack_harness
):
    project, agent, pack, source, config = pack_harness
    before = await stored_flow(agent)
    original_node = pack_node(before)
    original_binding = ToolPackToolBinding.model_validate(original_node["data"][TOOL_ORIGIN]["tool_pack"])
    async with session_scope() as session:
        canvas = await session.get(Flow, UUID(agent))
        canvas_data = deepcopy(canvas.data)
        opened = next(node for node in canvas_data["nodes"] if TOOL_ORIGIN in node["data"])
        opened["data"]["node"]["lf_version"] = "1.13.0"
        canvas.data = canvas_data
        session.add(canvas)
        row = await session.get(Flow, UUID(source))
        row.description = "A reviewed description change"
        session.add(row)
    before = await stored_flow(agent)
    with pytest.raises(ValueError, match="tool pack changed"):
        await get_tool_pack_flow(user_id=str(active_user.id), binding=original_binding)
    response = await client.patch(
        f"/api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": config}
    )
    assert response.status_code == 422, response.text
    assert (await stored_flow(agent)).data == before.data
    manifest = (await client.get(f"/api/v1/projects/{pack}/tool-pack", headers=logged_in_headers)).json()
    updated_config = {**config, "tool_packs": [manifest["reference"]]}
    await save_config(client, logged_in_headers, project, updated_config)
    after = await stored_flow(agent)
    updated_node = pack_node(after)
    assert updated_node["id"] == original_node["id"]
    assert updated_node["position"] == original_node["position"]
    assert after.data["edges"] == before.data["edges"]
    updated_binding = ToolPackToolBinding.model_validate(updated_node["data"][TOOL_ORIGIN]["tool_pack"])
    assert updated_binding.reference.revision != original_binding.reference.revision
    assert updated_binding.version_id == original_binding.version_id  # Same executable definition.
    await get_tool_pack_flow(user_id=str(active_user.id), binding=updated_binding)


async def test_pack_refresh_protects_canvas_edits(client, logged_in_headers, pack_harness):
    project, agent, pack, source, config = pack_harness
    async with session_scope() as session:
        row = await session.get(Flow, UUID(agent))
        data = deepcopy(row.data)
        generated = next(node for node in data["nodes"] if TOOL_ORIGIN in node["data"])
        generated["data"]["node"]["template"]["session_id"]["value"] = "my-independent-edit"
        row.data = data
        session.add(row)
    await save_config(client, logged_in_headers, project, config)
    edited = (await stored_flow(agent)).data
    async with session_scope() as session:
        row = await session.get(Flow, UUID(source))
        row.description = "Changed export"
        session.add(row)
    manifest = (await client.get(f"/api/v1/projects/{pack}/tool-pack", headers=logged_in_headers)).json()
    response = await client.patch(
        f"/api/v1/projects/{project}",
        headers=logged_in_headers,
        json={"project_config": {**config, "tool_packs": [manifest["reference"]]}},
    )
    assert response.status_code == 422, response.text
    assert "edited on the canvas" in response.json()["detail"]
    assert (await stored_flow(agent)).data == edited
    async with session_scope() as session:
        assert (await session.get(Folder, UUID(project))).project_config["tool_packs"] == config["tool_packs"]


async def test_snapshot_rejects_forged_missing_and_wrong_flow_versions(active_user, pack_harness):
    _project, agent, _pack, source, _config = pack_harness
    binding = ToolPackToolBinding.model_validate(pack_node(await stored_flow(agent))["data"][TOOL_ORIGIN]["tool_pack"])
    wrong = binding.model_copy(update={"version_id": uuid4()})
    with pytest.raises(ValueError, match="snapshot is unavailable"):
        await get_tool_pack_flow(user_id=str(active_user.id), binding=wrong)
    async with session_scope() as session:
        version = await session.get(FlowVersion, binding.version_id)
        version.flow_id = UUID(agent)
        version.version_number = 900
        session.add(version)
    with pytest.raises(ValueError, match="snapshot is unavailable"):
        await get_tool_pack_flow(user_id=str(active_user.id), binding=binding)
    async with session_scope() as session:
        version = await session.get(FlowVersion, binding.version_id)
        version.flow_id = UUID(source)
        version.data = {"nodes": [], "edges": []}
        session.add(version)
    with pytest.raises(ValueError, match="snapshot is unavailable"):
        await get_tool_pack_flow(user_id=str(active_user.id), binding=binding)


async def test_pack_save_and_execution_require_execute_permission(
    client, logged_in_headers, active_user, pack_harness, monkeypatch
):
    project, agent, _pack, _source, config = pack_harness
    binding = ToolPackToolBinding.model_validate(pack_node(await stored_flow(agent))["data"][TOOL_ORIGIN]["tool_pack"])
    actions = []

    async def deny_execute(_user, action, **_scope):
        actions.append(action.value)
        if action.value == "execute":
            raise HTTPException(403)

    monkeypatch.setattr("langflow.services.database.models.folder.tool_packs.ensure_flow_permission", deny_execute)
    response = await client.patch(
        f"/api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": config}
    )
    assert response.status_code == 404, response.text
    with pytest.raises(HTTPException) as error:
        await get_tool_pack_flow(user_id=str(active_user.id), binding=binding)
    assert error.value.status_code == 404
    assert actions == ["read", "execute", "read", "execute"]
