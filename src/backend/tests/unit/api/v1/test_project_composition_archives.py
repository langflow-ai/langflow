"""Project ZIP handoffs recreate dependencies without reaching back to the source account."""

# ruff: noqa: F811 -- Imported pytest fixtures are injected by name.

import io
import json
import zipfile
from copy import deepcopy
from uuid import UUID

import pytest
from langflow.api.utils.composition_zip import COMPOSITION_FILENAME, composition_zip, extract_composition
from langflow.helpers.flow import get_tool_pack_flow
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.graph.graph.base import Graph
from lfx.projects.archives import CompositionGraph
from lfx.projects.bindings import flow_revision
from lfx.projects.tool_packs import ToolPackToolBinding
from lfx.projects.tools import TOOL_ORIGIN, tool_node_revision
from sqlmodel import select

from tests.unit.api.v1.test_harness_tool_packs import pack_harness, pack_node  # noqa: F401
from tests.unit.api.v1.test_project_config_write_through import create_flow, echo_flow_data, save_config, stored_flow


async def download(client, headers, project):
    response = await client.get(f"api/v1/projects/download/{project}", headers=headers)
    assert response.status_code == 200, response.text
    return response.content


async def upload(client, headers, contents):
    return await client.post(
        "api/v1/projects/upload/",
        headers=headers,
        files={"file": ("research.zip", contents, "application/zip")},
    )


async def test_composition_import_preserves_pack_local_tools_and_canvas_edits(
    client,
    logged_in_headers,
    active_user,
    pack_harness,
):
    project, agent, pack, source, config = pack_harness
    local = await create_flow(active_user, folder_id=project, name="Local archive tool", data=echo_flow_data())
    await save_config(client, logged_in_headers, project, {**config, "tools": [local]})
    async with session_scope() as session:
        row = await session.get(Flow, UUID(agent))
        data = deepcopy(row.data)
        node = next(node for node in data["nodes"] if node["data"].get(TOOL_ORIGIN, {}).get("tool_pack"))
        node["position"] = {"x": 782, "y": 339}
        node["data"]["node"]["template"]["session_id"]["value"] = "preserved-canvas-setting"
        row.data = data
        session.add(row)
    before = await stored_flow(agent)
    contents = await download(client, logged_in_headers, project)
    portable = await extract_composition(contents)
    assert len(portable.projects) == 2
    CompositionGraph(portable).validate()
    response = await upload(client, logged_in_headers, contents)
    assert response.status_code == 201, response.text
    flows = response.json()
    assert len(flows) == 2  # The upload response still describes the root project.
    assert not {flow["id"] for flow in flows}.intersection({agent, source, local})
    imported = next(flow for flow in flows if any(TOOL_ORIGIN in node["data"] for node in flow["data"]["nodes"]))
    saved = await stored_flow(imported["id"])
    node = pack_node(saved)
    binding = ToolPackToolBinding.model_validate(node["data"][TOOL_ORIGIN]["tool_pack"])
    assert str(binding.reference.project_id) != pack
    assert str(binding.tool.flow_id) != source
    assert node["id"] == pack_node(before)["id"]
    assert node["position"] == {"x": 782, "y": 339}
    assert node["data"]["node"]["template"]["session_id"]["value"] == "preserved-canvas-setting"
    assert node["data"][TOOL_ORIGIN]["applied_revision"] != tool_node_revision(node)
    definition = await get_tool_pack_flow(user_id=str(active_user.id), binding=binding)
    assert flow_revision(definition.data["data"]) == flow_revision((await stored_flow(source)).data)
    async with session_scope() as session:
        folder = await session.get(Folder, saved.folder_id)
        pack_folder = await session.get(Folder, binding.reference.project_id)
        version = await session.get(FlowVersion, binding.version_id)
        assert pack_folder.project_config["tools"] == [str(binding.tool.flow_id)]
        assert folder.project_config["tool_packs"] == [binding.reference.model_dump(mode="json")]
        assert folder.project_config["agent_flow_id"] == imported["id"]
        assert folder.project_config["tools"] == [next(flow["id"] for flow in flows if flow["id"] != imported["id"])]
        assert flow_revision(version.data) == binding.tool.revision
        assert version.user_id == active_user.id
        imported_config = deepcopy(folder.project_config)
    # An ordinary save remains possible and keeps independent canvas configuration.
    await save_config(client, logged_in_headers, str(saved.folder_id), imported_config)
    assert (
        pack_node(await stored_flow(imported["id"]))["data"]["node"]["template"]["session_id"]["value"]
        == "preserved-canvas-setting"
    )
    assert (await stored_flow(agent)).data == before.data


