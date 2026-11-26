"""Permission bindings preserve source snapshots, canvas ownership, and mixed archives."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_job_service, session_scope
from lfx.graph.graph.base import Graph
from lfx.memory import astore_message
from lfx.projects.baselines import permission_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.flow_slots import ProjectFlowBindings
from lfx.projects.permissions import PERMISSION_ORIGIN, permission_outputs
from lfx.schema.message import Message, MessageResponse
from sqlmodel import select

from tests.unit.api.v1.test_permission_flow_runtime import StoredPermissionModel
from tests.unit.api.v1.test_project_compaction_bindings import add_remaining_bindings, setup_compaction
from tests.unit.api.v1.test_project_config_write_through import create_flow, save_config, stored_flow, stored_template


class ComposedPermissionModel(StoredPermissionModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if "Messages to summarize:" in str(messages[0].content):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Earlier evidence [source-1]."))])
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


async def setup_permission(client, headers, user):
    project, agent, _, config = await setup_compaction(client, headers, user)
    await add_remaining_bindings(user, project, config)
    data = permission_baseline({"tool_policy": "tool_defaults"})["data"]
    source = await create_flow(user, folder_id=project, data=data, name="Permissions")
    output = permission_outputs(data)[0]
    config["tool_policy"] = "deny"  # retained scalar preference; the flow supplies the active policy
    config["flow_bindings"]["tool_policy"] = {
        "flow_id": source,
        "revision": flow_revision(data),
        "node_id": output["node_id"],
        "output_name": output["output_name"],
        "timeout_seconds": 2.5,
    }
    return project, agent, source, config


async def execute(agent, user):
    job = uuid4()
    await get_job_service().create_job(job_id=job, flow_id=UUID(agent), user_id=user.id)
    session_id = str(uuid4())
    for sender, text in [("User", "Earlier question " * 90), ("Machine", "Earlier answer " * 90)]:
        await astore_message(
            Message(text=text, sender=sender, sender_name=sender, session_id=session_id),
            flow_id=agent,
            user_id=str(user.id),
        )
    effects = []

    @tool
    def record(value: str) -> str:
        """Record approved evidence."""
        effects.append(value)
        return value

    graph = Graph.from_payload(deepcopy((await stored_flow(agent)).data), flow_id=agent, user_id=str(user.id))
    graph.set_run_id(job)
    graph.session_id = session_id
    vertex = graph.get_vertex("Agent-1")
    vertex.update_raw_params(
        {
            "model": ComposedPermissionModel(),
            "tools": [record],
            "input_value": "Research",
            "n_messages": 10,
            "add_current_date_tool": False,
            "add_calculator_tool": False,
        },
        overwrite=True,
    )
    results = [result async for result in graph.async_start()]
    assert all(getattr(result, "valid", True) for result in results)
    return effects, MessageResponse.from_message(vertex.custom_component.get_output("response").value).model_dump()


async def test_permission_save_snapshots_executes_all_five_contracts_and_is_idempotent(
    client, logged_in_headers, active_user
):
    project, agent, source, config = await setup_permission(client, logged_in_headers, active_user)
    original = deepcopy((await stored_flow(source)).data)
    config["flow_bindings"]["tool_policy"]["version_id"] = str(uuid4())
    saved = await save_config(client, logged_in_headers, project, config)
    binding = saved["project_config"]["flow_bindings"]["tool_policy"]
    assert binding["version_id"] != config["flow_bindings"]["tool_policy"]["version_id"]
    assert saved["restore_version_ids"]
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(binding["version_id"]))
        assert str(version.flow_id) == source
        assert version.data == original
    assert (await stored_flow(source)).data == original
    assert (await save_config(client, logged_in_headers, project, config))["project_config"] == saved["project_config"]
    assert (await save_config(client, logged_in_headers, project, config))["flows_updated"] == 0
    assert (await stored_template(agent))["tool_policy"]["value"] == "deny"
    effects, public = await execute(agent, active_user)
    assert effects == ["evidence"]
    for kind in ["compacted", "context_prepared", "hook_completed", "permission_decision"]:
        assert kind in str(public)
    assert binding["revision"] in str(public)
    assert binding["version_id"] in str(public)


async def test_permission_removal_retains_other_bindings_and_restores_scalar_policy(
    client, logged_in_headers, active_user
):
    project, agent, _, config = await setup_permission(client, logged_in_headers, active_user)
    await save_config(client, logged_in_headers, project, config)
    binding = config["flow_bindings"].pop("tool_policy")
    saved = await save_config(client, logged_in_headers, project, config)
    assert set(saved["project_config"]["flow_bindings"]) == {"system_prompt", "hooks", "context_strategy", "compaction"}
    assert (await stored_template(agent))["permission_binding"]["value"] == ""
    assert (await execute(agent, active_user))[0] == []
    config["flow_bindings"]["tool_policy"] = binding
    await save_config(client, logged_in_headers, project, config)
    await save_config(client, logged_in_headers, project, None)
    assert (await stored_template(agent))["permission_binding"]["value"] == ""
    assert not any(node["data"].get(PERMISSION_ORIGIN) for node in (await stored_flow(agent)).data["nodes"])


@pytest.mark.parametrize(
    "defect",
    ["foreign_project", "foreign_user", "self", "output", "revision", "timeout", "shape", "canvas", "old_agent"],
)
async def test_invalid_permission_binding_rolls_back_all_writes(client, logged_in_headers, active_user, defect):
    project, agent, source, config = await setup_permission(client, logged_in_headers, active_user)
    binding = config["flow_bindings"]["tool_policy"]
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
                    template.pop("permission_binding")
                else:
                    template["permission_binding"]["value"] = '{"manual":true}'
                flow.data = data
            await session.commit()
    elif defect == "shape":
        config["flow_bindings"]["tool_policy"] = [binding]
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
        sources = [
            UUID(entry.flow_id)
            for _, entry in ProjectFlowBindings.model_validate(
                {k: v for k, v in config["flow_bindings"].items() if k != "tool_policy"}
            ).entries()
        ]
        assert not (await session.exec(select(FlowVersion).where(FlowVersion.flow_id.in_(sources)))).all()


async def test_permission_baseline_discovery_and_draft_validation_are_scoped(client, logged_in_headers, active_user):
    project, _, source, _ = await setup_permission(client, logged_in_headers, active_user)
    suffix = "?field_name=tool_policy"
    choices = await client.get(f"api/v1/projects/{project}/flow-outputs{suffix}", headers=logged_in_headers)
    assert choices.status_code == 200
    assert [choice["flow_id"] for choice in choices.json()] == [source]
    baseline = await client.post(
        f"api/v1/projects/{project}/flow-baseline{suffix}",
        headers=logged_in_headers,
        json={"initial_config": {"tool_policy": "deny"}},
    )
    assert baseline.status_code == 200, baseline.text
    flow = baseline.json()
    assert flow["folder_id"] == project
    assert flow["data"]["harness_contract"] == {"field_name": "tool_policy", "slot": "PermissionGate"}
    template = flow["data"]["nodes"][-1]["data"]["node"]["template"]
    assert template["action"]["value"] == "reject"
    template["code"]["value"] = "raise RuntimeError('must not execute')"
    endpoint = f"api/v1/projects/{project}/flow-outputs/validate{suffix}"
    assert (await client.post(endpoint, headers=logged_in_headers, json={"data": flow["data"]})).json()["valid"]
    flow["data"]["edges"] = []
    assert not (await client.post(endpoint, headers=logged_in_headers, json={"data": flow["data"]})).json()["valid"]
    invalid = await client.post(
        f"api/v1/projects/{project}/flow-baseline{suffix}",
        headers=logged_in_headers,
        json={"initial_config": {"tool_policy": "unknown"}},
    )
    assert invalid.status_code == 422
    assert "permission policy" in invalid.text
    assert (
        await client.get(f"api/v1/projects/{uuid4()}/flow-outputs{suffix}", headers=logged_in_headers)
    ).status_code == 404


async def test_permission_archive_remaps_and_executes_five_contracts(client, logged_in_headers, active_user):
    project, _, _, config = await setup_permission(client, logged_in_headers, active_user)
    saved = await save_config(client, logged_in_headers, project, config)
    exported = await client.get(f"api/v1/projects/download/{project}", headers=logged_in_headers)
    assert exported.status_code == 200
    imported = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("permissions.zip", exported.content, "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    flows = imported.json()
    agent = next(flow for flow in flows if any(node["data"].get(PERMISSION_ORIGIN) for node in flow["data"]["nodes"]))
    async with session_scope() as session:
        imported_config = deepcopy((await session.get(Folder, UUID(agent["folder_id"]))).project_config)
        old = ProjectFlowBindings.model_validate(saved["project_config"]["flow_bindings"])
        new = ProjectFlowBindings.model_validate(imported_config["flow_bindings"])
        assert len(new.entries()) == len(old.entries()) == 5
        for field, binding in new.entries():
            assert binding.flow_id in {flow["id"] for flow in flows}
            assert binding.flow_id not in {entry.flow_id for _, entry in old.entries()}
            assert binding.version_id not in {entry.version_id for _, entry in old.entries()}
            version = await session.get(FlowVersion, UUID(binding.version_id))
            assert str(version.flow_id) == binding.flow_id
            if field == "tool_policy":
                assert binding.timeout_seconds == 2.5
    assert (await save_config(client, logged_in_headers, agent["folder_id"], imported_config))["flows_updated"] == 0
    effects, public = await execute(agent["id"], active_user)
    assert effects == ["evidence"]
    for kind in ["compacted", "context_prepared", "hook_completed", "permission_decision"]:
        assert kind in str(public)
    for field in ["compaction", "context_strategy", "tool_policy"]:
        assert imported_config["flow_bindings"][field]["version_id"] in str(public)


async def test_permission_snapshot_failure_rolls_back_mixed_sources(
    client, logged_in_headers, active_user, monkeypatch
):
    from langflow.services.database.models.folder import config_writer

    project, agent, source, config = await setup_permission(client, logged_in_headers, active_user)
    original = config_writer.create_flow_version_entry

    async def fail_permission(session, flow_id, *args, **kwargs):
        result = await original(session, flow_id, *args, **kwargs)
        if str(flow_id) == source:
            msg = "Snapshot storage failed"
            raise RuntimeError(msg)
        return result

    monkeypatch.setattr(config_writer, "create_flow_version_entry", fail_permission)
    before = deepcopy((await stored_flow(agent)).data)
    response = await client.patch(
        f"api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": config}
    )
    assert response.status_code == 500
    assert (await stored_flow(agent)).data == before
    async with session_scope() as session:
        assert (await session.get(Folder, UUID(project))).project_config is None
        sources = [
            UUID(entry.flow_id) for _, entry in ProjectFlowBindings.model_validate(config["flow_bindings"]).entries()
        ]
        assert not (await session.exec(select(FlowVersion).where(FlowVersion.flow_id.in_(sources)))).all()


async def test_permission_source_changes_require_review_before_save_or_import(client, logged_in_headers, active_user):
    project, agent, source, config = await setup_permission(client, logged_in_headers, active_user)
    saved = await save_config(client, logged_in_headers, project, config)
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(source))
        data = deepcopy(flow.data)
        data["nodes"][-1]["data"]["node"]["template"]["action"]["value"] = "reject"
        flow.data = data
        await session.commit()
    before = deepcopy((await stored_flow(agent)).data)
    stale = await client.patch(f"api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": config})
    assert stale.status_code == 422
    assert (await stored_flow(agent)).data == before
    exported = await client.get(f"api/v1/projects/download/{project}", headers=logged_in_headers)
    assert exported.status_code == 200
    imported = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("stale-permissions.zip", exported.content, "application/zip")},
    )
    assert imported.status_code == 422
    config["flow_bindings"]["tool_policy"]["revision"] = flow_revision(data)
    updated = await save_config(client, logged_in_headers, project, config)
    assert (
        updated["project_config"]["flow_bindings"]["tool_policy"]["version_id"]
        != saved["project_config"]["flow_bindings"]["tool_policy"]["version_id"]
    )
    assert (await execute(agent, active_user))[0] == []
