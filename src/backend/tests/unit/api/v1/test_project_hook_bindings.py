"""Hook bindings save, execute, and import through the same APIs as Instructions."""

import json
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.graph.graph.base import Graph
from lfx.projects.baselines import hook_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.hooks import HOOK_ORIGIN, hook_outputs
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


async def setup_hooks(client, headers, user):
    project = await create_project(client, headers, name="Hook harness")
    agent = await create_flow(user, folder_id=project, data=agent_flow_data(), name="Agent")
    source_data = hook_baseline()["data"]
    source = await create_flow(user, folder_id=project, data=source_data, name="Audit hook")
    output = hook_outputs(source_data)[0]
    binding = {
        "flow_id": source,
        "node_id": output["node_id"],
        "output_name": output["output_name"],
        "revision": flow_revision(source_data),
        "on_event": "before_llm_call",
        "mode": "observe",
    }
    return project, agent, source, {"agent_flow_id": agent, "flow_bindings": {"hooks": [binding]}}


async def run_stored_agent(agent, user):
    model = RecordingModel()
    graph = Graph.from_payload(deepcopy((await stored_flow(agent)).data), user_id=str(user.id))
    graph.session_id = f"hook-test-{agent}"
    assert json.loads(graph.get_vertex("Agent-1").params["hook_bindings"])
    graph.get_vertex("Agent-1").update_raw_params(
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
    built = next(result for result in results if getattr(getattr(result, "vertex", None), "id", None) == "Agent-1")
    assert built.valid, built.result_dict
    assert model.seen
    # Inspect the actual response through the API serializer, not Data's display artifact.
    message = graph.get_vertex("Agent-1").custom_component.get_output("response").value
    return MessageResponse.from_message(message).model_dump()


async def test_hooks_save_versions_and_execute_from_the_stored_agent(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_hooks(client, logged_in_headers, active_user)
    before = deepcopy((await stored_flow(source)).data)
    config["flow_bindings"]["hooks"][0]["version_id"] = str(uuid4())
    saved = await save_config(client, logged_in_headers, project, config)
    binding = saved["project_config"]["flow_bindings"]["hooks"][0]
    assert saved["restore_version_ids"]
    assert binding["version_id"] != config["flow_bindings"]["hooks"][0]["version_id"]
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(binding["version_id"]))
        assert str(version.flow_id) == source
        assert version.data == before
    assert (await stored_flow(source)).data == before
    repeated = await save_config(client, logged_in_headers, project, config)
    assert repeated["flows_updated"] == 0
    assert repeated["project_config"] == saved["project_config"]
    built = await run_stored_agent(agent, active_user)
    assert "hook_completed" in str(built)
    assert binding["revision"] in str(built)


async def test_instructions_and_ordered_hooks_coexist_and_clear_independently(client, logged_in_headers, active_user):
    project, agent, _, config = await setup_hooks(client, logged_in_headers, active_user)
    instructions = instructions_data()
    source = await create_flow(active_user, folder_id=project, data=instructions, name="Instructions")
    config["flow_bindings"]["system_prompt"] = {
        "flow_id": source,
        "node_id": "Prompt-test",
        "output_name": "prompt",
        "revision": flow_revision(instructions),
    }
    config["flow_bindings"]["hooks"].append(
        {**config["flow_bindings"]["hooks"][0], "on_event": "after_llm_call", "priority": -10}
    )
    saved = await save_config(client, logged_in_headers, project, config)
    values = json.loads((await stored_template(agent))["hook_bindings"]["value"])
    assert [value["on_event"] for value in values] == ["before_llm_call", "after_llm_call"]
    assert values[0]["version_id"] == values[1]["version_id"]
    assert set(saved["project_config"]["flow_bindings"]) == {"system_prompt", "hooks"}
    config["flow_bindings"].pop("hooks")
    saved = await save_config(client, logged_in_headers, project, config)
    assert json.loads((await stored_template(agent))["hook_bindings"]["value"]) == []
    assert "system_prompt" in saved["project_config"]["flow_bindings"]
    await save_config(client, logged_in_headers, project, None)
    assert not any(node["data"].get(HOOK_ORIGIN) for node in (await stored_flow(agent)).data["nodes"])


@pytest.mark.parametrize(
    "defect", ["foreign_project", "foreign_user", "self", "output", "revision", "mode", "canvas", "old_agent"]
)
async def test_invalid_hooks_reject_the_whole_save(client, logged_in_headers, active_user, defect):
    project, agent, source, config = await setup_hooks(client, logged_in_headers, active_user)
    binding = config["flow_bindings"]["hooks"][0]
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
                    template.pop("hook_bindings")
                else:
                    template["hook_bindings"]["value"] = '[{"custom":true}]'
                flow.data = data
            await session.commit()
    elif defect == "self":
        binding["flow_id"] = agent
    elif defect == "output":
        binding["output_name"] = "missing"
    elif defect == "revision":
        binding["revision"] = "unreviewed"
    else:
        binding["mode"] = "control"  # Requires an explicit stop policy.
    before = deepcopy((await stored_flow(agent)).data)
    response = await client.patch(
        f"api/v1/projects/{project}", json={"project_config": config}, headers=logged_in_headers
    )
    assert response.status_code == 422, response.text
    assert (await stored_flow(agent)).data == before
    async with session_scope() as session:
        assert (await session.get(Folder, UUID(project))).project_config is None


async def test_hook_discovery_validation_and_baseline_are_scoped(client, logged_in_headers, active_user):
    project, _, source, _ = await setup_hooks(client, logged_in_headers, active_user)
    response = await client.get(f"api/v1/projects/{project}/flow-outputs?field_name=hooks", headers=logged_in_headers)
    assert response.status_code == 200
    assert [choice["flow_id"] for choice in response.json()] == [source]
    baseline = await client.post(
        f"api/v1/projects/{project}/flow-baseline?field_name=hooks", headers=logged_in_headers, json={}
    )
    assert baseline.status_code == 200, baseline.text
    flow = baseline.json()
    assert flow["folder_id"] == project
    assert flow["data"]["harness_contract"] == {"field_name": "hooks", "slot": "Hook"}
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["code"]["value"] = "raise RuntimeError('must not execute')"
    valid = await client.post(
        f"api/v1/projects/{project}/flow-outputs/validate?field_name=hooks",
        headers=logged_in_headers,
        json={"data": flow["data"]},
    )
    assert valid.status_code == 200
    assert valid.json()["valid"]
    flow["data"]["edges"] = []
    invalid = await client.post(
        f"api/v1/projects/{project}/flow-outputs/validate?field_name=hooks",
        headers=logged_in_headers,
        json={"data": flow["data"]},
    )
    assert not invalid.json()["valid"]
    assert "Hook Event" in invalid.json()["reason"]
    foreign = await client.get(f"api/v1/projects/{uuid4()}/flow-outputs?field_name=hooks", headers=logged_in_headers)
    assert foreign.status_code == 404


async def test_hook_archive_rebinds_new_ids_and_versions_with_original_present(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_hooks(client, logged_in_headers, active_user)
    saved = await save_config(client, logged_in_headers, project, config)
    exported = await client.get(f"api/v1/projects/download/{project}", headers=logged_in_headers)
    assert exported.status_code == 200
    imported = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("hooks.zip", exported.content, "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    flows = imported.json()
    assert not {flow["id"] for flow in flows}.intersection({agent, source})
    new_agent = next(flow for flow in flows if any(node["data"].get(HOOK_ORIGIN) for node in flow["data"]["nodes"]))
    bindings = json.loads((await stored_template(new_agent["id"]))["hook_bindings"]["value"])
    assert bindings[0]["flow_id"] in {flow["id"] for flow in flows}
    assert bindings[0]["version_id"] != saved["project_config"]["flow_bindings"]["hooks"][0]["version_id"]
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(bindings[0]["version_id"]))
        assert str(version.flow_id) == bindings[0]["flow_id"]
        new_project = await session.get(Folder, UUID(new_agent["folder_id"]))
        new_config = deepcopy(new_project.project_config)
    again = await save_config(client, logged_in_headers, new_agent["folder_id"], new_config)
    assert again["flows_updated"] == 0
    built = await run_stored_agent(new_agent["id"], active_user)
    assert "hook_completed" in str(built)
    assert bindings[0]["version_id"] in str(built)


async def test_stale_hook_source_needs_rebinding_and_cannot_be_imported(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_hooks(client, logged_in_headers, active_user)
    first = await save_config(client, logged_in_headers, project, config)
    before = deepcopy((await stored_flow(agent)).data)
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(source))
        data = deepcopy(flow.data)
        data["nodes"][-1]["data"]["node"]["template"]["reason"]["value"] = "Reviewed change"
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
    config["flow_bindings"]["hooks"][0]["revision"] = flow_revision(data)
    updated = await save_config(client, logged_in_headers, project, config)
    assert (
        updated["project_config"]["flow_bindings"]["hooks"][0]["version_id"]
        != first["project_config"]["flow_bindings"]["hooks"][0]["version_id"]
    )
    assert "Reviewed change" in str(await run_stored_agent(agent, active_user))


async def test_required_hook_snapshot_failure_rolls_back_the_binding(
    client, logged_in_headers, active_user, monkeypatch
):
    from langflow.services.database.models.folder import config_writer

    project, agent, source, config = await setup_hooks(client, logged_in_headers, active_user)
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