@pytest.mark.parametrize("defect", ["missing_pack", "missing_flow", "stale_pack", "duplicate_flow", "wrong_owner"])
async def test_invalid_composition_is_atomic(client, logged_in_headers, pack_harness, defect):
    project, _agent, pack, _source, _config = pack_harness
    composition = await extract_composition(await download(client, logged_in_headers, project))
    root = next(item for item in composition.projects if str(item.id) == project)
    dependency = next(item for item in composition.projects if str(item.id) == pack)
    if defect == "missing_pack":
        composition.projects.remove(dependency)
    elif defect == "missing_flow":
        dependency.flows.clear()
    elif defect == "stale_pack":
        dependency.flows[0]["description"] = "unreviewed contract"
    elif defect == "duplicate_flow":
        root.flows.append(deepcopy(dependency.flows[0]))
    else:
        root.project_config["tools"] = [dependency.flows[0]["id"]]
    async with session_scope() as session:
        before = set((await session.exec(select(Folder.id))).all())
    response = await upload(client, logged_in_headers, composition_zip(composition).getvalue())
    assert response.status_code == 422, response.text
    async with session_scope() as session:
        assert set((await session.exec(select(Folder.id))).all()) == before


@pytest.mark.parametrize(
    "defect", ["missing_manifest", "missing_member", "duplicate_member", "future_version", "extra_member"]
)
async def test_corrupt_zip_never_falls_back_to_partial_import(client, logged_in_headers, pack_harness, defect):
    project = pack_harness[0]
    contents = await download(client, logged_in_headers, project)
    original = zipfile.ZipFile(io.BytesIO(contents))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for member in original.namelist():
            if defect == "missing_manifest" and member == COMPOSITION_FILENAME:
                continue
            if defect == "missing_member" and member.endswith(".flow"):
                continue
            data = original.read(member)
            if defect == "future_version" and member == COMPOSITION_FILENAME:
                manifest = json.loads(data)
                manifest["version"] = 99
                data = json.dumps(manifest).encode()
            archive.writestr(member, data)
        if defect == "duplicate_member":
            with pytest.warns(UserWarning, match="Duplicate"):
                archive.writestr(COMPOSITION_FILENAME, original.read(COMPOSITION_FILENAME))
        if defect == "extra_member":
            archive.writestr("unexpected.flow", "{}")
    response = await upload(client, logged_in_headers, output.getvalue())
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("defect", ["changed_source", "missing_snapshot", "inaccessible_pack"])
async def test_export_requires_reviewed_accessible_sources(client, logged_in_headers, pack_harness, defect):
    project, agent, pack, source, _config = pack_harness
    async with session_scope() as session:
        if defect == "changed_source":
            flow = await session.get(Flow, UUID(source))
            flow.description = "Changed export"
            session.add(flow)
        elif defect == "missing_snapshot":
            binding = ToolPackToolBinding.model_validate(
                pack_node(await stored_flow(agent))["data"][TOOL_ORIGIN]["tool_pack"]
            )
            version = await session.get(FlowVersion, binding.version_id)
            await session.delete(version)
        else:
            folder = await session.get(Folder, UUID(pack))
            folder.user_id = None
            session.add(folder)
    response = await client.get(f"api/v1/projects/download/{project}", headers=logged_in_headers)
    assert response.status_code == (404 if defect == "inaccessible_pack" else 422), response.text


