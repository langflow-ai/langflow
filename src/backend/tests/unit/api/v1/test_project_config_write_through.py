"""Saving a project's form writes it through to the project's flows.

``project_config`` records what a person picked. A run never consults a folder, so the values
that actually run have to reach the components of the project's own flows. These tests save a
config over the API and then read the stored flow back to prove they did.

The Agent node is the real serialised component, so what gets written into is the template a
flow actually holds.
"""

import asyncio
from copy import deepcopy
from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.graph.flow_builder import add_component, add_connection, empty_flow
from lfx.projects.tools import TOOL_ORIGIN
from sqlmodel import select


def agent_flow_data(node_id: str = "Agent-1") -> dict:
    """A flow holding one real Agent component."""
    frontend = AgentComponent().to_frontend_node()
    data = frontend.get("data", frontend)
    data["id"] = node_id
    return {"nodes": [{"id": node_id, "data": data}], "edges": []}


def plain_flow_data() -> dict:
    """A flow with a component the harness type does not target."""
    frontend = AgentComponent().to_frontend_node()
    data = frontend.get("data", frontend)
    data["type"] = "ChatInput"
    return {"nodes": [{"id": "ChatInput-1", "data": data}], "edges": []}


async def create_flow(active_user, *, folder_id, data, name="harness-flow") -> str:
    async with session_scope() as session:
        flow_create = FlowCreate(
            name=name,
            description="",
            data=data,
            folder_id=UUID(folder_id) if folder_id else None,
            user_id=active_user.id,
        )
        flow = Flow.model_validate(flow_create.model_dump(exclude={"id"}))
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        flow_id = str(flow.id)
        await session.commit()
    return flow_id


async def stored_template(flow_id: str, index: int = 0) -> dict:
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))).first()
        return flow.data["nodes"][index]["data"]["node"]["template"]


async def create_project(client, headers, *, name, project_type="agent-harness") -> str:
    response = await client.post(
        "api/v1/projects/",
        json={"name": name, "description": "", "project_type": project_type},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


async def save_config(client, headers, project_id, config) -> dict:
    response = await client.patch(
        f"api/v1/projects/{project_id}",
        json={"project_config": config},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


@pytest.mark.usefixtures("active_user")
async def test_the_saved_form_reaches_the_flow(client: AsyncClient, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="wt-reaches")
    flow_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data())

    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse"})

    assert saved["flows_updated"] == 1
    assert (await stored_template(flow_id))["system_prompt"]["value"] == "Be terse"


@pytest.mark.usefixtures("active_user")
async def test_only_the_selected_agent_flow_is_written(client: AsyncClient, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="wt-every-flow")
    first = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="first")
    second = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="second")

    saved = await save_config(
        client, logged_in_headers, project_id, {"system_prompt": "Be terse", "agent_flow_id": first}
    )

    assert saved["flows_updated"] == 1
    assert (await stored_template(first))["system_prompt"]["value"] == "Be terse"
    assert (await stored_template(second))["system_prompt"]["value"] != "Be terse"


@pytest.mark.usefixtures("active_user")
async def test_a_flow_without_the_targeted_component_is_left_alone(client: AsyncClient, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="wt-untargeted")
    flow_id = await create_flow(active_user, folder_id=project_id, data=plain_flow_data())

    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse"})

    assert saved["flows_updated"] == 0
    assert (await stored_template(flow_id))["system_prompt"]["value"] != "Be terse"


@pytest.mark.usefixtures("active_user")
async def test_saving_the_same_form_again_rewrites_nothing(client: AsyncClient, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="wt-idempotent")
    await create_flow(active_user, folder_id=project_id, data=agent_flow_data())

    first = await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse"})
    again = await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse"})

    assert first["flows_updated"] == 1
    assert again["flows_updated"] == 0


@pytest.mark.usefixtures("active_user")
async def test_the_picked_flows_are_not_written_into_the_agent(client: AsyncClient, logged_in_headers, active_user):
    """The Agent's tools are objects built from the graph; ids there would break the run."""
    project_id = await create_project(client, logged_in_headers, name="wt-tools")
    flow_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data())

    response = await client.patch(
        f"api/v1/projects/{project_id}", json={"project_config": {"tools": [flow_id]}}, headers=logged_in_headers
    )

    assert response.status_code == 422
    assert (await stored_template(flow_id))["tools"]["value"] != [flow_id]


