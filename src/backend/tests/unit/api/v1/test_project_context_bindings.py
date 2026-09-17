"""Context customization persists and executes through project saves and archive import."""

import json
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.graph.graph.base import Graph
from lfx.projects.baselines import context_baseline, hook_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.context import CONTEXT_ORIGIN, context_outputs
from lfx.projects.hooks import hook_outputs
from lfx.schema.message import MessageResponse
from sqlmodel import select

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    save_config,
    stored_flow,
    stored_template,
)
from tests.unit.api.v1.test_project_instruction_bindings import RecordingModel, instructions_data


async def setup_context(client, headers, user):
    project = await create_project(client, headers, name="Context harness")
    agent = await create_flow(user, folder_id=project, data=agent_flow_data(), name="Agent")
    data = context_baseline()["data"]
    template = data["nodes"][-1]["data"]["node"]["template"]
    template["code"]["value"] = template["code"]["value"].replace(
        "return messages_to_table(prepared)",
        'prepared[-1] = prepared[-1].model_copy(update={"content": "Use primary sources."})\n'
        "        return messages_to_table(prepared)",
    )
    source = await create_flow(user, folder_id=project, data=data, name="Context")
    selected = context_outputs(data)[0]
    binding = {
        "flow_id": source,
        "revision": flow_revision(data),
        "timeout_seconds": 5,
        "node_id": selected["node_id"],
        "output_name": selected["output_name"],
    }
    return (
        project,
        agent,
        source,
        {
            "agent_flow_id": agent,
            "context_strategy": "recent_turns",
            "context_turns": 2,
            "flow_bindings": {"context_strategy": binding},
        },
    )


async def run_context_agent(agent, user):
    model = RecordingModel()
    graph = Graph.from_payload(deepcopy((await stored_flow(agent)).data), user_id=str(user.id))
    graph.session_id = f"context-binding-{agent}"
    vertex = graph.get_vertex("Agent-1")
    assert json.loads(vertex.params["context_binding"])
    vertex.update_raw_params(
        {
            "model": model,
            "input_value": "Research",
            "n_messages": 0,
            "add_current_date_tool": False,
            "add_calculator_tool": False,
        },
        overwrite=True,
    )
    results = [result async for result in graph.async_start()]
    assert all(getattr(result, "valid", True) for result in results)
    assert model.seen[-1][-1].content == "Use primary sources."
    return model, MessageResponse.from_message(vertex.custom_component.get_output("response").value).model_dump()


async def test_context_save_snapshots_source_and_executes_without_rewriting_it(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_context(client, logged_in_headers, active_user)
    before = deepcopy((await stored_flow(source)).data)
    config["flow_bindings"]["context_strategy"]["version_id"] = str(uuid4())
    saved = await save_config(client, logged_in_headers, project, config)
    binding = saved["project_config"]["flow_bindings"]["context_strategy"]
    assert saved["restore_version_ids"]
    assert binding["version_id"] != config["flow_bindings"]["context_strategy"]["version_id"]
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(binding["version_id"]))
        assert str(version.flow_id) == source
        assert version.data == before
    assert (await stored_flow(source)).data == before
    repeated = await save_config(client, logged_in_headers, project, config)
    assert repeated["flows_updated"] == 0
    assert repeated["project_config"] == saved["project_config"]
    _, public = await run_context_agent(agent, active_user)
    assert "context_prepared" in str(public)
    assert binding["revision"] in str(public)
    assert binding["version_id"] in str(public)
    # Scalar preferences remain available for removing the binding later.
    assert (await stored_template(agent))["context_strategy"]["value"] == "recent_turns"


async def add_other_bindings(user, project, config):
    instructions = instructions_data()
    source = await create_flow(user, folder_id=project, data=instructions, name="Instructions")
    config["flow_bindings"]["system_prompt"] = {
        "flow_id": source,
        "node_id": "SystemPromptBuilder-test",
        "output_name": "instructions",
        "revision": flow_revision(instructions),
    }
    hook = hook_baseline()["data"]
    source = await create_flow(user, folder_id=project, data=hook, name="Hook")
    output = hook_outputs(hook)[0]
    config["flow_bindings"]["hooks"] = [
        {
            "flow_id": source,
            "node_id": output["node_id"],
            "output_name": output["output_name"],
            "revision": flow_revision(hook),
            "on_event": "before_llm_call",
        }
    ]


