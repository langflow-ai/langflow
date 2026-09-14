"""Harness runtime settings reach saved Agent graphs without replacing canvas customizations."""

from copy import deepcopy

import pytest
from langflow.services.deps import session_scope
from lfx.base.agents.harness import HarnessRuntimeConfig

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    save_config,
    stored_flow,
    stored_template,
)


async def test_runtime_settings_write_through_and_preserve_canvas_edits(client, logged_in_headers, active_user):
    project = await create_project(client, logged_in_headers, name="Runtime harness")
    agent = await create_flow(active_user, folder_id=project, data=agent_flow_data())
    settings = HarnessRuntimeConfig(
        context_strategy="recent_turns",
        context_turns=3,
        compaction="summarize",
        compaction_trigger_tokens=4000,
        compaction_keep_messages=6,
        max_iterations=4,
    ).model_dump()
    saved = await save_config(client, logged_in_headers, project, settings)
    assert saved["restore_version_ids"]
    template = await stored_template(agent)
    assert {name: template[name]["value"] for name in settings} == settings
    flow = await stored_flow(agent)
    data = deepcopy(flow.data)
    data["nodes"][0]["data"]["node"]["template"]["context_turns"]["value"] = 7
    async with session_scope() as session:
        flow.data = data
        session.add(flow)
        await session.commit()
    saved = await save_config(client, logged_in_headers, project, {**settings, "context_turns": 5, "max_iterations": 2})
    assert saved["fields_skipped"] == 1
    template = await stored_template(agent)
    assert template["context_turns"]["value"] == 7
    assert template["max_iterations"]["value"] == 2


@pytest.mark.parametrize("invalid", [{"context_turns": 0}, {"compaction": "fake"}, {"max_iterations": True}])
async def test_invalid_runtime_config_does_not_change_the_graph(client, logged_in_headers, active_user, invalid):
    project = await create_project(client, logged_in_headers, name="Invalid runtime")
    data = agent_flow_data()
    agent = await create_flow(active_user, folder_id=project, data=data)
    response = await client.patch(
        f"api/v1/projects/{project}", json={"project_config": invalid}, headers=logged_in_headers
    )
    assert response.status_code == 422
    assert "Invalid harness runtime" in response.text
    assert (await stored_flow(agent)).data == data


async def test_old_agent_requires_update_only_when_new_runtime_behavior_is_requested(
    client, logged_in_headers, active_user
):
    project = await create_project(client, logged_in_headers, name="Old runtime")
    data = agent_flow_data()
    template = data["nodes"][0]["data"]["node"]["template"]
    for name in HarnessRuntimeConfig.model_fields:
        if name != "max_iterations":
            template.pop(name)
    agent = await create_flow(active_user, folder_id=project, data=data)
    await save_config(client, logged_in_headers, project, HarnessRuntimeConfig().model_dump())
    before = deepcopy((await stored_flow(agent)).data)
    response = await client.patch(
        f"api/v1/projects/{project}",
        json={"project_config": {"context_strategy": "recent_turns"}},
        headers=logged_in_headers,
    )
    assert response.status_code == 422
    assert "Update the Agent component" in response.text
    assert (await stored_flow(agent)).data == before
