"""Project-managed Compaction survives saves, execution, and mixed-contract archives."""

import json
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.graph.graph.base import Graph
from lfx.memory import aget_messages, astore_message
from lfx.projects.baselines import compaction_baseline, context_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.compaction import COMPACTION_ORIGIN, compaction_outputs
from lfx.projects.context import context_outputs
from lfx.projects.flow_slots import ProjectFlowBindings
from lfx.schema.message import Message, MessageResponse
from sqlmodel import select

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    save_config,
    stored_flow,
    stored_template,
)
from tests.unit.api.v1.test_project_context_bindings import add_other_bindings
from tests.unit.api.v1.test_project_instruction_bindings import RecordingModel


async def setup_compaction(client, headers, user):
    project = await create_project(client, headers, name="Compaction harness")
    agent = await create_flow(user, folder_id=project, data=agent_flow_data(), name="Agent")
    data = compaction_baseline({"compaction_keep_messages": 1})["data"]
    source = await create_flow(user, folder_id=project, data=data, name="Compaction")
    selected = compaction_outputs(data)[0]
    binding = {
        "flow_id": source,
        "revision": flow_revision(data),
        "trigger_tokens": 80,
        "timeout_seconds": 2.5,
        "node_id": selected["node_id"],
        "output_name": selected["output_name"],
    }
    return (
        project,
        agent,
        source,
        {
            "agent_flow_id": agent,
            "compaction": "off",
            "compaction_trigger_tokens": 9999,
            "compaction_keep_messages": 5,
            "flow_bindings": {"compaction": binding},
        },
    )


async def run_compaction_agent(agent, user):
    session_id = f"compaction-binding-{uuid4()}"
    for sender, text in [("User", "Old question " * 90), ("Machine", "Old answer " * 90)]:
        await astore_message(
            Message(text=text, sender=sender, sender_name=sender, session_id=session_id),
            flow_id=agent,
            user_id=str(user.id),
        )
    graph = Graph.from_payload(deepcopy((await stored_flow(agent)).data), flow_id=agent, user_id=str(user.id))
    graph.session_id = session_id
    vertex = graph.get_vertex("Agent-1")
    assert json.loads(vertex.params["compaction_binding"])
    model = RecordingModel()
    vertex.update_raw_params(
        {
            "model": model,
            "input_value": "Research",
            "n_messages": 10,
            "add_current_date_tool": False,
            "add_calculator_tool": False,
        },
        overwrite=True,
    )
    results = [result async for result in graph.async_start()]
    assert all(getattr(result, "valid", True) for result in results)
    assert len(model.seen) == 2
    assert model.seen[-1][-1].content == "Research"
    public = MessageResponse.from_message(vertex.custom_component.get_output("response").value).model_dump()
    assert "compacted" in str(public)
    saved = await aget_messages(session_id=session_id, flow_id=UUID(agent), user_id=user.id)
    assert any(message.text == "Old question " * 90 for message in saved)
    return model, public


async def test_compaction_save_snapshots_executes_and_is_idempotent(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_compaction(client, logged_in_headers, active_user)
    original = deepcopy((await stored_flow(source)).data)
    config["flow_bindings"]["compaction"]["version_id"] = str(uuid4())
    saved = await save_config(client, logged_in_headers, project, config)
    binding = saved["project_config"]["flow_bindings"]["compaction"]
    assert saved["restore_version_ids"]
    assert binding["version_id"] != config["flow_bindings"]["compaction"]["version_id"]
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(binding["version_id"]))
        assert str(version.flow_id) == source
        assert version.data == original
    assert (await stored_flow(source)).data == original
    repeated = await save_config(client, logged_in_headers, project, config)
    assert repeated["flows_updated"] == 0
    assert repeated["project_config"] == saved["project_config"]
    _, public = await run_compaction_agent(agent, active_user)
    assert binding["revision"] in str(public)
    assert binding["version_id"] in str(public)
    template = await stored_template(agent)
    assert template["compaction"]["value"] == "off"
    assert template["compaction_trigger_tokens"]["value"] == 9999
    assert template["compaction_keep_messages"]["value"] == 5


async def add_remaining_bindings(user, project, config):
    await add_other_bindings(user, project, config)
    data = context_baseline()["data"]
    source = await create_flow(user, folder_id=project, data=data, name="Context")
    output = context_outputs(data)[0]
    config["flow_bindings"]["context_strategy"] = {
        "flow_id": source,
        "revision": flow_revision(data),
        "node_id": output["node_id"],
        "output_name": output["output_name"],
    }