async def test_imported_pack_is_callable_by_an_account_with_no_access_to_originals(
    client,
    logged_in_headers,
    pack_harness,
):
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import get_auth_service

    project, _agent, original_pack, _source, _config = pack_harness
    contents = await download(client, logged_in_headers, project)
    async with session_scope() as session:
        recipient = User(
            username="archive-recipient",
            password=get_auth_service().get_password_hash("archive-test-password"),
            is_active=True,
            is_superuser=False,
        )
        session.add(recipient)
        await session.flush()
        recipient_id = str(recipient.id)
    client.cookies.clear()
    login = await client.post(
        "api/v1/login",
        data={"username": "archive-recipient", "password": "archive-test-password"},  # pragma: allowlist secret
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    denied = await client.get(f"api/v1/projects/{original_pack}/tool-pack", headers=headers)
    assert denied.status_code == 404
    response = await upload(client, headers, contents)
    assert response.status_code == 201, response.text
    imported = response.json()[0]
    graph = Graph.from_payload(deepcopy(imported["data"]), instantiate_components=False, user_id=recipient_id)
    graph.set_run_id()
    node = next(node for node in imported["data"]["nodes"] if node["data"].get(TOOL_ORIGIN))
    component = RunFlowComponent(_user_id=recipient_id, _vertex=graph.get_vertex(node["id"]))
    template = node["data"]["node"]["template"]
    component.set_attributes({key: field.get("value") for key, field in template.items() if isinstance(field, dict)})
    tools = await component._get_tools()
    result = await tools[0].ainvoke({"flow_tweak_data": {"ChatInput-echo~input_value": "independent handoff"}})
    assert "independent handoff" in str(result)
    binding = ToolPackToolBinding.model_validate(node["data"][TOOL_ORIGIN]["tool_pack"])
    async with session_scope() as session:
        pack = await session.get(Folder, binding.reference.project_id)
        version = await session.get(FlowVersion, binding.version_id)
        assert str(pack.user_id) == recipient_id
        assert str(version.user_id) == recipient_id
    # Its own archive can be exported and imported a second time.
    again = await upload(client, headers, await download(client, headers, imported["folder_id"]))
    assert again.status_code == 201, again.text


async def test_creation_hook_denial_on_dependency_rolls_back_root(client, logged_in_headers, pack_harness, monkeypatch):
    from fastapi import HTTPException

    contents = await download(client, logged_in_headers, pack_harness[0])
    calls = []

    async def reject_second(context):
        calls.append(context.requested_name)
        if len(calls) == 2:
            raise HTTPException(403, "Project limit reached")

    monkeypatch.setattr("langflow.api.v1.project_compositions.enforce_pre_creation", reject_second)
    async with session_scope() as session:
        before = set((await session.exec(select(Folder.id))).all())
    response = await upload(client, logged_in_headers, contents)
    assert response.status_code == 403
    assert len(calls) == 2
    async with session_scope() as session:
        assert set((await session.exec(select(Folder.id))).all()) == before


async def test_composition_scrubs_graph_and_configuration_secrets_before_revising(
    client,
    logged_in_headers,
    pack_harness,
):
    project, _agent, pack, source, config = pack_harness
    marker = "composition-redaction-fixture"
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(source))
        data = deepcopy(flow.data)
        field = data["nodes"][0]["data"]["node"]["template"]["session_id"]
        field.update(value=marker, password=True)
        flow.data = data
        session.add(flow)
    manifest = (await client.get(f"api/v1/projects/{pack}/tool-pack", headers=logged_in_headers)).json()
    await save_config(
        client,
        logged_in_headers,
        project,
        {
            **config,
            "tool_packs": [manifest["reference"]],
            "custom_settings": {"api_key": marker},
        },
    )
    contents = await download(client, logged_in_headers, project)
    with zipfile.ZipFile(io.BytesIO(contents)) as archive:
        assert all(marker.encode() not in archive.read(member) for member in archive.namelist())
    response = await upload(client, logged_in_headers, contents)
    assert response.status_code == 201, response.text
    imported = await stored_flow(response.json()[0]["id"])
    binding = ToolPackToolBinding.model_validate(pack_node(imported)["data"][TOOL_ORIGIN]["tool_pack"])
    async with session_scope() as session:
        version = await session.get(FlowVersion, binding.version_id)
        assert marker not in json.dumps(version.data)
        assert flow_revision(version.data) == binding.tool.revision


async def test_bound_flow_import_keeps_required_secret_widgets_for_recipient(client, logged_in_headers, active_user):
    from tests.unit.api.v1.test_project_instruction_bindings import setup_binding

    project, _agent, source, config = await setup_binding(client, logged_in_headers, active_user)
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(source))
        data = deepcopy(flow.data)
        template = data["nodes"][0]["data"]["node"]["template"]
        template["required_secret"] = {
            "name": "required_secret",
            "type": "str",
            "password": True,
            "required": True,
            "value": "bound-source-redaction-fixture",
        }
        flow.data = data
        session.add(flow)
    config["flow_bindings"]["system_prompt"]["revision"] = flow_revision(data)
    await save_config(client, logged_in_headers, project, config)
    response = await upload(client, logged_in_headers, await download(client, logged_in_headers, project))
    assert response.status_code == 201, response.text
    imported = next(
        flow
        for flow in response.json()
        if any("required_secret" in node["data"]["node"]["template"] for node in flow["data"]["nodes"])
    )
    secret = imported["data"]["nodes"][0]["data"]["node"]["template"]["required_secret"]
    assert secret["required"] is True
    assert secret["value"] is None
