"""Project save hooks exercise the real API, transaction and snapshot store."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.folder.save_context import LangflowProjectSaveContext
from langflow.services.deps import session_scope
from lfx.projects.lifecycle import (
    FlowSelector,
    PreparedSave,
    ProjectConfigError,
    ProjectResourceUnavailableError,
    ProjectSaveConflictError,
    SourceVersionReference,
)
from sqlmodel import select

from tests.unit.api.v1.test_project_config_write_through import (
    agent_flow_data,
    create_flow,
    create_project,
    echo_flow_data,
    save_config,
    stored_flow,
    stored_template,
)


@pytest.fixture
def installed_save_plugin(monkeypatch, tmp_path):
    """Use real installed distribution metadata, not a mocked entry-point list."""
    import importlib
    import shutil
    import sys

    import tomllib
    from lfx.projects import get_project_type, registry
    from lfx.services.deps import get_settings_service

    fixture = Path(__file__).resolve().parents[5] / "lfx/tests/data/project_type_plugin"
    metadata = tomllib.loads((fixture / "pyproject.toml").read_text())["project"]
    site = tmp_path / "site-packages"
    shutil.copytree(fixture / "sample_project_types", site / "sample_project_types")
    info = site / "lfx_test_project_types-0.0.1.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: lfx-test-project-types\nVersion: 0.0.1\n")
    (info / "entry_points.txt").write_text(
        "[lfx.project_type.adapters]\n"
        + "".join(
            f"{name} = {value}\n" for name, value in metadata["entry-points"]["lfx.project_type.adapters"].items()
        )
    )
    monkeypatch.syspath_prepend(str(site))
    importlib.invalidate_caches()
    original = registry._PROJECT_TYPES
    isolated = type(original)(
        adapter_type=original.adapter_type,
        entry_point_group=original.entry_point_group,
        config_section_path=original.config_section_path,
    )
    for name in original.list_keys():
        if name != "support-desk":
            isolated.register_class(name, original.get_class(name))
    monkeypatch.setattr(registry, "_PROJECT_TYPES", isolated)
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    yield type(get_project_type("support-desk"))
    sys.modules.pop("sample_project_types", None)


@pytest.fixture
async def plugin_project(client, logged_in_headers, active_user, installed_save_plugin):  # noqa: ARG001
    project = await create_project(client, logged_in_headers, name="Support hooks", project_type="support-desk")
    target = await create_flow(active_user, folder_id=project, name="Support agent", data=agent_flow_data())
    source = await create_flow(active_user, folder_id=project, name="Support source", data=echo_flow_data())
    return project, target, source


async def versions(flow_id):
    async with session_scope() as session:
        return list((await session.exec(select(FlowVersion).where(FlowVersion.flow_id == UUID(flow_id)))).all())


async def test_installed_hook_normalizes_pins_and_preserves_canvas(client, logged_in_headers, plugin_project):
    project, target, source = plugin_project
    saved = await save_config(
        client,
        logged_in_headers,
        project,
        {"instructions": "  Answer briefly.  ", "source_id": source, "source_version": str(uuid4())},
    )
    assert saved["project_config"]["instructions"] == "Answer briefly."
    assert (await stored_template(target))["system_prompt"]["value"] == "Answer briefly."
    snapshot = (await versions(source))[0]
    assert str(snapshot.id) == saved["project_config"]["source_version"]
    assert snapshot.data == (await stored_flow(source)).data
    assert saved["restore_version_ids"][target]
    again = await save_config(client, logged_in_headers, project, saved["project_config"])
    assert again["flows_updated"] == 0
    assert len(await versions(source)) == 1
    async with session_scope() as session:
        row = await session.get(Flow, UUID(target))
        data = deepcopy(row.data)
        data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] = "Canvas wins"
        row.data = data
        session.add(row)
    saved = await save_config(
        client,
        logged_in_headers,
        project,
        {"instructions": "New form", "_applied": {target: {"Agent-1": {"system_prompt": "Canvas wins"}}}},
    )
    assert saved["fields_skipped"] == 1
    assert (await stored_template(target))["system_prompt"]["value"] == "Canvas wins"


async def test_failure_after_pinning_rolls_back_config_and_new_versions(
    client, logged_in_headers, plugin_project, installed_save_plugin, monkeypatch
):
    project, target, source = plugin_project
    previous = await save_config(client, logged_in_headers, project, {"instructions": "Old"})
    before = (await stored_flow(target)).data
    original = installed_save_plugin.save_config

    async def failing(self, request, ctx):
        await original(self, request, ctx)
        msg = "Rejected after snapshot"
        raise ProjectConfigError(msg)

    monkeypatch.setattr(installed_save_plugin, "save_config", failing)
    response = await client.patch(
        f"/api/v1/projects/{project}",
        headers=logged_in_headers,
        json={"project_config": {"instructions": "New", "source_id": source}},
    )
    assert response.status_code == 422, response.text
    assert await versions(source) == []
    assert (await stored_flow(target)).data == before
    async with session_scope() as session:
        assert (await session.get(Folder, UUID(project))).project_config == previous["project_config"]


@pytest.mark.parametrize("invalid", ["foreign", "duplicate", "token", "baseline"])
async def test_compose_results_cannot_escape_targets(
    client, logged_in_headers, plugin_project, installed_save_plugin, monkeypatch, invalid
):
    project, target, _ = plugin_project
    original = installed_save_plugin.compose

    def compose(self, prepared, ctx):
        changes = original(self, prepared, ctx)
        first = next(change for change in changes if str(change.flow_id) == target)
        if invalid == "foreign":
            return (replace(first, flow_id=uuid4()),)
        if invalid == "duplicate":
            return (first, first)
        if invalid == "baseline":
            return (replace(first, applied_values=[]),)
        return (replace(first, token="forged"),)  # noqa: S106 -- invalid opaque read token

    before = (await stored_flow(target)).data
    monkeypatch.setattr(installed_save_plugin, "compose", compose)
    response = await client.patch(
        f"/api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": {"instructions": "Reject me"}}
    )
    assert response.status_code == 422, response.text
    assert (await stored_flow(target)).data == before
    assert await versions(target) == []


async def test_empty_field_types_run_hooks_and_omission_does_not(
    client, logged_in_headers, plugin_project, installed_save_plugin, monkeypatch
):
    project, _, _ = plugin_project
    monkeypatch.setattr(installed_save_plugin, "fields", ())
    calls = []

    async def normalize(_self, request, _ctx):
        calls.append(request.operation)
        return PreparedSave(None if request.config is None else {"normalized": True})

    monkeypatch.setattr(installed_save_plugin, "save_config", normalize)
    response = await client.post(
        "/api/v1/projects/",
        headers=logged_in_headers,
        json={"name": "Created with hooks", "project_type": "support-desk", "project_config": {}},
    )
    assert response.status_code == 201, response.text
    assert response.json()["project_config"] == {"normalized": True}
    saved = await save_config(client, logged_in_headers, project, {})
    assert saved["project_config"] == {"normalized": True}
    response = await client.patch(
        f"/api/v1/projects/{project}", headers=logged_in_headers, json={"description": "Metadata"}
    )
    assert response.status_code == 200
    cleared = await save_config(client, logged_in_headers, project, None)
    assert cleared["project_config"] is None
    assert calls == ["create", "replace", "clear"]


async def test_context_tokens_require_execute_and_views_are_detached(active_user, plugin_project):
    project, target, source = plugin_project
    async with session_scope() as session:
        ctx = LangflowProjectSaveContext(session, active_user)
        await ctx.start_save(await session.get(Folder, UUID(project)))
        view = await ctx.read_flow(FlowSelector(id=UUID(source)), access="read")
        with pytest.raises(ProjectConfigError, match="execute"):
            await ctx.pin_sources((view.token,), label="forbidden")
        view = await ctx.read_flow(FlowSelector(id=UUID(source)), access="execute")
        original = deepcopy(view.data)
        view.data.clear()
        (pinned,) = await ctx.pin_sources((view.token,), label="test")
        assert pinned.data == original
        assert (await session.get(Flow, UUID(source))).data == original
        with pytest.raises(ProjectConfigError, match="execute"):
            await ctx.pin_sources(("forged",), label="forbidden")
        wrong = SourceVersionReference(uuid4(), pinned.reference.version_id, pinned.reference.revision)
        with pytest.raises(ProjectResourceUnavailableError):
            await ctx.read_saved_source(wrong)
        wrong = replace(pinned.reference, flow_id=UUID(target))
        with pytest.raises(ProjectConfigError, match="snapshot is unavailable"):
            await ctx.read_saved_source(wrong)


@pytest.mark.parametrize("field", ["data", "description"])
@pytest.mark.parametrize("role", ["source", "target"])
async def test_context_detects_changed_read_state(active_user, plugin_project, field, role):
    project, target, source = plugin_project
    selected = source if role == "source" else target
    async with session_scope() as session:
        ctx = LangflowProjectSaveContext(session, active_user)
        await ctx.start_save(await session.get(Folder, UUID(project)))
        await ctx.read_flow(FlowSelector(id=UUID(selected)), access="execute" if role == "source" else "read")
        row = await session.get(Flow, UUID(selected))
        if field == "data":
            data = deepcopy(row.data)
            data["nodes"][0]["position"] = {"x": 42, "y": 17}
            row.data = data
        else:
            row.description = "Changed after read"
        session.add(row)
        await session.flush()
        with pytest.raises(ProjectSaveConflictError):
            await ctx.verify_unchanged()
        await session.rollback()


async def test_failure_after_staging_graph_rolls_back_entire_save(
    client, logged_in_headers, active_user, plugin_project, monkeypatch
):
    from langflow.services.database.models.folder import config_writer

    project, first, source = plugin_project
    second = await create_flow(active_user, folder_id=project, name="Second agent", data=agent_flow_data())
    old = {flow_id: (await stored_flow(flow_id)).data for flow_id in (first, second)}
    original = config_writer._restore_point
    calls = 0

    async def fail_second(session, flow):
        nonlocal calls
        calls += 1
        if calls == 2:
            await session.flush()
            msg = "internal failure text must not reach the caller"
            raise RuntimeError(msg)
        return await original(session, flow)

    monkeypatch.setattr(config_writer, "_restore_point", fail_second)
    response = await client.patch(
        f"/api/v1/projects/{project}",
        headers=logged_in_headers,
        json={"project_config": {"instructions": "New", "source_id": source}},
    )
    assert response.status_code == 500, response.text
    assert "internal failure text" not in response.text
    for flow_id, data in old.items():
        assert (await stored_flow(flow_id)).data == data
        assert await versions(flow_id) == []
    assert await versions(source) == []
    async with session_scope() as session:
        assert (await session.get(Folder, UUID(project))).project_config is None


async def test_locked_targets_and_restore_failure_preserve_existing_behavior(
    client, logged_in_headers, plugin_project, monkeypatch
):
    from langflow.services.database.models.folder import config_writer

    project, target, _ = plugin_project
    await save_config(client, logged_in_headers, project, {"instructions": "Old"})
    async with session_scope() as session:
        row = await session.get(Flow, UUID(target))
        row.locked = True
        session.add(row)
    saved = await save_config(client, logged_in_headers, project, {"instructions": "New"})
    assert saved["flows_locked"] == 1
    assert (await stored_template(target))["system_prompt"]["value"] == "Old"
    assert saved["project_config"]["_applied"][target]["Agent-1"]["system_prompt"] == "Old"
    async with session_scope() as session:
        row = await session.get(Flow, UUID(target))
        row.locked = False
        session.add(row)

    async def unavailable(*_args, **_kwargs):
        msg = "Restore storage unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr(config_writer, "create_flow_version_entry", unavailable)
    # The previous restore snapshot still matches Old; change only layout to need a new one.
    async with session_scope() as session:
        row = await session.get(Flow, UUID(target))
        data = deepcopy(row.data)
        data["nodes"][0]["position"] = {"x": 123, "y": 456}
        row.data = data
        session.add(row)
    saved = await save_config(client, logged_in_headers, project, {"instructions": "New"})
    assert saved["restore_version_ids"] == {}
    assert (await stored_template(target))["system_prompt"]["value"] == "New"


async def test_missing_plugin_keeps_reads_but_rejects_explicit_saves(client, logged_in_headers, plugin_project):
    project, _, _ = plugin_project
    async with session_scope() as session:
        row = await session.get(Folder, UUID(project))
        row.project_type = "missing-save-plugin"
        row.project_config = {"instructions": "Keep me"}
        session.add(row)
    response = await client.get(f"/api/v1/projects/{project}", headers=logged_in_headers)
    assert response.status_code == 200
    assert response.json()["project_type"] == "missing-save-plugin"
    response = await client.patch(
        f"/api/v1/projects/{project}", headers=logged_in_headers, json={"description": "Still here"}
    )
    assert response.status_code == 200
    for config in ({}, None):
        response = await client.patch(
            f"/api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": config}
        )
        assert response.status_code == 422
    async with session_scope() as session:
        assert (await session.get(Folder, UUID(project))).project_config == {"instructions": "Keep me"}


async def test_normalized_reference_is_authorized_again(
    client, logged_in_headers, plugin_project, installed_save_plugin, monkeypatch
):
    from lfx.inputs.inputs import StrInput
    from lfx.projects import ProjectTypeField

    project, _, _ = plugin_project
    field = ProjectTypeField("library", StrInput(name="library"), references="support-desk")
    monkeypatch.setattr(installed_save_plugin, "fields", (field,))

    async def add_reference(_self, _request, _ctx):
        return PreparedSave(
            {"library": {"project_id": str(uuid4()), "expected_type": "support-desk", "revision": "a" * 64}}
        )

    monkeypatch.setattr(installed_save_plugin, "save_config", add_reference)
    response = await client.patch(f"/api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": {}})
    assert response.status_code == 404, response.text


async def test_execute_denial_is_checked_after_cached_read(active_user, plugin_project, monkeypatch):
    from fastapi import HTTPException
    from langflow.services.authorization import FlowAction
    from langflow.services.database.models.folder import save_context

    project, _, source = plugin_project
    original = save_context.ensure_flow_permission

    async def deny_execute(user, action, **kwargs):
        if action == FlowAction.EXECUTE:
            raise HTTPException(403, "Denied")
        return await original(user, action, **kwargs)

    monkeypatch.setattr(save_context, "ensure_flow_permission", deny_execute)
    async with session_scope() as session:
        ctx = LangflowProjectSaveContext(session, active_user)
        await ctx.start_save(await session.get(Folder, UUID(project)))
        await ctx.read_flow(FlowSelector(id=UUID(source)), access="read")
        with pytest.raises(ProjectResourceUnavailableError, match="not found"):
            await ctx.read_flow(FlowSelector(id=UUID(source)), access="execute")


async def test_scorer_reuses_unchanged_snapshot_but_never_missing_snapshot(client, logged_in_headers, active_user):
    from lfx.projects.bindings import flow_revision
    from lfx.projects.evaluations import scorer_baseline, scorer_outputs

    project = await create_project(client, logged_in_headers, name="Saved scorer", project_type="eval-suite")
    graph = scorer_baseline()["data"]
    scorer = await create_flow(active_user, folder_id=project, name="Scorer", data=graph)
    output = scorer_outputs(graph)[0]
    saved = await save_config(
        client,
        logged_in_headers,
        project,
        {
            "scorer": {
                "flow_id": scorer,
                "node_id": output["node_id"],
                "output_name": output["output_name"],
                "revision": flow_revision(graph),
                "version_id": str(uuid4()),
            }
        },
    )
    config = saved["project_config"]
    version_id = UUID(config["scorer"]["version_id"])
    async with session_scope() as session:
        row = await session.get(Flow, UUID(scorer))
        row.data = {"nodes": [], "edges": []}
        session.add(row)
    again = await save_config(client, logged_in_headers, project, config)
    assert again["project_config"]["scorer"]["version_id"] == str(version_id)
    assert "_applied" not in again["project_config"]
    async with session_scope() as session:
        await session.delete(await session.get(FlowVersion, version_id))
    response = await client.patch(
        f"/api/v1/projects/{project}", headers=logged_in_headers, json={"project_config": config}
    )
    assert response.status_code == 422
    assert "snapshot is unavailable" in response.text
    cleared = await save_config(client, logged_in_headers, project, None)
    assert cleared["project_config"] is None


async def test_required_snapshot_failure_rejects_save(client, logged_in_headers, plugin_project, monkeypatch):
    from langflow.services.database.models.folder import save_context

    project, target, source = plugin_project
    before = (await stored_flow(target)).data

    async def unavailable(*_args, **_kwargs):
        msg = "private snapshot failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(save_context, "create_flow_version_entry", unavailable)
    response = await client.patch(
        f"/api/v1/projects/{project}",
        headers=logged_in_headers,
        json={"project_config": {"instructions": "New", "source_id": source}},
    )
    assert response.status_code == 500
    assert "private snapshot failure" not in response.text
    assert await versions(source) == []
    assert (await stored_flow(target)).data == before


async def test_foreign_source_remains_private(client, logged_in_headers, plugin_project, user_two_api_key):
    client.cookies.clear()
    foreign_project = await create_project(
        client, {"x-api-key": user_two_api_key}, name="Private", project_type="flows"
    )
    response = await client.post(
        "/api/v1/flows/",
        headers={"x-api-key": user_two_api_key},
        json={
            "name": "Private source",
            "folder_id": foreign_project,
            "data": echo_flow_data(),
        },
    )
    assert response.status_code == 201, response.text
    foreign_id = response.json()["id"]
    async with session_scope() as session:
        foreign = await session.get(Flow, UUID(foreign_id))
        local = await session.get(Flow, UUID(plugin_project[1]))
        assert foreign.user_id != local.user_id
    project, target, _ = plugin_project
    before = (await stored_flow(target)).data
    response = await client.patch(
        f"/api/v1/projects/{project}",
        headers=logged_in_headers,
        json={"project_config": {"instructions": "New", "source_id": foreign_id}},
    )
    assert response.status_code == 404, response.text
    assert (await stored_flow(target)).data == before


async def test_configured_type_conversion_requires_clear(client, logged_in_headers, plugin_project):
    project, _, _ = plugin_project
    await save_config(client, logged_in_headers, project, {"instructions": "Configured"})
    response = await client.patch(
        f"/api/v1/projects/{project}", headers=logged_in_headers, json={"project_type": "flows"}
    )
    assert response.status_code == 422
    await save_config(client, logged_in_headers, project, None)
    response = await client.patch(
        f"/api/v1/projects/{project}", headers=logged_in_headers, json={"project_type": "flows"}
    )
    assert response.status_code == 200
