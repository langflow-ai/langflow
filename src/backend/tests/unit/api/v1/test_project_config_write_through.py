"""Saving a project's form writes it through to the project's flows.

``project_config`` records what a person picked. A run never consults a folder, so the values
that actually run have to reach the components of the project's own flows. These tests save a
config over the API and then read the stored flow back to prove they did.

The Agent node is the real serialised component, so what gets written into is the template a
flow actually holds.
"""

from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.deps import session_scope
from lfx.components.models_and_agents.agent import AgentComponent
from sqlmodel import select


def agent_flow_data(node_id: str = "Agent-1") -> dict:
    """A flow holding one real Agent component."""
    frontend = AgentComponent().to_frontend_node()
    return {"nodes": [{"id": node_id, "data": frontend.get("data", frontend)}], "edges": []}


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
async def test_every_flow_in_the_project_is_written(client: AsyncClient, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="wt-every-flow")
    first = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="first")
    second = await create_flow(active_user, folder_id=project_id, data=agent_flow_data(), name="second")

    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse"})

    assert saved["flows_updated"] == 2
    assert (await stored_template(first))["system_prompt"]["value"] == "Be terse"
    assert (await stored_template(second))["system_prompt"]["value"] == "Be terse"


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

    saved = await save_config(client, logged_in_headers, project_id, {"tools": [flow_id]})

    assert saved["flows_updated"] == 0
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

    saved = await save_config(client, logged_in_headers, project_id, {"system_prompt": "Be terse"})

    assert saved["flows_updated"] == 1
    assert (await stored_template(locked))["system_prompt"]["value"] != "Be terse"
    assert (await stored_template(unlocked))["system_prompt"]["value"] == "Be terse"


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