async def test_context_clears_independently_and_preserves_instructions_hooks_and_scalar_preferences(
    client,
    logged_in_headers,
    active_user,
):
    project, agent, _, config = await setup_context(client, logged_in_headers, active_user)
    await add_other_bindings(active_user, project, config)
    await save_config(client, logged_in_headers, project, config)
    model, public = await run_context_agent(agent, active_user)
    assert model.seen[-1][0].content.startswith("Use primary sources. Today is ")
    assert "{current_date}" not in model.seen[-1][0].content
    assert "hook_completed" in str(public)
    context = config["flow_bindings"].pop("context_strategy")
    saved = await save_config(client, logged_in_headers, project, config)
    assert set(saved["project_config"]["flow_bindings"]) == {"system_prompt", "hooks"}
    template = await stored_template(agent)
    assert template["context_binding"]["value"] == ""
    assert template["context_strategy"]["value"] == "recent_turns"
    assert template["context_turns"]["value"] == 2
    assert json.loads(template["hook_bindings"]["value"])
    config["flow_bindings"]["context_strategy"] = context
    await save_config(client, logged_in_headers, project, config)
    await save_config(client, logged_in_headers, project, None)
    assert (await stored_template(agent))["context_binding"]["value"] == ""
    assert not any(node["data"].get(CONTEXT_ORIGIN) for node in (await stored_flow(agent)).data["nodes"])


@pytest.mark.parametrize(
    "defect",
    ["foreign_project", "foreign_user", "self", "output", "revision", "timeout", "shape", "canvas", "old_agent"],
)
async def test_invalid_context_binding_rolls_back_save(client, logged_in_headers, active_user, defect):
    project, agent, source, config = await setup_context(client, logged_in_headers, active_user)
    binding = config["flow_bindings"]["context_strategy"]
    if defect in {"foreign_project", "foreign_user", "canvas", "old_agent"}:
        async with session_scope() as session:
            flow = await session.get(Flow, UUID(agent if defect in {"canvas", "old_agent"} else source))
            if defect == "foreign_project":
                flow.folder_id = None
            elif defect == "foreign_user":
                flow.user_id = None
            else:
                data = deepcopy(flow.data)
                template = data["nodes"][0]["data"]["node"]["template"]
                if defect == "old_agent":
                    template.pop("context_binding")
                else:
                    template["context_binding"]["value"] = '{"manual":true}'
                flow.data = data
            await session.commit()
    elif defect == "shape":
        config["flow_bindings"]["context_strategy"] = [binding]
    else:
        key, value = {
            "self": ("flow_id", agent),
            "output": ("output_name", "missing"),
            "revision": ("revision", "unreviewed"),
            "timeout": ("timeout_seconds", 0),
        }[defect]
        binding[key] = value
    before = deepcopy((await stored_flow(agent)).data)
    response = await client.patch(
        f"api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": config}
    )
    assert response.status_code == 422, response.text
    assert (await stored_flow(agent)).data == before
    async with session_scope() as session:
        assert (await session.get(Folder, UUID(project))).project_config is None


async def test_context_discovery_baseline_and_draft_validation_are_scoped(client, logged_in_headers, active_user):
    project, _, source, _ = await setup_context(client, logged_in_headers, active_user)
    suffix = "?field_name=context_strategy"
    choices = await client.get(f"api/v1/projects/{project}/flow-outputs{suffix}", headers=logged_in_headers)
    assert choices.status_code == 200
    assert [choice["flow_id"] for choice in choices.json()] == [source]
    baseline = await client.post(f"api/v1/projects/{project}/flow-baseline{suffix}", headers=logged_in_headers, json={})
    assert baseline.status_code == 200, baseline.text
    flow = baseline.json()
    assert flow["folder_id"] == project
    assert flow["data"]["harness_contract"] == {"field_name": "context_strategy", "slot": "ContextManager"}
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["code"]["value"] = "raise RuntimeError('must not execute')"
    endpoint = f"api/v1/projects/{project}/flow-outputs/validate{suffix}"
    valid = await client.post(endpoint, headers=logged_in_headers, json={"data": flow["data"]})
    assert valid.json()["valid"]
    flow["data"]["edges"] = []
    invalid = await client.post(endpoint, headers=logged_in_headers, json={"data": flow["data"]})
    assert not invalid.json()["valid"]
    assert "Agent Context" in invalid.json()["reason"]
    foreign = await client.get(f"api/v1/projects/{uuid4()}/flow-outputs{suffix}", headers=logged_in_headers)
    assert foreign.status_code == 404


async def test_context_baseline_uses_the_form_settings_and_rejects_invalid_turns(client, logged_in_headers):
    project = await create_project(client, logged_in_headers, name="Context baseline")
    endpoint = f"api/v1/projects/{project}/flow-baseline?field_name=context_strategy"
    response = await client.post(
        endpoint,
        headers=logged_in_headers,
        json={"initial_config": {"context_strategy": "recent_turns", "context_turns": 3}},
    )
    assert response.status_code == 200, response.text
    template = response.json()["data"]["nodes"][-1]["data"]["node"]["template"]
    assert template["strategy"]["value"] == "recent_turns"
    assert template["turns"]["value"] == 3
    invalid = await client.post(endpoint, headers=logged_in_headers, json={"initial_config": {"context_turns": 0}})
    assert invalid.status_code == 422, invalid.text


