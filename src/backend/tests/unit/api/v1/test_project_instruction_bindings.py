"""Exercise the Instructions binding through real persistence, graph execution, and import."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import session_scope
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.models_and_agents.system_prompt_builder import SystemPromptBuilderComponent
from lfx.graph.graph.base import Graph
from lfx.projects.bindings import BINDING_ORIGIN, flow_revision
from pydantic import Field

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    save_config,
    stored_flow,
    stored_template,
)


def instructions_data(text="Use primary sources. Today is {current_date}."):
    component = SystemPromptBuilderComponent()
    component.set(input_value=text)
    data = component.to_frontend_node()["data"]
    data["id"] = "SystemPromptBuilder-test"
    return {"nodes": [{"id": data["id"], "data": data}], "edges": []}


async def setup_binding(client, headers, user, *, data=None):
    project_id = await create_project(client, headers, name="Instructions harness")
    agent_id = await create_flow(user, folder_id=project_id, data=agent_flow_data(), name="Agent")
    source = instructions_data() if data is None else data
    source_id = await create_flow(user, folder_id=project_id, data=source, name="Research instructions")
    binding = {
        "flow_id": source_id,
        "node_id": "SystemPromptBuilder-test",
        "output_name": "instructions",
        "revision": flow_revision(source),
    }
    config = {
        "agent_flow_id": agent_id,
        "system_prompt": "Form instructions",
        "flow_bindings": {"system_prompt": binding},
    }
    return project_id, agent_id, source_id, config


async def invoke_binding(agent_id, user):
    data = (await stored_flow(agent_id)).data
    graph = Graph.from_payload(deepcopy(data), instantiate_components=False, user_id=str(user.id))
    node = next(node for node in data["nodes"] if node["data"].get(BINDING_ORIGIN))
    component = RunFlowComponent(_user_id=str(user.id), _vertex=graph.get_vertex(node["id"]))
    template = node["data"]["node"]["template"]
    component.set_attributes({key: entry.get("value") for key, entry in template.items() if isinstance(entry, dict)})
    binding = node["data"][BINDING_ORIGIN]
    return await component._resolve_flow_output(vertex_id=binding["node_id"], output_name=binding["output_name"])


async def test_binding_is_visible_callable_versioned_and_idempotent(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_binding(client, logged_in_headers, active_user)
    original = deepcopy((await stored_flow(source)).data)
    saved = await save_config(client, logged_in_headers, project, config)
    assert saved["flows_updated"] == 1
    assert saved["restore_version_ids"]
    stored = (await stored_flow(agent)).data
    generated = next(node for node in stored["nodes"] if node["data"].get(BINDING_ORIGIN))
    edge = next(edge for edge in stored["edges"] if edge["source"] == generated["id"])
    assert edge["data"]["targetHandle"]["fieldName"] == "system_prompt"
    assert (await stored_flow(source)).data == original
    assert (
        await invoke_binding(agent, active_user)
        == original["nodes"][0]["data"]["node"]["template"]["input_value"]["value"]
    )
    async with session_scope() as session:
        version = await session.get(
            FlowVersion, UUID(saved["project_config"]["flow_bindings"]["system_prompt"]["version_id"])
        )
        assert version.data == original
    again = await save_config(client, logged_in_headers, project, config)
    assert again["flows_updated"] == 0
    assert (await stored_flow(agent)).data == stored


class RecordingModel(BaseChatModel):
    seen: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "recording-model"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Research complete"))])


async def test_bound_output_reaches_the_model_with_agent_placeholders(client, logged_in_headers, active_user):
    project, agent_id, _, config = await setup_binding(client, logged_in_headers, active_user)
    await save_config(client, logged_in_headers, project, config)
    model = RecordingModel()
    graph = Graph.from_payload(deepcopy((await stored_flow(agent_id)).data), user_id=str(active_user.id))
    graph.get_vertex("Agent-1").update_raw_params(
        {
            "model": model,
            "input_value": "Research this question",
            "n_messages": 0,
            "add_current_date_tool": False,
            "add_calculator_tool": False,
        },
        overwrite=True,
    )
    results = [result async for result in graph.async_start()]
    built_agent = next(
        result for result in results if getattr(getattr(result, "vertex", None), "id", None) == "Agent-1"
    )
    assert built_agent.valid, built_agent.result_dict
    assert "Research complete" in str(built_agent.result_dict), built_agent.result_dict
    prompt = model.seen[0][0].content
    assert "Use primary sources." in prompt
    assert "{current_date}" not in prompt
    assert "UTC" in prompt


async def test_clearing_config_removes_its_generated_binding(client, logged_in_headers, active_user):
    project, agent, _, config = await setup_binding(client, logged_in_headers, active_user)
    await save_config(client, logged_in_headers, project, config)
    saved = await save_config(client, logged_in_headers, project, None)
    assert saved["project_config"] is None
    assert not any(node["data"].get(BINDING_ORIGIN) for node in (await stored_flow(agent)).data["nodes"])


@pytest.mark.parametrize("returned", ['""', '{"text": "Unexpected object"}', '["Unexpected list"]'])
async def test_runtime_rejects_values_that_violate_the_declared_text_contract(
    client, logged_in_headers, active_user, returned
):
    source = instructions_data()
    template = source["nodes"][0]["data"]["node"]["template"]
    template["code"]["value"] = template["code"]["value"].replace("return self.input_value", f"return {returned}")
    project, agent, _, config = await setup_binding(client, logged_in_headers, active_user, data=source)
    await save_config(client, logged_in_headers, project, config)
    with pytest.raises(ValueError, match="non-empty text"):
        await invoke_binding(agent, active_user)


async def test_unbinding_restores_form_value_without_changing_source(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_binding(client, logged_in_headers, active_user)
    await save_config(
        client, logged_in_headers, project, {"agent_flow_id": agent, "system_prompt": "Form instructions"}
    )
    await save_config(client, logged_in_headers, project, config)
    config["system_prompt"] = "Updated form instructions"
    await save_config(client, logged_in_headers, project, config)
    assert await invoke_binding(agent, active_user) != config["system_prompt"]
    assert (await stored_template(agent))["system_prompt"]["value"] == "Form instructions"
    config["flow_bindings"] = {}
    await save_config(client, logged_in_headers, project, config)
    assert (await stored_template(agent))["system_prompt"]["value"] == "Updated form instructions"
    assert not any(node["data"].get(BINDING_ORIGIN) for node in (await stored_flow(agent)).data["nodes"])
    assert (await stored_template(source))["input_value"]["value"].startswith("Use primary sources")


async def test_source_edits_require_review_before_execution(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_binding(client, logged_in_headers, active_user)
    await save_config(client, logged_in_headers, project, config)
    updated = instructions_data("Updated research instructions")
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(source))
        flow.data = updated
        await session.commit()
    with pytest.raises(ValueError, match="Instructions flow has changed"):
        await invoke_binding(agent, active_user)
    response = await client.patch(
        f"api/v1/projects/{project}", json={"project_config": config}, headers=logged_in_headers
    )
    assert response.status_code == 422
    config["flow_bindings"]["system_prompt"]["revision"] = flow_revision(updated)
    await save_config(client, logged_in_headers, project, config)
    assert await invoke_binding(agent, active_user) == "Updated research instructions"


@pytest.mark.parametrize("defect", ["foreign", "self", "missing_output", "required_input", "invalid_binding"])
async def test_invalid_binding_is_atomic(client, logged_in_headers, active_user, defect):
    project, agent, source, config = await setup_binding(client, logged_in_headers, active_user)
    before = deepcopy((await stored_flow(agent)).data)
    binding = config["flow_bindings"]["system_prompt"]
    if defect == "foreign":
        other = await create_project(client, logged_in_headers, name="Other project")
        binding["flow_id"] = await create_flow(active_user, folder_id=other, data=instructions_data())
    elif defect == "self":
        binding["flow_id"] = agent
    elif defect == "missing_output":
        binding["output_name"] = "removed"
    elif defect == "required_input":
        data = instructions_data("")
        async with session_scope() as session:
            flow = await session.get(Flow, UUID(source))
            flow.data = data
            await session.commit()
        binding["revision"] = flow_revision(data)
    else:
        config["flow_bindings"] = []
    response = await client.patch(
        f"api/v1/projects/{project}", json={"project_config": config}, headers=logged_in_headers
    )
    assert response.status_code == 422
    assert (await stored_flow(agent)).data == before


async def test_output_discovery_is_scoped_and_reports_explicit_outputs(client, logged_in_headers, active_user):
    project, agent, source, _ = await setup_binding(client, logged_in_headers, active_user)
    response = await client.get(f"api/v1/projects/{project}/flow-outputs", headers=logged_in_headers)
    assert response.status_code == 200
    assert [choice["flow_id"] for choice in response.json()] == [source]
    assert response.json()[0]["node_id"] == "SystemPromptBuilder-test"
    assert agent not in [choice["flow_id"] for choice in response.json()]
    assert (await client.get(f"api/v1/projects/{uuid4()}/flow-outputs", headers=logged_in_headers)).status_code == 404


async def test_archive_import_remaps_binding_while_source_project_remains(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_binding(client, logged_in_headers, active_user)
    await save_config(client, logged_in_headers, project, config)
    exported = await client.get(f"api/v1/projects/download/{project}", headers=logged_in_headers)
    assert exported.status_code == 200
    imported = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("research.zip", exported.content, "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    ids = {flow["id"] for flow in imported.json()}
    assert not ids.intersection({agent, source})
    imported_agent = next(
        flow for flow in imported.json() if any(node["data"].get(BINDING_ORIGIN) for node in flow["data"]["nodes"])
    )
    assert await invoke_binding(imported_agent["id"], active_user) == await invoke_binding(agent, active_user)


@pytest.mark.parametrize("defect", ["stale_revision", "invalid_bindings"])
async def test_archive_import_rejects_invalid_saved_bindings(client, logged_in_headers, active_user, defect):
    project, _, source, config = await setup_binding(client, logged_in_headers, active_user)
    await save_config(client, logged_in_headers, project, config)
    if defect == "stale_revision":
        async with session_scope() as session:
            flow = await session.get(Flow, UUID(source))
            flow.data = instructions_data("A change that has not been reviewed.")
            await session.commit()
    exported = await client.get(f"api/v1/projects/{project}", headers=logged_in_headers)
    project_data = exported.json()
    payload = {
        "folder_name": "Imported Instructions",
        "folder_project_type": "agent-harness",
        "folder_project_config": [] if defect == "invalid_bindings" else project_data["project_config"],
        "flows": project_data["flows"],
    }
    if defect == "invalid_bindings":
        payload["folder_project_config"] = {**config, "flow_bindings": []}
    import json

    response = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("instructions.json", json.dumps(payload).encode(), "application/json")},
    )
    assert response.status_code == 422, response.text
