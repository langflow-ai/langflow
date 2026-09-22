"""Exercise the Instructions binding through real persistence, graph execution, and import."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.models_and_agents.prompt import PromptComponent
from lfx.graph.graph.base import Graph
from lfx.projects.baselines import instructions_baseline
from lfx.projects.bindings import BINDING_ORIGIN, flow_revision, instruction_outputs
from lfx.schema.message import Message
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
    data = instructions_baseline(text)["data"]
    node = data["nodes"][0]
    node["id"] = node["data"]["id"] = "Prompt-test"
    if not text.strip():
        node["data"]["node"]["template"]["template"]["value"] = text
    return data


def prompt_data(text="Use primary sources. Today is {{current_date}}."):
    component = PromptComponent(template=text)
    data = component.to_frontend_node()["data"]
    data["id"] = "Prompt-test"
    return {"nodes": [{"id": data["id"], "data": data}], "edges": []}


async def setup_binding(client, headers, user, *, data=None):
    project_id = await create_project(client, headers, name="Instructions harness")
    agent_id = await create_flow(user, folder_id=project_id, data=agent_flow_data(), name="Agent")
    source = instructions_data() if data is None else data
    source_id = await create_flow(user, folder_id=project_id, data=source, name="Research instructions")
    output = instruction_outputs(source)[0]
    binding = {
        "flow_id": source_id,
        "node_id": output["node_id"],
        "output_name": output["output_name"],
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
    result = await invoke_binding(agent, active_user)
    assert isinstance(result, Message)
    assert result.text == "Use primary sources. Today is {current_date}."
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


@pytest.mark.parametrize("source", [instructions_data, prompt_data])
async def test_bound_output_reaches_the_model_with_agent_placeholders(client, logged_in_headers, active_user, source):
    project, agent_id, source_id, config = await setup_binding(client, logged_in_headers, active_user, data=source())
    original = deepcopy((await stored_flow(source_id)).data)
    choices = await client.get(f"api/v1/projects/{project}/flow-outputs", headers=logged_in_headers)
    assert any(choice["flow_id"] == source_id for choice in choices.json())
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
    assert (await stored_flow(source_id)).data == original


@pytest.mark.parametrize("returned", ["Message(text='  ')", "{'text': 'not a Message'}", "['not a Message']"])
async def test_prompt_message_contract_is_checked_at_runtime(client, logged_in_headers, active_user, returned):
    source = prompt_data()
    template = source["nodes"][0]["data"]["node"]["template"]
    template["code"]["value"] = template["code"]["value"].replace("return prompt", f"return {returned}")
    project, agent, _, config = await setup_binding(client, logged_in_headers, active_user, data=source)
    await save_config(client, logged_in_headers, project, config)
    with pytest.raises(ValueError, match="non-empty text"):
        await invoke_binding(agent, active_user)


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
    template["code"]["value"] = template["code"]["value"].replace("return prompt", f"return {returned}")
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
    assert (await stored_template(source))["template"]["value"].startswith("Use primary sources")


@pytest.mark.parametrize("factory", [instructions_data, prompt_data])
async def test_source_edits_require_review_before_execution(client, logged_in_headers, active_user, factory):
    project, agent, source, config = await setup_binding(client, logged_in_headers, active_user, data=factory())
    await save_config(client, logged_in_headers, project, config)
    updated = factory("Updated research instructions")
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
    value = await invoke_binding(agent, active_user)
    assert (value.text if isinstance(value, Message) else value) == "Updated research instructions"


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
    assert response.json()[0]["node_id"] == "Prompt-test"
    assert agent not in [choice["flow_id"] for choice in response.json()]
    assert (await client.get(f"api/v1/projects/{uuid4()}/flow-outputs", headers=logged_in_headers)).status_code == 404


@pytest.mark.parametrize("factory", [instructions_data, prompt_data])
async def test_archive_import_remaps_binding_while_source_project_remains(
    client, logged_in_headers, active_user, factory
):
    project, agent, source, config = await setup_binding(client, logged_in_headers, active_user, data=factory())
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
    imported_value = await invoke_binding(imported_agent["id"], active_user)
    original_value = await invoke_binding(agent, active_user)
    assert type(imported_value) is type(original_value)
    assert (imported_value.text if isinstance(imported_value, Message) else imported_value) == (
        original_value.text if isinstance(original_value, Message) else original_value
    )


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


async def test_instructions_baseline_creates_a_callable_flow_through_normal_api(client, logged_in_headers, active_user):
    project = await create_project(client, logged_in_headers, name="Baseline harness")
    response = await client.post(
        f"api/v1/projects/{project}/flow-baseline",
        headers=logged_in_headers,
        json={"initial_value": "Use the form draft. Today is {current_date}."},
    )
    assert response.status_code == 200, response.text
    baseline = response.json()
    node = baseline["data"]["nodes"][0]
    assert node["type"] == "genericNode"
    assert node["position"] == {"x": 300, "y": 150}
    created = await client.post("api/v1/flows/", headers=logged_in_headers, json=baseline)
    assert created.status_code == 201, created.text
    source = created.json()["id"]
    choices = await client.get(f"api/v1/projects/{project}/flow-outputs", headers=logged_in_headers)
    output = next(choice for choice in choices.json() if choice["flow_id"] == source)
    binding = {key: output[key] for key in ("flow_id", "node_id", "output_name", "revision")}
    agent = await create_flow(active_user, folder_id=project, data=agent_flow_data())
    await save_config(
        client,
        logged_in_headers,
        project,
        {
            "agent_flow_id": agent,
            "flow_bindings": {"system_prompt": binding},
        },
    )
    value = await invoke_binding(agent, active_user)
    assert isinstance(value, Message)
    assert value.text == "Use the form draft. Today is {current_date}."
    # Naming and placement still belong to ordinary flow creation.
    another = await client.post("api/v1/flows/", headers=logged_in_headers, json=baseline)
    assert another.status_code == 201
    assert another.json()["name"] != created.json()["name"]
    assert another.json()["folder_id"] == project


@pytest.mark.parametrize("initial_value", [None, "", "   "])
async def test_instructions_baseline_defaults_are_ready_to_run(client, logged_in_headers, initial_value):
    project = await create_project(client, logged_in_headers, name="Default baseline")
    response = await client.post(
        f"api/v1/projects/{project}/flow-baseline", headers=logged_in_headers, json={"initial_value": initial_value}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    checked = await client.post(
        f"api/v1/projects/{project}/flow-outputs/validate", headers=logged_in_headers, json={"data": data}
    )
    assert checked.json()["valid"] is True
    assert checked.json()["outputs"][0]["output_name"] == "prompt"


async def test_draft_contract_check_neither_executes_nor_saves_code(client, logged_in_headers, active_user):
    project, _, source, _ = await setup_binding(client, logged_in_headers, active_user)
    original = deepcopy((await stored_flow(source)).data)
    draft = deepcopy(original)
    draft["nodes"][0]["data"]["node"]["template"]["code"]["value"] = "raise RuntimeError('must never execute')"
    endpoint = f"api/v1/projects/{project}/flow-outputs/validate"
    checked = await client.post(endpoint, headers=logged_in_headers, json={"data": draft})
    assert checked.status_code == 200
    assert checked.json()["valid"] is True
    draft["nodes"][0]["data"]["node"]["template"]["template"]["value"] = ""
    assert (await client.post(endpoint, headers=logged_in_headers, json={"data": draft})).json()["valid"] is False
    assert (await client.post(endpoint, headers=logged_in_headers, json={"data": {"nodes": [], "edges": []}})).json()[
        "valid"
    ] is False
    assert (await stored_flow(source)).data == original


async def test_baseline_and_validation_reject_foreign_projects_and_unsupported_fields(
    client, logged_in_headers, user_two
):
    project = await create_project(client, logged_in_headers, name="Scoped baseline")
    async with session_scope() as session:
        foreign = Folder(name="Foreign baseline", user_id=user_two.id, project_type="agent-harness")
        session.add(foreign)
        await session.flush()
        foreign_id = foreign.id
    for suffix, payload in [("flow-baseline", {}), ("flow-outputs/validate", {"data": {}})]:
        response = await client.post(f"api/v1/projects/{foreign_id}/{suffix}", headers=logged_in_headers, json=payload)
        assert response.status_code == 404
        response = await client.post(f"api/v1/projects/{uuid4()}/{suffix}", headers=logged_in_headers, json=payload)
        assert response.status_code == 404
        response = await client.post(
            f"api/v1/projects/{project}/{suffix}?field_name=tools", headers=logged_in_headers, json=payload
        )
        assert response.status_code == 422