async def test_context_archive_preserves_all_three_contracts_with_original_project_present(
    client,
    logged_in_headers,
    active_user,
):
    project, agent, source, config = await setup_context(client, logged_in_headers, active_user)
    await add_other_bindings(active_user, project, config)
    saved = await save_config(client, logged_in_headers, project, config)
    exported = await client.get(f"api/v1/projects/download/{project}", headers=logged_in_headers)
    assert exported.status_code == 200
    imported = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("context.zip", exported.content, "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    flows = imported.json()
    assert not {flow["id"] for flow in flows}.intersection({agent, source})
    new_agent = next(flow for flow in flows if any(node["data"].get(CONTEXT_ORIGIN) for node in flow["data"]["nodes"]))
    binding = json.loads((await stored_template(new_agent["id"]))["context_binding"]["value"])
    assert binding["flow_id"] in {flow["id"] for flow in flows}
    assert binding["version_id"] != saved["project_config"]["flow_bindings"]["context_strategy"]["version_id"]
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(binding["version_id"]))
        assert str(version.flow_id) == binding["flow_id"]
        imported_project = await session.get(Folder, UUID(new_agent["folder_id"]))
        imported_config = deepcopy(imported_project.project_config)
    assert set(imported_config["flow_bindings"]) == {"system_prompt", "hooks", "context_strategy"}
    assert (await save_config(client, logged_in_headers, new_agent["folder_id"], imported_config))["flows_updated"] == 0
    model, public = await run_context_agent(new_agent["id"], active_user)
    assert model.seen[-1][0].content.startswith("Use primary sources. Today is ")
    assert "{current_date}" not in model.seen[-1][0].content
    assert "hook_completed" in str(public)
    assert binding["version_id"] in str(public)


async def test_context_source_changes_require_review_before_save_or_import(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_context(client, logged_in_headers, active_user)
    first = await save_config(client, logged_in_headers, project, config)
    before = deepcopy((await stored_flow(agent)).data)
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(source))
        data = deepcopy(flow.data)
        data["nodes"][-1]["data"]["node"]["template"]["turns"]["value"] = 3
        flow.data = data
        await session.commit()
    rejected = await client.patch(
        f"api/v1/projects/{project}", json={"project_config": config}, headers=logged_in_headers
    )
    assert rejected.status_code == 422
    assert (await stored_flow(agent)).data == before
    exported = await client.get(f"api/v1/projects/download/{project}", headers=logged_in_headers)
    assert exported.status_code == 422, exported.text
    # Legacy JSON uploads must still reject stale bindings independently of export.
    current = (await client.get(f"api/v1/projects/{project}", headers=logged_in_headers)).json()
    payload = {
        "folder_name": "Stale binding import",
        "folder_project_type": "agent-harness",
        "folder_project_config": current["project_config"],
        "flows": current["flows"],
    }
    imported = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("stale.json", json.dumps(payload).encode(), "application/json")},
    )
    assert imported.status_code == 422, imported.text
    config["flow_bindings"]["context_strategy"]["revision"] = flow_revision(data)
    updated = await save_config(client, logged_in_headers, project, config)
    assert (
        updated["project_config"]["flow_bindings"]["context_strategy"]["version_id"]
        != first["project_config"]["flow_bindings"]["context_strategy"]["version_id"]
    )
    await run_context_agent(agent, active_user)


async def test_required_context_snapshot_failure_rolls_back_every_write(
    client, logged_in_headers, active_user, monkeypatch
):
    from langflow.services.database.models.folder import config_writer

    project, agent, source, config = await setup_context(client, logged_in_headers, active_user)
    before = deepcopy((await stored_flow(agent)).data)
    original = config_writer.create_flow_version_entry

    async def fail_after_snapshot(*args, **kwargs):
        await original(*args, **kwargs)
        msg = "Snapshot storage failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(config_writer, "create_flow_version_entry", fail_after_snapshot)
    response = await client.patch(
        f"api/v1/projects/{project}", json={"project_config": config}, headers=logged_in_headers
    )
    assert response.status_code == 500
    assert (await stored_flow(agent)).data == before
    async with session_scope() as session:
        assert (await session.get(Folder, UUID(project))).project_config is None
        assert not (await session.exec(select(FlowVersion).where(FlowVersion.flow_id == UUID(source)))).all()