async def test_compaction_clears_independently_and_keeps_scalar_preferences(client, logged_in_headers, active_user):
    project, agent, _, config = await setup_compaction(client, logged_in_headers, active_user)
    await add_remaining_bindings(active_user, project, config)
    await save_config(client, logged_in_headers, project, config)
    binding = config["flow_bindings"].pop("compaction")
    saved = await save_config(client, logged_in_headers, project, config)
    assert set(saved["project_config"]["flow_bindings"]) == {"system_prompt", "context_strategy", "hooks"}
    template = await stored_template(agent)
    assert template["compaction_binding"]["value"] == ""
    assert template["compaction_trigger_tokens"]["value"] == 9999
    assert json.loads(template["context_binding"]["value"])
    assert json.loads(template["hook_bindings"]["value"])
    config["flow_bindings"]["compaction"] = binding
    await save_config(client, logged_in_headers, project, config)
    await save_config(client, logged_in_headers, project, None)
    assert (await stored_template(agent))["compaction_binding"]["value"] == ""
    assert not any(node["data"].get(COMPACTION_ORIGIN) for node in (await stored_flow(agent)).data["nodes"])


@pytest.mark.parametrize(
    "defect",
    [
        "foreign_project",
        "foreign_user",
        "self",
        "output",
        "revision",
        "timeout",
        "threshold",
        "shape",
        "canvas",
        "old_agent",
        "recursive",
    ],
)
async def test_invalid_compaction_binding_rolls_back_save(client, logged_in_headers, active_user, defect):
    project, agent, source, config = await setup_compaction(client, logged_in_headers, active_user)
    binding = config["flow_bindings"]["compaction"]
    if defect in {"foreign_project", "foreign_user", "canvas", "old_agent", "recursive"}:
        async with session_scope() as session:
            flow = await session.get(Flow, UUID(agent if defect in {"canvas", "old_agent"} else source))
            if defect == "foreign_project":
                flow.folder_id = None
            elif defect == "foreign_user":
                flow.user_id = None
            else:
                data = deepcopy(flow.data)
                if defect == "recursive":
                    node = agent_flow_data()["nodes"][0]
                    node["data"]["node"]["template"]["compaction_binding"]["value"] = json.dumps(
                        {**binding, "flow_id": agent}
                    )
                    data["nodes"].append(node)
                    binding["revision"] = flow_revision(data)
                else:
                    template = data["nodes"][0]["data"]["node"]["template"]
                    if defect == "old_agent":
                        template.pop("compaction_binding")
                    else:
                        template["compaction_binding"]["value"] = '{"manual":true}'
                flow.data = data
            await session.commit()
    elif defect == "shape":
        config["flow_bindings"]["compaction"] = [binding]
    else:
        key, value = {
            "self": ("flow_id", agent),
            "output": ("output_name", "missing"),
            "revision": ("revision", "unreviewed"),
            "timeout": ("timeout_seconds", 0),
            "threshold": ("trigger_tokens", 0),
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


async def test_compaction_discovery_baseline_and_validation_are_scoped(client, logged_in_headers, active_user):
    project, _, source, _ = await setup_compaction(client, logged_in_headers, active_user)
    suffix = "?field_name=compaction"
    choices = await client.get(f"api/v1/projects/{project}/flow-outputs{suffix}", headers=logged_in_headers)
    assert choices.status_code == 200
    assert [choice["flow_id"] for choice in choices.json()] == [source]
    baseline = await client.post(
        f"api/v1/projects/{project}/flow-baseline{suffix}",
        headers=logged_in_headers,
        json={"initial_config": {"compaction_keep_messages": 3}},
    )
    assert baseline.status_code == 200, baseline.text
    flow = baseline.json()
    assert flow["folder_id"] == project
    assert flow["data"]["harness_contract"] == {"field_name": "compaction", "slot": "Compactor"}
    assert flow["data"]["nodes"][-1]["data"]["node"]["template"]["keep_messages"]["value"] == 3
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["code"]["value"] = "raise RuntimeError('must not execute')"
    endpoint = f"api/v1/projects/{project}/flow-outputs/validate{suffix}"
    valid = await client.post(endpoint, headers=logged_in_headers, json={"data": flow["data"]})
    assert valid.json()["valid"]
    flow["data"]["edges"] = []
    invalid = await client.post(endpoint, headers=logged_in_headers, json={"data": flow["data"]})
    assert not invalid.json()["valid"]
    assert "Compaction Input" in invalid.json()["reason"]
    invalid = await client.post(
        f"api/v1/projects/{project}/flow-baseline{suffix}",
        headers=logged_in_headers,
        json={"initial_config": {"compaction_keep_messages": 0}},
    )
    assert invalid.status_code == 422
    assert "recent-message count" in invalid.text
    foreign = await client.get(f"api/v1/projects/{uuid4()}/flow-outputs{suffix}", headers=logged_in_headers)
    assert foreign.status_code == 404


async def test_compaction_archive_preserves_four_contracts_and_executes_without_original_ids(
    client, logged_in_headers, active_user
):
    project, agent, source, config = await setup_compaction(client, logged_in_headers, active_user)
    await add_remaining_bindings(active_user, project, config)
    saved = await save_config(client, logged_in_headers, project, config)
    exported = await client.get(f"api/v1/projects/download/{project}", headers=logged_in_headers)
    assert exported.status_code == 200
    imported = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("compaction.zip", exported.content, "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    flows = imported.json()
    assert not {flow["id"] for flow in flows}.intersection({agent, source})
    new_agent = next(
        flow for flow in flows if any(node["data"].get(COMPACTION_ORIGIN) for node in flow["data"]["nodes"])
    )
    binding = json.loads((await stored_template(new_agent["id"]))["compaction_binding"]["value"])
    assert binding["flow_id"] in {flow["id"] for flow in flows}
    assert binding["version_id"] != saved["project_config"]["flow_bindings"]["compaction"]["version_id"]
    assert binding["trigger_tokens"] == 80
    assert binding["timeout_seconds"] == 2.5
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(binding["version_id"]))
        assert str(version.flow_id) == binding["flow_id"]
        imported_project = await session.get(Folder, UUID(new_agent["folder_id"]))
        imported_config = deepcopy(imported_project.project_config)
    assert set(imported_config["flow_bindings"]) == {"system_prompt", "hooks", "context_strategy", "compaction"}
    original_sources = {
        binding.flow_id
        for _, binding in ProjectFlowBindings.model_validate(saved["project_config"]["flow_bindings"]).entries()
    }
    imported_bindings = ProjectFlowBindings.model_validate(imported_config["flow_bindings"])
    for _, imported_binding in imported_bindings.entries():
        assert imported_binding.flow_id in {flow["id"] for flow in flows}
        assert imported_binding.flow_id not in original_sources
    # Generated Instructions nodes must follow the imported binding too.
    for node in new_agent["data"]["nodes"]:
        target = node["data"]["node"]["template"].get("flow_id_selected", {}).get("value")
        assert target not in original_sources
    assert (await save_config(client, logged_in_headers, new_agent["folder_id"], imported_config))["flows_updated"] == 0
    model, public = await run_compaction_agent(new_agent["id"], active_user)
    assert model.seen[-1][0].content.startswith("Use primary sources. Today is ")
    assert "hook_completed" in str(public)
    assert "context_prepared" in str(public)
    for field in ["compaction", "context_strategy"]:
        assert imported_config["flow_bindings"][field]["version_id"] in str(public)


async def test_compaction_source_changes_require_review_before_save_or_import(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_compaction(client, logged_in_headers, active_user)
    first = await save_config(client, logged_in_headers, project, config)
    before = deepcopy((await stored_flow(agent)).data)
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(source))
        data = deepcopy(flow.data)
        data["nodes"][-1]["data"]["node"]["template"]["instructions"]["value"] = "Keep unresolved questions."
        flow.data = data
        await session.commit()
    rejected = await client.patch(
        f"api/v1/projects/{project}", json={"project_config": config}, headers=logged_in_headers
    )
    assert rejected.status_code == 422
    assert (await stored_flow(agent)).data == before
    exported = await client.get(f"api/v1/projects/download/{project}", headers=logged_in_headers)
    imported = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("stale.zip", exported.content, "application/zip")},
    )
    assert imported.status_code == 422, imported.text
    config["flow_bindings"]["compaction"]["revision"] = flow_revision(data)
    updated = await save_config(client, logged_in_headers, project, config)
    assert (
        updated["project_config"]["flow_bindings"]["compaction"]["version_id"]
        != first["project_config"]["flow_bindings"]["compaction"]["version_id"]
    )
    await run_compaction_agent(agent, active_user)


async def test_required_compaction_snapshot_failure_rolls_back_every_write(
    client, logged_in_headers, active_user, monkeypatch
):
    from langflow.services.database.models.folder import config_writer

    project, agent, source, config = await setup_compaction(client, logged_in_headers, active_user)
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