@pytest.mark.usefixtures("active_user")
async def test_a_plain_project_writes_nothing_through(client: AsyncClient, logged_in_headers, active_user):
    """The default type declares no form, so it has nothing to write."""
    project_id = await create_project(client, logged_in_headers, name="wt-plain", project_type="flows")
    flow_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data())

    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse"})

    assert saved["flows_updated"] == 0
    assert (await stored_template(flow_id))["system_prompt"]["value"] != "Be terse"


@pytest.mark.usefixtures("active_user")
async def test_renaming_a_project_does_not_disturb_its_flows(client: AsyncClient, logged_in_headers, active_user):
    """A save that carries no config must not rewrite anything."""
    project_id = await create_project(client, logged_in_headers, name="wt-rename")
    flow_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data())
    await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse"})

    response = await client.patch(
        f"api/v1/projects/{project_id}",
        json={"name": "wt-rename (renamed)"},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["flows_updated"] == 0
    assert (await stored_template(flow_id))["system_prompt"]["value"] == "Be terse"


@pytest.mark.usefixtures("active_user")
async def test_a_flow_added_to_the_project_later_is_configured_by_the_next_save(
    client: AsyncClient, logged_in_headers, active_user
):
    """A flow that joins a configured harness is written on the next save, not left behind."""
    project_id = await create_project(client, logged_in_headers, name="wt-added-later")
    await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse"})

    joined = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="joined")
    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse", "n_messages": 5})

    assert saved["flows_updated"] == 1
    written = await stored_template(joined)
    assert written["system_prompt"]["value"] == "Be terse"
    assert written["n_messages"]["value"] == 5


@pytest.mark.usefixtures("active_user")
async def test_a_locked_flow_is_left_alone_rather_than_failing_the_save(
    client: AsyncClient, logged_in_headers, active_user
):
    """Editing a locked flow answers 423; saving the project's form must not go around that."""
    project_id = await create_project(client, logged_in_headers, name="wt-locked")
    locked = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="locked")
    unlocked = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="unlocked")
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == UUID(locked)))).first()
        flow.locked = True
        session.add(flow)
        await session.commit()

    saved = await save_config(
        client, logged_in_headers, project_id, {"system_prompt": "Be terse", "agent_flow_id": locked}
    )

    assert saved["flows_updated"] == 0
    assert saved["flows_locked"] == 1
    assert (await stored_template(locked))["system_prompt"]["value"] != "Be terse"
    assert (await stored_template(unlocked))["system_prompt"]["value"] != "Be terse"


@pytest.mark.usefixtures("active_user")
async def test_a_written_flow_looks_edited(client: AsyncClient, logged_in_headers, active_user):
    """Nothing bumps updated_at for us, and a flow whose contents changed is not untouched."""
    project_id = await create_project(client, logged_in_headers, name="wt-updated-at")
    flow_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data())
    async with session_scope() as session:
        before = (await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))).first().updated_at

    await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse"})

    async with session_scope() as session:
        after = (await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))).first().updated_at
    assert after > before


def echo_flow_data():
    registry = {}
    for component in (ChatInput, ChatOutput):
        frontend = component().to_frontend_node()
        node = frontend.get("data", frontend)["node"]
        node["field_order"] = [item.name for item in component.inputs]
        registry[component.name] = node
    flow = empty_flow("echo")
    source = add_component(flow, "ChatInput", registry, component_id="ChatInput-echo")
    target = add_component(flow, "ChatOutput", registry, component_id="ChatOutput-echo")
    add_connection(flow, source["id"], "message", target["id"], "input_value")
    return flow["data"]


async def stored_flow(flow_id: str) -> Flow:
    async with session_scope() as session:
        return await session.get(Flow, UUID(flow_id))


async def edit_prompt(flow_id: str, value: str):
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(flow_id))
        data = deepcopy(flow.data)
        data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] = value
        flow.data = data
        session.add(flow)
        await session.commit()


async def test_ambiguous_agent_selection_changes_nothing(client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="ambiguous")
    first = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="first")
    second = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="second")
    response = await client.patch(
        f"api/v1/projects/{project_id}", json={"project_config": {"system_prompt": "wrong"}}, headers=logged_in_headers
    )
    assert response.status_code == 422
    assert (await stored_template(first))["system_prompt"]["value"] != "wrong"
    assert (await stored_template(second))["system_prompt"]["value"] != "wrong"


async def test_a2a_marked_flow_is_a_default_without_changing_roles(client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="marked")
    first = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="first")
    second = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="second")
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(first))
        flow.flow_type = "agent"
        session.add(flow)
        await session.commit()
    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "first"})
    assert saved["project_config"]["agent_flow_id"] == first
    saved = await save_config(
        client, logged_in_headers, project_id, {"agent_flow_id": second, "system_prompt": "second"}
    )
    assert saved["flows_updated"] == 1
    assert (await stored_flow(first)).flow_type == "agent"
    assert (await stored_flow(second)).flow_type == "workflow"


