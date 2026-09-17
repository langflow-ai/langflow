"""Nested Tool Pack definitions stay reviewed, isolated, and callable after edits/resumes."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.api.utils.composition_zip import composition_zip, extract_composition
from langflow.helpers.flow import get_tool_pack_flow
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import session_scope
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.flow_builder import add_component, add_connection, empty_flow
from lfx.graph.graph.base import Graph
from lfx.projects.bindings import flow_revision
from lfx.projects.tool_packs import ToolPackToolBinding
from lfx.projects.tools import TOOL_ORIGIN, prepare_tool_template

from tests.unit.api.v1.test_harness_tool_packs import pack_node
from tests.unit.api.v1.test_project_composition_archives import download, upload
from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    echo_flow_data,
    save_config,
    stored_flow,
)


def nested_data(child):
    graph = Graph.from_payload(child["data"], instantiate_components=False)
    adapter = prepare_tool_template(child)
    adapter["outputs"] = [output.model_dump() for output in RunFlowComponent()._format_flow_outputs(graph)]
    adapter["add_tool_output"] = False
    registry = {"RunFlow": adapter}
    for cls in (ChatInput, ChatOutput):
        registry[cls.name] = cls().to_frontend_node()["data"]["node"]
        registry[cls.name]["field_order"] = [item.name for item in cls.inputs]
    parent = empty_flow("Nested lookup")
    add_component(parent, "ChatInput", registry, component_id="ChatInput-parent")
    add_component(parent, "RunFlow", registry, component_id="RunFlow-child")
    add_component(parent, "ChatOutput", registry, component_id="ChatOutput-parent")
    add_connection(
        parent, "ChatInput-parent", "message", "RunFlow-child", "ChatInput-echo~input_value", registry=registry
    )
    add_connection(
        parent, "RunFlow-child", "ChatOutput-echo~message", "ChatOutput-parent", "input_value", registry=registry
    )
    return parent["data"]


@pytest.fixture(params=[False, True], ids=["same-project", "cross-project"])
async def nested_pack(client, logged_in_headers, active_user, request):
    pack = await create_project(client, logged_in_headers, name="Nested tools", project_type="tool-pack")
    child_project = (
        await create_project(client, logged_in_headers, name="Shared flows", project_type="flows")
        if request.param
        else pack
    )
    child = await create_flow(active_user, folder_id=child_project, name="Inner source", data=echo_flow_data())
    source = await create_flow(
        active_user,
        folder_id=pack,
        name="Nested source",
        data=nested_data(
            {
                "id": child,
                "name": "Inner source",
                "data": (await stored_flow(child)).data,
            }
        ),
    )
    await save_config(client, logged_in_headers, pack, {"tools": [source]})
    manifest = (await client.get(f"api/v1/projects/{pack}/tool-pack", headers=logged_in_headers)).json()
    project = await create_project(client, logged_in_headers, name="Nested harness")
    agent = await create_flow(active_user, folder_id=project, name="Nested agent", data=agent_flow_data())
    config = {"agent_flow_id": agent, "tool_packs": [manifest["reference"]]}
    await save_config(client, logged_in_headers, project, config)
    return project, agent, pack, source, child, manifest


async def tools_from(agent_id, user_id, checkpoint=None):
    graph = (
        Graph.resume_from_checkpoint(checkpoint)
        if checkpoint
        else Graph.from_payload(
            deepcopy((await stored_flow(agent_id)).data),
            flow_id=agent_id,
            user_id=str(user_id),
            instantiate_components=False,
        )
    )
    if not checkpoint:
        graph.set_run_id(uuid4())
    data = (await stored_flow(agent_id)).data if not checkpoint else checkpoint.flow_payload
    node = next(node for node in data["nodes"] if node["data"].get(TOOL_ORIGIN))
    component = RunFlowComponent(_user_id=str(user_id), _vertex=graph.get_vertex(node["id"]))
    component.set_attributes(
        {key: entry.get("value") for key, entry in node["data"]["node"]["template"].items() if isinstance(entry, dict)}
    )
    return graph, await component._get_tools()


async def call(tool, value):
    return await tool.ainvoke({"flow_tweak_data": {"ChatInput-parent~input_value": value}})


async def change_child(child):
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(child))
        data = deepcopy(flow.data)
        field = data["nodes"][0]["data"]["node"]["template"]["code"]
        field["value"] = field["value"].replace("text=self.input_value,", 'text="changed: " + self.input_value,')
        assert field["value"] != flow.data["nodes"][0]["data"]["node"]["template"]["code"]["value"]
        flow.data = data
        session.add(flow)


async def test_nested_edits_change_manifest_but_not_compiled_tool_or_restored_run(
    client,
    logged_in_headers,
    active_user,
    nested_pack,
):
    from lfx.graph.checkpoint.builder import build_checkpoint
    from lfx.graph.checkpoint.schema import GraphCheckpoint

    project, agent, pack, _source, child, before = nested_pack
    assert [item["flow_id"] for item in before["tools"][0]["dependencies"]] == [child]
    saved = await stored_flow(agent)
    binding = ToolPackToolBinding.model_validate(pack_node(saved)["data"][TOOL_ORIGIN]["tool_pack"])
    assert len(binding.dependency_versions) == 1
    async with session_scope() as session:
        version = await session.get(FlowVersion, binding.dependency_versions[0].version_id)
        assert version.flow_id == UUID(child)
        assert flow_revision(version.data) == binding.tool.dependencies[0].revision
    graph, tools = await tools_from(agent, active_user.id)
    assert "original call" in str(await call(tools[0], "original call"))
    checkpoint = GraphCheckpoint.model_validate_json(build_checkpoint(graph).model_dump_json())
    await change_child(child)
    after = (await client.get(f"api/v1/projects/{pack}/tool-pack", headers=logged_in_headers)).json()
    assert after["reference"]["revision"] != before["reference"]["revision"]
    assert after["tools"][0]["revision"] == before["tools"][0]["revision"]
    assert "changed:" not in str(await call(tools[0], "still frozen"))
    _, restored = await tools_from(agent, active_user.id, checkpoint)
    assert "changed:" not in str(await call(restored[0], "after restart"))
    with pytest.raises(ValueError, match="tool pack changed"):
        await tools_from(agent, active_user.id)
    await save_config(
        client,
        logged_in_headers,
        project,
        {
            "agent_flow_id": agent,
            "tool_packs": [after["reference"]],
        },
    )
    _, refreshed = await tools_from(agent, active_user.id)
    assert "changed: reviewed call" in str(await call(refreshed[0], "reviewed call"))


async def test_nested_composition_round_trip_creates_fresh_dependency_versions(
    client,
    logged_in_headers,
    active_user,
    nested_pack,
):
    project, _agent, _pack, _source, child, _manifest = nested_pack
    response = await upload(client, logged_in_headers, await download(client, logged_in_headers, project))
    assert response.status_code == 201, response.text
    agent = response.json()[0]["id"]
    imported = await stored_flow(agent)
    binding = ToolPackToolBinding.model_validate(pack_node(imported)["data"][TOOL_ORIGIN]["tool_pack"])
    assert str(binding.dependency_versions[0].flow.flow_id) != child
    _, tools = await tools_from(agent, active_user.id)
    assert "portable nested call" in str(await call(tools[0], "portable nested call"))


async def test_nested_snapshots_reject_missing_forged_and_incomplete_versions(active_user, nested_pack):
    _project, agent, _pack, _source, _child, _manifest = nested_pack
    binding = ToolPackToolBinding.model_validate(pack_node(await stored_flow(agent))["data"][TOOL_ORIGIN]["tool_pack"])
    incomplete = binding.model_copy(update={"dependency_versions": ()})
    with pytest.raises(ValueError, match="snapshots are incomplete"):
        await get_tool_pack_flow(user_id=str(active_user.id), binding=incomplete)
    wrong = binding.model_copy(
        update={"dependency_versions": (binding.dependency_versions[0].model_copy(update={"version_id": uuid4()}),)}
    )
    with pytest.raises(ValueError, match="snapshot is unavailable"):
        await get_tool_pack_flow(user_id=str(active_user.id), binding=wrong)
    async with session_scope() as session:
        version = await session.get(FlowVersion, binding.dependency_versions[0].version_id)
        version.data = {"nodes": [], "edges": []}
        session.add(version)
    with pytest.raises(ValueError, match="snapshot is unavailable"):
        await get_tool_pack_flow(user_id=str(active_user.id), binding=binding)


async def test_resumed_tool_still_requires_current_access_to_nested_flow(active_user, nested_pack, monkeypatch):
    from lfx.graph.checkpoint.builder import build_checkpoint

    _project, agent, _pack, _source, child, _manifest = nested_pack
    graph, tools = await tools_from(agent, active_user.id)
    assert "before revoke" in str(await call(tools[0], "before revoke"))
    checkpoint = build_checkpoint(graph)

    async def deny_child(_user, action, **scope):
        if str(scope.get("flow_id")) == child and action.value == "execute":
            raise HTTPException(403)

    monkeypatch.setattr("langflow.services.database.models.folder.tool_packs.ensure_flow_permission", deny_child)
    with pytest.raises(HTTPException) as error:
        await tools_from(agent, active_user.id, checkpoint)
    assert error.value.status_code == 404


async def test_invalid_nested_reference_has_a_safe_review_error(client, logged_in_headers, nested_pack):
    _project, _agent, pack, source, _child, _manifest = nested_pack
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(source))
        data = deepcopy(flow.data)
        node = next(node for node in data["nodes"] if node["id"] == "RunFlow-child")
        node["data"]["node"]["template"]["flow_id_selected"]["value"] = "invalid-id"
        flow.data = data
        session.add(flow)
    response = await client.get(f"api/v1/projects/{pack}/tool-pack", headers=logged_in_headers)
    assert response.status_code == 409
    assert response.json() == {"detail": "The tool pack has invalid dependencies. Review its configuration."}


@pytest.mark.parametrize("duplicate", [False, True], ids=["missing-snapshot", "duplicate-snapshot"])
async def test_archive_rejects_incomplete_nested_snapshots(client, logged_in_headers, nested_pack, duplicate):
    project, agent, _pack, _source, _child, _manifest = nested_pack
    composition = await extract_composition(await download(client, logged_in_headers, project))
    root = next(item for item in composition.projects if str(item.id) == project)
    flow = next(item for item in root.flows if item["id"] == agent)
    node = next(item for item in flow["data"]["nodes"] if item["data"].get(TOOL_ORIGIN))
    binding = node["data"][TOOL_ORIGIN]["tool_pack"]
    versions = binding["dependency_versions"]
    binding["dependency_versions"] = versions * 2 if duplicate else []
    response = await upload(client, logged_in_headers, composition_zip(composition).getvalue())
    assert response.status_code == 422, response.text
    assert "snapshots are incomplete" in response.json()["detail"]


async def test_nested_tool_description_is_reviewed_and_frozen(client, logged_in_headers, active_user, nested_pack):
    _project, agent, pack, _source, child, before = nested_pack
    binding = ToolPackToolBinding.model_validate(pack_node(await stored_flow(agent))["data"][TOOL_ORIGIN]["tool_pack"])
    original = binding.tool.dependencies[0].description
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(child))
        flow.description = "New instructions for a nested tool call."
        session.add(flow)
    after = (await client.get(f"api/v1/projects/{pack}/tool-pack", headers=logged_in_headers)).json()
    assert after["reference"] != before["reference"]
    assert after["tools"][0]["revision"] == before["tools"][0]["revision"]
    with pytest.raises(ValueError, match="tool pack changed"):
        await get_tool_pack_flow(user_id=str(active_user.id), binding=binding)
    restored = await get_tool_pack_flow(user_id=str(active_user.id), binding=binding, require_current=False)
    assert restored.data["dependencies"][child]["description"] == original
