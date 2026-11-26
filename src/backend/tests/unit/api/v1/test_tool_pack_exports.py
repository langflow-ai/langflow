from copy import deepcopy
from uuid import UUID

import pytest
from fastapi import HTTPException
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope

from tests.unit.api.v1.test_project_config_write_through import (
    create_flow,
    create_project,
    echo_flow_data,
    save_config,
    stored_flow,
)


@pytest.fixture
async def exported_pack(client, logged_in_headers, active_user):
    project_id = await create_project(
        client, logged_in_headers, name="Reusable research tools", project_type="tool-pack"
    )
    first = await create_flow(active_user, folder_id=project_id, name="Source lookup", data=echo_flow_data())
    second = await create_flow(active_user, folder_id=project_id, name="Other lookup", data=echo_flow_data())
    return project_id, first, second


async def test_tool_pack_saves_explicit_exports_without_rewriting_flows_or_mcp(
    client,
    logged_in_headers,
    exported_pack,
):
    project_id, first, second = exported_pack
    before = await stored_flow(first)
    saved = await save_config(client, logged_in_headers, project_id, {"tools": [first, first]})
    assert saved["project_config"]["tools"] == [first]
    after = await stored_flow(first)
    assert after.data == before.data
    assert after.updated_at == before.updated_at
    assert after.mcp_enabled == before.mcp_enabled
    response = await client.get(f"/api/v1/projects/{project_id}/tool-pack", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    manifest = response.json()
    assert manifest["reference"]["expected_type"] == "tool-pack"
    assert [tool["flow_id"] for tool in manifest["tools"]] == [first]
    assert second not in response.text
    assert "template" not in response.text
    await save_config(client, logged_in_headers, project_id, None)
    cleared = await client.get(f"/api/v1/projects/{project_id}/tool-pack", headers=logged_in_headers)
    assert cleared.json()["tools"] == []
    assert cleared.json()["reference"]["revision"] != manifest["reference"]["revision"]


async def test_tool_pack_rejects_invalid_and_foreign_exports_atomically(
    client,
    logged_in_headers,
    active_user,
    exported_pack,
):
    project_id, first, second = exported_pack
    other = await create_project(client, logged_in_headers, name="Other project", project_type="flows")
    foreign = await create_flow(active_user, folder_id=other, name="Foreign tool", data=echo_flow_data())
    await save_config(client, logged_in_headers, project_id, {"tools": [first]})
    async with session_scope() as session:
        invalid = await session.get(Flow, UUID(second))
        invalid.data = {"nodes": [], "edges": []}
        session.add(invalid)
    for exports in ([foreign], [second], [first, "invalid"], {"id": first}, None):
        response = await client.patch(
            f"/api/v1/projects/{project_id}", json={"project_config": {"tools": exports}}, headers=logged_in_headers
        )
        assert response.status_code == 422, response.text
        async with session_scope() as session:
            assert (await session.get(Folder, UUID(project_id))).project_config["tools"] == [first]


async def test_tool_pack_revision_tracks_export_edits_but_not_unexported_flows(
    client,
    logged_in_headers,
    exported_pack,
):
    project_id, first, second = exported_pack
    await save_config(client, logged_in_headers, project_id, {"tools": [first]})
    url = f"/api/v1/projects/{project_id}/tool-pack"
    before = (await client.get(url, headers=logged_in_headers)).json()
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(second))
        flow.description = "Unexported edit"
        session.add(flow)
    assert (await client.get(url, headers=logged_in_headers)).json() == before
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(first))
        data = deepcopy(flow.data)
        data["nodes"][0]["data"]["node"]["template"]["input_value"]["value"] = "Changed default"
        flow.data = data
        session.add(flow)
    after = (await client.get(url, headers=logged_in_headers)).json()
    assert after["reference"]["revision"] != before["reference"]["revision"]
    assert after["tools"][0]["revision"] != before["tools"][0]["revision"]
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(first))
        flow.data = {"nodes": [], "edges": []}
        session.add(flow)
    assert (await client.get(url, headers=logged_in_headers)).status_code == 409


async def test_tool_pack_discovery_checks_identity_type_and_project_flow_permissions(
    client,
    logged_in_headers,
    exported_pack,
    user_two_api_key,
    monkeypatch,
):
    project_id, first, _ = exported_pack
    await save_config(client, logged_in_headers, project_id, {"tools": [first]})
    url = f"/api/v1/projects/{project_id}/tool-pack"
    client.cookies.clear()
    assert (await client.get(url, headers={"x-api-key": user_two_api_key})).status_code == 404
    assert (await client.get(url)).status_code in {401, 403}
    plain = await create_project(client, logged_in_headers, name="Plain", project_type="flows")
    assert (await client.get(f"/api/v1/projects/{plain}/tool-pack", headers=logged_in_headers)).status_code == 422
    calls = []

    async def deny(user, action, **scope):
        assert user.id
        assert action.value == "read"
        calls.append(scope)
        raise HTTPException(403)

    with monkeypatch.context() as patch:
        patch.setattr("langflow.services.database.models.folder.tool_packs.ensure_project_permission", deny)
        assert (await client.get(url, headers=logged_in_headers)).status_code == 404
        assert calls[-1]["project_id"] == UUID(project_id)
    monkeypatch.setattr("langflow.services.database.models.folder.tool_packs.ensure_flow_permission", deny)
    assert (await client.get(url, headers=logged_in_headers)).status_code == 404
    assert calls[-1]["flow_id"] == UUID(first)
