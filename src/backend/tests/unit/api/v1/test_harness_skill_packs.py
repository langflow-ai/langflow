"""Review, compose, and hand off skills through the actual project API."""

from uuid import UUID

import pytest
from langflow.api.utils.composition_zip import extract_composition
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.projects.skills import parse_harness_skills
from lfx.projects.tools import TOOL_ORIGIN
from sqlmodel import select

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    echo_flow_data,
    save_config,
    stored_flow,
)


@pytest.fixture
async def skill_harness(client, logged_in_headers, active_user):
    tools = await create_project(client, logged_in_headers, name="Skill tools", project_type="tool-pack")
    source = await create_flow(active_user, folder_id=tools, name="Skill lookup", data=echo_flow_data())
    await save_config(client, logged_in_headers, tools, {"tools": [source]})
    tool_manifest = (await client.get(f"/api/v1/projects/{tools}/tool-pack", headers=logged_in_headers)).json()
    pack = await create_project(client, logged_in_headers, name="Research skills", project_type="skill-pack")
    definition = {
        "name": "research",
        "description": "Research a question",
        "instructions": "Use original sources.",
        "tool_packs": [tool_manifest["reference"]],
    }
    await save_config(client, logged_in_headers, pack, {"skills": [definition]})
    manifest = (await client.get(f"/api/v1/projects/{pack}/skill-pack", headers=logged_in_headers)).json()
    project = await create_project(client, logged_in_headers, name="Skill consumer")
    agent = await create_flow(active_user, folder_id=project, name="Skill agent", data=agent_flow_data())
    config = {"agent_flow_id": agent, "skill_packs": [manifest["reference"]]}
    await save_config(client, logged_in_headers, project, config)
    return project, agent, pack, tools, config, definition


def skills_of(flow):
    node = next(n for n in flow.data["nodes"] if n["data"]["type"] == "Agent")
    return parse_harness_skills(node["data"]["node"]["template"]["skill_bindings"]["value"])


async def test_skill_save_embeds_reviewed_content_and_scoped_tools(client, logged_in_headers, skill_harness):
    project, agent, pack, _, config, definition = skill_harness
    flow = await stored_flow(agent)
    skills = skills_of(flow)
    assert skills.packs[0].skills[0].instructions == "Use original sources."
    assert not skills.global_tool_pack_ids
    assert len([node for node in flow.data["nodes"] if TOOL_ORIGIN in node["data"]]) == 1
    await save_config(client, logged_in_headers, pack, {"skills": [{**definition, "instructions": "Edited later."}]})
    assert skills_of(await stored_flow(agent)) == skills
    response = await client.patch(
        f"/api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": config}
    )
    assert response.status_code == 422
    assert "Skill Pack changed" in response.text
    await save_config(client, logged_in_headers, project, {"agent_flow_id": agent, "skill_packs": []})
    cleared = await stored_flow(agent)
    assert not skills_of(cleared).packs
    assert not any(TOOL_ORIGIN in node["data"] for node in cleared.data["nodes"])


async def test_skill_composition_relocates_skills_tools_and_revisions(client, logged_in_headers, skill_harness):
    project, agent, pack, tools, _, _ = skill_harness
    response = await client.get(f"/api/v1/projects/download/{project}", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    composition = await extract_composition(response.content)
    assert {item.project_type for item in composition.projects} == {"agent-harness", "skill-pack", "tool-pack"}
    uploaded = await client.post(
        "/api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("skills.zip", response.content, "application/zip")},
    )
    assert uploaded.status_code == 201, uploaded.text
    imported = await stored_flow(uploaded.json()[0]["id"])
    skills = skills_of(imported)
    assert str(skills.packs[0].reference.project_id) != pack
    assert str(skills.packs[0].skills[0].tool_packs[0].project_id) != tools
    assert skills.packs[0].skills[0].instructions == "Use original sources."
    async with session_scope() as session:
        folder = await session.get(Folder, imported.folder_id)
        config = folder.project_config
    await save_config(client, logged_in_headers, str(imported.folder_id), config)
    assert skills_of(await stored_flow(agent)).packs[0].reference.project_id == UUID(pack)


async def test_skills_reject_invalid_content_and_foreign_packs(client, logged_in_headers):
    pack = await create_project(client, logged_in_headers, name="Validation skills", project_type="skill-pack")
    response = await client.patch(
        f"/api/v1/projects/{pack}",
        headers=logged_in_headers,
        json={"project_config": {"skills": [{"name": "Invalid Name", "description": "", "instructions": ""}]}},
    )
    assert response.status_code == 422
    normal = await create_project(client, logged_in_headers, name="Not skills")
    response = await client.get(f"/api/v1/projects/{normal}/skill-pack", headers=logged_in_headers)
    assert response.status_code == 422


async def test_empty_flow_skill_pack_can_be_exported_and_imported(client, logged_in_headers, active_user):
    pack = await create_project(client, logged_in_headers, name="Writing skills", project_type="skill-pack")
    await save_config(
        client,
        logged_in_headers,
        pack,
        {"skills": [{"name": "write", "description": "Write prose", "instructions": "Use plain language."}]},
    )
    response = await client.get(f"/api/v1/projects/download/{pack}", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    uploaded = await client.post(
        "/api/v1/projects/upload/",
        headers=logged_in_headers,
        files={"file": ("skills.zip", response.content, "application/zip")},
    )
    assert uploaded.status_code == 201, uploaded.text
    async with session_scope() as session:
        packs = list(
            (
                await session.exec(
                    select(Folder).where(Folder.project_type == "skill-pack", Folder.user_id == active_user.id)
                )
            ).all()
        )
    assert len(packs) >= 2
    assert any(str(item.id) != pack and item.project_config["skills"][0]["name"] == "write" for item in packs)


async def test_skill_attachment_requires_tool_execute_permission(client, logged_in_headers, skill_harness, monkeypatch):
    from fastapi import HTTPException

    project, agent, _, _, config, _ = skill_harness
    before = (await stored_flow(agent)).data

    async def deny_execute(_user, action, **_scope):
        if action.value == "execute":
            raise HTTPException(403)

    monkeypatch.setattr("langflow.services.database.models.folder.tool_packs.ensure_flow_permission", deny_execute)
    response = await client.patch(
        f"/api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": config}
    )
    assert response.status_code == 404
    assert (await stored_flow(agent)).data == before


async def test_standalone_artifact_rejects_unprovisioned_skill_dependencies(skill_harness, active_user):
    from langflow.services.deployment_artifacts import ProjectArtifactError, build_project_artifact

    project, _, _, _, _, _ = skill_harness
    async with session_scope() as session:
        with pytest.raises(ProjectArtifactError, match="standalone deployment packages cannot resolve"):
            await build_project_artifact(session, active_user, UUID(project))