@pytest.mark.parametrize("field", ["agent_flow_id", "tools"])
async def test_selection_cannot_reach_another_project(field, client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name=f"own-{field}")
    other_id = await create_project(client, logged_in_headers, name=f"other-{field}")
    await create_flow(active_user, folder_id=project_id, data=agent_flow_data())
    outside = await create_flow(active_user, folder_id=other_id, data=agent_flow_data(), name="outside")
    value = outside if field == "agent_flow_id" else [outside]
    response = await client.patch(
        f"api/v1/projects/{project_id}", json={"project_config": {field: value}}, headers=logged_in_headers
    )
    assert response.status_code == 422


async def test_canvas_edits_win_and_baselines_cannot_be_replaced_by_the_form(client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="canvas-wins")
    flow_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data())
    await save_config(client, logged_in_headers, project_id, {"system_prompt": "project prompt", "n_messages": 10})
    await edit_prompt(flow_id, "canvas prompt")
    saved = await save_config(
        client,
        logged_in_headers,
        project_id,
        {
            "system_prompt": "new project prompt",
            "n_messages": 20,
            "_applied": {flow_id: {"Agent-1": {"system_prompt": "canvas prompt"}}},
        },
    )
    template = await stored_template(flow_id)
    assert template["system_prompt"]["value"] == "canvas prompt"
    assert template["n_messages"]["value"] == 20
    assert saved["fields_skipped"] == 1
    assert saved["flows_updated"] == 1
    baseline = saved["project_config"]["_applied"][flow_id]["Agent-1"]
    assert baseline == {"system_prompt": "project prompt", "n_messages": 20}
    # Returning the canvas value to the last applied baseline resumes following the form.
    await edit_prompt(flow_id, "project prompt")
    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "resumed"})
    assert saved["fields_skipped"] == 0
    assert (await stored_template(flow_id))["system_prompt"]["value"] == "resumed"


async def test_default_values_establish_provenance_without_creating_a_version(client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="default-provenance")
    flow_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data())
    default = (await stored_template(flow_id))["system_prompt"]["value"]
    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": default})
    assert saved["flows_updated"] == 0
    assert saved["restore_version_ids"] == {}
    await edit_prompt(flow_id, "local")
    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "incoming"})
    assert saved["fields_skipped"] == 1
    assert (await stored_template(flow_id))["system_prompt"]["value"] == "local"


async def test_writes_have_a_restorable_version_and_noop_saves_add_none(client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="restore")
    original = agent_flow_data()
    flow_id = await create_flow(active_user, folder_id=project_id, data=original)
    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "updated"})
    version_id = saved["restore_version_ids"][flow_id]
    async with session_scope() as session:
        version = await session.get(FlowVersion, UUID(version_id))
        assert version.data == original
        assert version.user_id == active_user.id
    again = await save_config(client, logged_in_headers, project_id, {"system_prompt": "updated"})
    assert again["restore_version_ids"] == {}
    async with session_scope() as session:
        versions = (await session.exec(select(FlowVersion).where(FlowVersion.flow_id == UUID(flow_id)))).all()
        assert len(versions) == 1


async def test_snapshot_failure_does_not_break_the_save(client, logged_in_headers, active_user, monkeypatch):
    from langflow.services.database.models.folder import config_writer

    async def unavailable(*_args, **_kwargs):
        msg = "version storage unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr(config_writer, "create_flow_version_entry", unavailable)
    project_id = await create_project(client, logged_in_headers, name="restore-unavailable")
    flow_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data())
    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "updated"})
    assert saved["restore_version_ids"] == {}
    assert (await stored_template(flow_id))["system_prompt"]["value"] == "updated"


