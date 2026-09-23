"""Local harness tools retain the definitions reviewed by the configuring user."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import session_scope
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.graph.graph.base import Graph
from lfx.projects.tools import TOOL_ORIGIN

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    echo_flow_data,
    save_config,
    stored_flow,
)


async def local_component(agent, user, checkpoint=None):
    graph = (
        Graph.resume_from_checkpoint(checkpoint)
        if checkpoint
        else Graph.from_payload(
            deepcopy((await stored_flow(agent)).data),
            flow_id=agent,
            user_id=str(user.id),
            instantiate_components=False,
        )
    )
    if checkpoint is None:
        graph.set_run_id(uuid4())
    node = next(node for node in graph.raw_graph_data["nodes"] if node["data"].get(TOOL_ORIGIN))
    component = RunFlowComponent(_vertex=graph.get_vertex(node["id"]), _user_id=str(user.id))
    component.set_attributes(
        {key: value.get("value") for key, value in node["data"]["node"]["template"].items() if isinstance(value, dict)}
    )
    return component


@pytest.fixture
async def local_harness(client, logged_in_headers, active_user):
    project = await create_project(client, logged_in_headers, name="Reviewed local tools")
    agent = await create_flow(active_user, folder_id=project, name="Agent", data=agent_flow_data())
    tool = await create_flow(active_user, folder_id=project, name="Echo", data=echo_flow_data())
    saved = await save_config(client, logged_in_headers, project, {"agent_flow_id": agent, "tools": [tool]})
    return project, agent, tool, saved["project_config"]


@pytest.mark.parametrize("change", ["name", "description", "definition"])
async def test_local_tool_contract_edit_requires_review(client, logged_in_headers, active_user, local_harness, change):
    project, agent, tool, config = local_harness
    original = await local_component(agent, active_user)
    tools = await original._get_tools()
    assert "hello" in str(await tools[0].ainvoke({"flow_tweak_data": {"ChatInput-echo~input_value": "hello"}}))
    async with session_scope() as session:
        changed = await session.get(Flow, UUID(tool))
        if change == "definition":
            data = deepcopy(changed.data)
            data["nodes"][-1]["data"]["node"]["template"]["sender_name"]["value"] = "Reviewed author"
            changed.data = data
        else:
            setattr(changed, change, "Changed tool contract")
        session.add(changed)
    refreshed = await local_component(agent, active_user)
    with pytest.raises(ValueError, match=r"changed|review|Review"):
        await refreshed._get_tools()
    # Omitting review metadata, or supplying the old value, cannot silently accept a change.
    for request in (config, {"agent_flow_id": agent, "tools": [tool]}):
        response = await client.patch(
            f"api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": request}
        )
        assert response.status_code == 422
    choices = (await client.get(f"api/v1/projects/{project}/tool-definitions", headers=logged_in_headers)).json()
    current = next(item for item in choices if item["flow_id"] == tool)
    current["version_id"] = str(uuid4())
    saved = await save_config(client, logged_in_headers, project, {**config, "tool_bindings": {tool: current}})
    assert saved["project_config"]["tool_bindings"][tool]["version_id"] != current["version_id"]
    assert await (await local_component(agent, active_user))._get_tools()


async def test_local_tool_checkpoint_retains_definition_and_checks_current_access(
    active_user, local_harness, monkeypatch
):
    from fastapi import HTTPException
    from lfx.graph.checkpoint.builder import build_checkpoint
    from lfx.graph.checkpoint.schema import GraphCheckpoint

    _project, agent, tool, config = local_harness
    original = await local_component(agent, active_user)
    await original._get_tools()
    checkpoint = GraphCheckpoint.model_validate_json(build_checkpoint(original.graph).model_dump_json())
    async with session_scope() as session:
        source = await session.get(Flow, UUID(tool))
        source.name = "Renamed after pause"
        source.data = {"nodes": [], "edges": []}
        session.add(source)
    restored = await local_component(agent, active_user, checkpoint)
    callable_tools = await restored._get_tools()
    assert "hello" in str(await callable_tools[0].ainvoke({"flow_tweak_data": {"ChatInput-echo~input_value": "hello"}}))
    assert callable_tools[0].metadata["harness_local_tool"] == config["tool_bindings"][tool]

    async def deny_child(_user, action, **scope):
        if str(scope.get("flow_id")) == tool and action.value == "execute":
            raise HTTPException(403)

    monkeypatch.setattr("langflow.services.database.models.folder.flow_bindings.ensure_flow_permission", deny_child)
    denied = await local_component(agent, active_user, checkpoint)
    with pytest.raises(HTTPException) as error:
        await denied._get_tools()
    assert error.value.status_code == 404


async def upload_json(client, headers, project):
    import json

    data = (await client.get(f"api/v1/projects/{project}", headers=headers)).json()
    payload = {
        "folder_name": "Imported local tools",
        "folder_project_type": "agent-harness",
        "folder_project_config": data["project_config"],
        "flows": data["flows"],
    }
    return await client.post(
        "api/v1/projects/upload/",
        headers=headers,
        files={"file": ("local-tools.json", json.dumps(payload), "application/json")},
    )


@pytest.mark.parametrize("format_name", ["zip", "json"])
async def test_local_tool_import_allocates_new_bindings(
    client, logged_in_headers, active_user, local_harness, format_name
):
    from tests.unit.api.v1.test_project_composition_archives import download, upload

    project, _agent, tool, config = local_harness
    if format_name == "zip":
        response = await upload(client, logged_in_headers, await download(client, logged_in_headers, project))
    else:
        response = await upload_json(client, logged_in_headers, project)
    assert response.status_code == 201, response.text[:500]
    imported_agent = next(
        flow for flow in response.json() if any(node["data"].get(TOOL_ORIGIN) for node in flow["data"]["nodes"])
    )
    component = await local_component(imported_agent["id"], active_user)
    tools = await component._get_tools()
    binding = tools[0].metadata["harness_local_tool"]
    assert binding["flow_id"] != tool
    assert binding["version_id"] != config["tool_bindings"][tool]["version_id"]
    assert "imported hello" in str(
        await tools[0].ainvoke({"flow_tweak_data": {"ChatInput-echo~input_value": "imported hello"}})
    )


async def test_local_tool_missing_snapshot_fails_execution_and_export(
    client, logged_in_headers, active_user, local_harness
):
    project, agent, tool, config = local_harness
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(config["tool_bindings"][tool]["version_id"]))
        await session.delete(version)
    with pytest.raises(ValueError, match="snapshot"):
        await (await local_component(agent, active_user))._get_tools()
    response = await client.get(f"api/v1/projects/download/{project}", headers=logged_in_headers)
    assert response.status_code == 422


@pytest.mark.parametrize("cross_project", [False, True])
async def test_nested_local_tool_review_resume_and_handoff(client, logged_in_headers, active_user, cross_project):
    from lfx.graph.checkpoint.builder import build_checkpoint
    from lfx.graph.checkpoint.schema import GraphCheckpoint

    from tests.unit.api.v1.test_project_composition_archives import download, upload
    from tests.unit.api.v1.test_transitive_tool_snapshots import call, change_child, nested_data

    project = await create_project(client, logged_in_headers, name="Nested local tools")
    child_project = (
        await create_project(client, logged_in_headers, name="Shared source", project_type="flows")
        if cross_project
        else project
    )
    child = await create_flow(active_user, folder_id=child_project, name="Inner source", data=echo_flow_data())
    source = await stored_flow(child)
    tool = await create_flow(
        active_user,
        folder_id=project,
        name="Nested local tool",
        data=nested_data({"id": child, "name": source.name, "data": source.data}),
    )
    agent = await create_flow(active_user, folder_id=project, name="Agent", data=agent_flow_data())
    saved = await save_config(client, logged_in_headers, project, {"agent_flow_id": agent, "tools": [tool]})
    binding = saved["project_config"]["tool_bindings"][tool]
    original = await local_component(agent, active_user)
    tools = await original._get_tools()
    assert "first" in str(await call(tools[0], "first"))
    checkpoint = GraphCheckpoint.model_validate_json(build_checkpoint(original.graph).model_dump_json())
    await change_child(child)
    with pytest.raises(ValueError, match="dependencies changed"):
        await (await local_component(agent, active_user))._get_tools()
    restored = await (await local_component(agent, active_user, checkpoint))._get_tools()
    answer = str(await call(restored[0], "still original"))
    assert "still original" in answer
    assert "changed:" not in answer
    choices = (await client.get(f"api/v1/projects/{project}/tool-definitions", headers=logged_in_headers)).json()
    current = next(item for item in choices if item["flow_id"] == tool)
    assert current["revision"] == binding["revision"]
    assert current["dependencies"][0]["revision"] != binding["dependencies"][0]["revision"]
    updated = await save_config(
        client, logged_in_headers, project, {**saved["project_config"], "tool_bindings": {tool: current}}
    )
    refreshed = await (await local_component(agent, active_user))._get_tools()
    assert "changed: reviewed" in str(await call(refreshed[0], "reviewed"))
    response = await upload(client, logged_in_headers, await download(client, logged_in_headers, project))
    assert response.status_code == 201, response.text[:500]
    imported = next(
        flow for flow in response.json() if any(node["data"].get(TOOL_ORIGIN) for node in flow["data"]["nodes"])
    )
    tools = await (await local_component(imported["id"], active_user))._get_tools()
    imported_binding = tools[0].metadata["harness_local_tool"]
    assert imported_binding["dependencies"][0]["flow_id"] != child
    assert (
        imported_binding["dependencies"][0]["version_id"]
        != updated["project_config"]["tool_bindings"][tool]["dependencies"][0]["version_id"]
    )
    assert "changed: imported" in str(await call(tools[0], "imported"))
    json_response = await upload_json(client, logged_in_headers, project)
    if cross_project:
        # Legacy JSON is limited to the root project's files.
        assert json_response.status_code == 422
    else:
        assert json_response.status_code == 201, json_response.text[:500]
        imported = next(
            flow
            for flow in json_response.json()
            if any(node["data"].get(TOOL_ORIGIN) for node in flow["data"]["nodes"])
        )
        tools = await (await local_component(imported["id"], active_user))._get_tools()
        assert "changed: json" in str(await call(tools[0], "json"))


async def test_completed_agent_records_its_reviewed_local_tool(client, logged_in_headers, active_user, local_harness):
    from langchain_core.messages import AIMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from lfx.components.files_and_knowledge.sourced_report import SourcedReportComponent
    from lfx.graph.flow_builder import add_component, add_connection

    from tests.unit.api.v1.test_project_instruction_bindings import RecordingModel

    class CallingModel(RecordingModel):
        tool_name: str = ""

        def bind_tools(self, tools, **kwargs):  # noqa: ARG002
            self.tool_name = tools[0].name
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
            completed = [item for item in messages if isinstance(item, ToolMessage)]
            response = (
                AIMessage(content="Reviewed local result: " + str(completed[-1].content))
                if completed
                else AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "local-call",
                            "name": self.tool_name,
                            "args": {"flow_tweak_data": {"ChatInput-echo~input_value": "local evidence"}},
                        }
                    ],
                )
            )
            return ChatResult(generations=[ChatGeneration(message=response)])

    project, agent, tool, config = local_harness
    data = {"data": deepcopy((await stored_flow(agent)).data)}
    report_component = SourcedReportComponent(title="Local tool configuration proof", require_resolved=False)
    report_node = report_component.to_frontend_node()["data"]["node"]
    report_node["field_order"] = [field.name for field in report_component.inputs]
    registry = {"SourcedReport": report_node}
    add_component(data, "SourcedReport", registry, component_id="SourcedReport-local")
    add_connection(data, "Agent-1", "response", "SourcedReport-local", "report", registry=registry)
    async with session_scope() as session:
        source = await session.get(Flow, UUID(agent))
        source.data = data["data"]
        session.add(source)
    graph = Graph.from_payload(deepcopy((await stored_flow(agent)).data), flow_id=agent, user_id=str(active_user.id))
    graph.get_vertex("Agent-1").update_raw_params(
        {
            "model": CallingModel(),
            "input_value": "Record the configured tool.",
            "n_messages": 0,
            "add_current_date_tool": False,
            "add_calculator_tool": False,
        },
        overwrite=True,
    )
    results = [result async for result in graph.async_start()]
    assert all(result.valid for result in results if hasattr(result, "valid"))
    result = graph.get_vertex("Agent-1").custom_component.get_output("response").value.properties.agent_run_result
    recorded = result["configurations"][0]["tools"][0]["local_flow"]
    assert recorded == config["tool_bindings"][tool]
    artifact = graph.get_vertex("SourcedReport-local").custom_component.get_output("artifact").value.data["artifact"]
    assert "local evidence" in artifact["markdown"]
    assert artifact["configurations"][0]["tools"][0]["local_flow"] == recorded
    response = await client.get(
        f"api/v1/projects/{project}/reports/{agent}/{artifact['id']}", headers=logged_in_headers
    )
    assert response.status_code == 200
    assert response.json()["configurations"][0]["tools"][0]["local_flow"] == recorded
