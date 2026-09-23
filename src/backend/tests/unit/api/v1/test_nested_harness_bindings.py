"""A reviewed customization includes the nested definitions that produce its output."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.helpers.flow import get_harness_flow
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import session_scope
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.input_output.text_output import TextOutputComponent
from lfx.components.models_and_agents.prompt import PromptComponent
from lfx.graph.flow_builder import add_component, add_connection, empty_flow
from lfx.graph.graph.base import Graph
from lfx.projects.bindings import BINDING_ORIGIN, FlowBinding

from tests.unit.api.v1.test_project_composition_archives import download, upload
from tests.unit.api.v1.test_project_config_write_through import create_flow, save_config, stored_flow
from tests.unit.api.v1.test_project_instruction_bindings import instructions_data, invoke_binding, setup_binding


def flow_reference(child):
    graph = Graph.from_payload(child["data"], instantiate_components=False)
    component = RunFlowComponent()
    adapter = component.to_frontend_node()["data"]["node"]
    adapter["template"]["flow_id_selected"]["value"] = child["id"]
    adapter["template"]["flow_name_selected"]["value"] = child["name"]
    adapter["outputs"] = [output.model_dump() for output in component._format_flow_outputs(graph)]
    adapter["field_order"] = [field.name for field in component.inputs]
    flow = empty_flow("Reference")
    add_component(flow, "RunFlow", {"RunFlow": adapter}, component_id="RunFlow-child")
    return flow["data"]["nodes"][0]


def nested_instructions(child):
    output = PromptComponent(template="{rules}").to_frontend_node()["data"]["node"]
    registry = {"Prompt Template": output}
    parent = empty_flow("Composed instructions")
    parent["data"]["nodes"].append(flow_reference(child))
    add_component(parent, "Prompt Template", registry, component_id="Prompt-test")
    add_connection(
        parent,
        "RunFlow-child",
        "TextOutput-rules~text",
        "Prompt-test",
        "rules",
        registry=registry,
    )
    return parent["data"]


def rule_flow_data(text):
    flow = {"data": instructions_data(text)}
    output = TextOutputComponent().to_frontend_node()["data"]["node"]
    add_component(flow, "TextOutput", {"TextOutput": output}, component_id="TextOutput-rules")
    add_connection(flow, "Prompt-test", "prompt", "TextOutput-rules", "input_value")
    return flow["data"]


@pytest.fixture(params=[False, True], ids=["local-child", "separate-project-child"])
async def nested_customization(client, logged_in_headers, active_user, request):
    from tests.unit.api.v1.test_project_config_write_through import create_project

    project, agent, source, config = await setup_binding(client, logged_in_headers, active_user)
    child_project = (
        await create_project(client, logged_in_headers, name="Shared rules", project_type="flows")
        if request.param
        else project
    )
    child = await create_flow(
        active_user, folder_id=child_project, name="Instruction rules", data=rule_flow_data("Original rules")
    )
    async with session_scope() as session:
        parent = await session.get(Flow, UUID(source))
        parent.data = nested_instructions(
            {"id": child, "name": "Instruction rules", "data": deepcopy((await stored_flow(child)).data)}
        )
        session.add(parent)
    response = await client.get(f"api/v1/projects/{project}/flow-outputs", headers=logged_in_headers)
    choice = next(item for item in response.json() if item["flow_id"] == source)
    config["flow_bindings"]["system_prompt"] = {
        key: value for key, value in choice.items() if key not in {"flow_name", "display_name"}
    }
    saved = await save_config(client, logged_in_headers, project, config)
    binding = FlowBinding.model_validate(saved["project_config"]["flow_bindings"]["system_prompt"])
    assert [item.flow_id for item in binding.dependencies] == [child]
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(binding.dependencies[0].version_id))
        assert version.flow_id == UUID(child)
    return project, agent, source, child, binding, config


async def change_rules(child):
    async with session_scope() as session:
        changed = await session.get(Flow, UUID(child))
        changed.data = rule_flow_data("Changed rules")
        session.add(changed)


async def test_nested_instruction_edit_requires_review_before_execution(
    client, logged_in_headers, active_user, nested_customization
):
    project, agent, source, child, binding, config = nested_customization
    assert (await invoke_binding(agent, active_user)).text == "Original rules"
    await change_rules(child)
    with pytest.raises(ValueError, match=r"[Dd]ependen|changed"):
        await invoke_binding(agent, active_user)
    response = await client.patch(
        f"api/v1/projects/{project}", json={"project_config": config}, headers=logged_in_headers
    )
    assert response.status_code == 422
    choices = (await client.get(f"api/v1/projects/{project}/flow-outputs", headers=logged_in_headers)).json()
    current = next(item for item in choices if item["flow_id"] == source)
    assert current["revision"] == binding.revision
    assert current["dependencies"][0]["revision"] != binding.dependencies[0].revision
    config["flow_bindings"]["system_prompt"] = {
        key: value for key, value in current.items() if key not in {"flow_name", "display_name"}
    }
    forged = str(uuid4())
    config["flow_bindings"]["system_prompt"]["dependencies"][0]["version_id"] = forged
    saved = await save_config(client, logged_in_headers, project, config)
    assert saved["project_config"]["flow_bindings"]["system_prompt"]["dependencies"][0]["version_id"] != forged
    assert (await invoke_binding(agent, active_user)).text == "Changed rules"


async def bound_component(agent, user, checkpoint=None):
    graph = (
        Graph.resume_from_checkpoint(checkpoint)
        if checkpoint
        else Graph.from_payload(
            deepcopy((await stored_flow(agent)).data), flow_id=agent, user_id=str(user.id), instantiate_components=False
        )
    )
    if checkpoint is None:
        graph.set_run_id(uuid4())
    node = next(node for node in graph.raw_graph_data["nodes"] if node["data"].get(BINDING_ORIGIN))
    component = RunFlowComponent(_user_id=str(user.id), _vertex=graph.get_vertex(node["id"]))
    component.set_attributes(
        {key: value.get("value") for key, value in node["data"]["node"]["template"].items() if isinstance(value, dict)}
    )
    return graph, component


async def test_restored_customization_retains_nested_versions_and_checks_access(
    active_user, nested_customization, monkeypatch
):
    from lfx.graph.checkpoint.builder import build_checkpoint
    from lfx.graph.checkpoint.schema import GraphCheckpoint

    _project, agent, _source, child, _binding, _config = nested_customization
    graph, component = await bound_component(agent, active_user)
    assert (
        await component._resolve_flow_output(vertex_id="Prompt-test", output_name="prompt")
    ).text == "Original rules"
    checkpoint = GraphCheckpoint.model_validate_json(build_checkpoint(graph).model_dump_json())
    await change_rules(child)
    _, restored = await bound_component(agent, active_user, checkpoint)
    assert (await restored._resolve_flow_output(vertex_id="Prompt-test", output_name="prompt")).text == "Original rules"

    async def deny_child(_user, action, **scope):
        if str(scope.get("flow_id")) == child and action.value == "execute":
            raise HTTPException(403)

    monkeypatch.setattr("langflow.services.database.models.folder.flow_bindings.ensure_flow_permission", deny_child)
    _, denied = await bound_component(agent, active_user, checkpoint)
    with pytest.raises(HTTPException) as error:
        await denied.get_graph(flow_id_selected=denied.flow_id_selected)
    assert error.value.status_code == 404


async def test_customization_archive_remaps_required_nested_versions(
    client, logged_in_headers, active_user, nested_customization
):
    project, _agent, _source, child, binding, _config = nested_customization
    response = await upload(client, logged_in_headers, await download(client, logged_in_headers, project))
    assert response.status_code == 201, response.text[:500]
    imported_agent = response.json()[0]["id"]
    _graph, component = await bound_component(imported_agent, active_user)
    imported_binding = component._instruction_binding()
    assert imported_binding.dependencies[0].flow_id != child
    assert imported_binding.dependencies[0].version_id != binding.dependencies[0].version_id
    assert (
        await component._resolve_flow_output(vertex_id="Prompt-test", output_name="prompt")
    ).text == "Original rules"


async def test_nested_customization_json_import_preserves_local_dependencies(
    client, logged_in_headers, active_user, nested_customization
):
    import json

    project, _agent, _source, _child, _binding, _config = nested_customization
    data = (await client.get(f"api/v1/projects/{project}", headers=logged_in_headers)).json()
    payload = {
        "folder_name": "Imported rules",
        "folder_project_type": "agent-harness",
        "folder_project_config": data["project_config"],
        "flows": data["flows"],
    }
    response = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("rules.json", json.dumps(payload), "application/json")},
    )
    if len(data["flows"]) == 2:
        # The legacy single-project format cannot carry a child from another project.
        assert response.status_code == 422
        return
    assert response.status_code == 201, response.text[:500]
    imported = next(
        flow for flow in response.json() if any(node["data"].get(BINDING_ORIGIN) for node in flow["data"]["nodes"])
    )
    assert (await invoke_binding(imported["id"], active_user)).text == "Original rules"


async def test_customization_rejects_missing_nested_snapshot(active_user, nested_customization):
    _project, _agent, _source, _child, binding, _config = nested_customization
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(binding.dependencies[0].version_id))
        await session.delete(version)
    with pytest.raises(ValueError, match="snapshot is unavailable"):
        await get_harness_flow(user_id=str(active_user.id), binding=binding, field_name="system_prompt")


async def test_hook_executes_its_nested_text_definition_and_records_it(client, logged_in_headers, active_user):
    from lfx.components.input_output import TextOutputComponent

    from tests.unit.api.v1.test_project_hook_bindings import run_stored_agent, setup_hooks

    project, agent, source, config = await setup_hooks(client, logged_in_headers, active_user)
    text = TextOutputComponent()
    text.set(input_value="Original rules")
    node = text.to_frontend_node()["data"]
    node["id"] = "TextOutput-rules"
    child = await create_flow(
        active_user,
        folder_id=project,
        name="Hook rules",
        data={"nodes": [{"id": node["id"], "data": node}], "edges": []},
    )
    child_flow = await stored_flow(child)
    async with session_scope() as session:
        parent = await session.get(Flow, UUID(source))
        data = deepcopy(parent.data)
        data["nodes"].append(flow_reference({"id": child, "name": child_flow.name, "data": child_flow.data}))
        hook = next(node for node in data["nodes"] if node["data"].get("type") == "Hook")
        add_connection({"data": data}, "RunFlow-child", "TextOutput-rules~text", hook["id"], "reason")
        parent.data = data
        session.add(parent)
    choices = (
        await client.get(f"api/v1/projects/{project}/flow-outputs?field_name=hooks", headers=logged_in_headers)
    ).json()
    choice = next(item for item in choices if item["flow_id"] == source)
    config["flow_bindings"]["hooks"][0].update(
        {key: value for key, value in choice.items() if key not in {"flow_name", "display_name"}}
    )
    saved = await save_config(client, logged_in_headers, project, config)
    result = await run_stored_agent(agent, active_user)
    assert "Original rules" in str(result)
    recorded = result["properties"]["agent_run_result"]["configurations"][0]["flow_bindings"]["hooks"][0]
    assert recorded["dependencies"] == saved["project_config"]["flow_bindings"]["hooks"][0]["dependencies"]
    assert recorded["dependencies"][0]["flow_id"] == child
    assert recorded["dependencies"][0]["version_id"]