async def test_tools_are_visible_callable_and_idempotent(client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="callable-tools")
    agent_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="agent")
    original_tool = echo_flow_data()
    tool_id = await create_flow(active_user, folder_id=project_id, data=original_tool, name="echo")
    config = {"agent_flow_id": agent_id, "tools": [tool_id]}
    saved = await save_config(client, logged_in_headers, project_id, config)
    assert saved["flows_updated"] == 1
    data = (await stored_flow(agent_id)).data
    tool_node = next(node for node in data["nodes"] if node["data"].get(TOOL_ORIGIN))
    template = tool_node["data"]["node"]["template"]
    assert template["flow_id_selected"]["value"] == tool_id
    assert template["ChatInput-echo~input_value"]["tool_mode"] is True
    assert data["edges"][0]["target"] == "Agent-1"
    assert data["edges"][0]["data"]["sourceHandle"]["name"] == "component_as_tool"
    assert (await stored_flow(tool_id)).data == original_tool
    assert (await stored_flow(tool_id)).mcp_enabled is False
    again = await save_config(client, logged_in_headers, project_id, config)
    assert again["flows_updated"] == 0
    assert (await stored_flow(agent_id)).data == data

    # Instantiate the persisted Run Flow configuration, discover its actual tools against
    # the database, then call the echo tool. No LLM or mocked graph/component-update path.
    component = RunFlowComponent(_user_id=str(active_user.id))
    component.set_attributes({key: value.get("value") for key, value in template.items() if isinstance(value, dict)})
    tools = await component._get_tools()
    assert tools
    payload = {"flow_tweak_data": {"ChatInput-echo~input_value": "hello harness"}}
    answer = await tools[0].ainvoke(payload)
    assert "hello harness" in str(answer)
    answers = await asyncio.gather(
        *[
            tools[0].ainvoke({"flow_tweak_data": {"ChatInput-echo~input_value": text}})
            for text in ("first independent call", "second independent call")
        ]
    )
    assert "first independent call" in str(answers[0])
    assert "second independent call" in str(answers[1])


async def test_deselecting_tools_preserves_hand_authored_nodes(client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="deselect")
    original = agent_flow_data()
    original["nodes"].append({"id": "note", "type": "noteNode", "data": {"text": "keep me"}})
    agent_id = await create_flow(active_user, folder_id=project_id, data=original, name="agent")
    tool_id = await create_flow(active_user, folder_id=project_id, data=echo_flow_data(), name="echo")
    await save_config(client, logged_in_headers, project_id, {"tools": [tool_id]})
    removed = await save_config(client, logged_in_headers, project_id, {"tools": []})
    assert removed["flows_updated"] == 1
    assert (await stored_flow(agent_id)).data == original


async def test_invalid_tool_does_not_partially_apply_other_fields(client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="invalid-tool")
    agent_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="agent")
    tool_id = await create_flow(active_user, folder_id=project_id, data={"nodes": [], "edges": []}, name="empty")
    response = await client.patch(
        f"api/v1/projects/{project_id}",
        json={"project_config": {"system_prompt": "must not apply", "tools": [tool_id]}},
        headers=logged_in_headers,
    )
    assert response.status_code == 422
    assert (await stored_template(agent_id))["system_prompt"]["value"] != "must not apply"


async def test_first_save_after_upgrade_preserves_legacy_canvas_edits(client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="legacy-provenance")
    flow_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data())
    await save_config(client, logged_in_headers, project_id, {"system_prompt": "old", "n_messages": 10})
    async with session_scope() as session:
        project = await session.get(Folder, UUID(project_id))
        project.project_config = {"system_prompt": "old", "n_messages": 10}
        session.add(project)
        await session.commit()
    await edit_prompt(flow_id, "local canvas edit")
    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "new", "n_messages": 20})
    assert saved["fields_skipped"] == 1
    template = await stored_template(flow_id)
    assert template["system_prompt"]["value"] == "local canvas edit"
    assert template["n_messages"]["value"] == 20


async def test_adding_a_tool_preserves_canvas_edits_and_avoids_existing_positions(
    client, logged_in_headers, active_user
):
    project_id = await create_project(client, logged_in_headers, name="tool-layout")
    agent_id = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="agent")
    first_id = await create_flow(active_user, folder_id=project_id, data=echo_flow_data(), name="first-tool")
    next_id = await create_flow(active_user, folder_id=project_id, data=echo_flow_data(), name="next-tool")
    await save_config(client, logged_in_headers, project_id, {"tools": [first_id]})
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(agent_id))
        data = deepcopy(flow.data)
        generated = next(node for node in data["nodes"] if node["data"].get(TOOL_ORIGIN))
        generated["data"]["node"]["template"]["session_id"]["value"] = "canvas session"
        original = deepcopy(generated)
        flow.data = data
        session.add(flow)
        await session.commit()
    await save_config(client, logged_in_headers, project_id, {"tools": [next_id, first_id]})
    nodes = (await stored_flow(agent_id)).data["nodes"]
    kept = next(node for node in nodes if node["id"] == original["id"])
    assert kept == original
    added = next(node for node in nodes if node["data"].get(TOOL_ORIGIN, {}).get("flow_id") == next_id)
    assert added["position"] != kept["position"]
