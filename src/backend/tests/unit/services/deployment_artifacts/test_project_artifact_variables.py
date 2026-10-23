from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import Response
from langflow.api.v1 import projects
from langflow.services.database.models.folder.model import Folder
from langflow.services.deployment_artifacts import builder
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE
from lfx.services.settings.base import Settings

from .test_project_artifact import MODULE, _flow, _session_with_flows, _snapshot_session_for_flows


def test_typed_deployment_variables_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LANGFLOW_DEPLOYMENT_TYPED_VARIABLES_ENABLED", raising=False)
    assert Settings().deployment_typed_variables_enabled is False


def test_typed_deployment_variables_can_be_enabled(monkeypatch):
    monkeypatch.setenv("LANGFLOW_DEPLOYMENT_TYPED_VARIABLES_ENABLED", "true")
    assert Settings().deployment_typed_variables_enabled is True


def _bound_flow(owner_id, project_id, names):
    flow = _flow(owner_id=owner_id, project_id=project_id)
    flow.data = {
        "nodes": [
            {
                "data": {
                    "node": {
                        "template": {
                            f"field_{index}": {"name": f"field_{index}", "load_from_db": True, "value": name}
                            for index, name in enumerate(names)
                        }
                    }
                }
            }
        ],
        "edges": [],
    }
    return flow


async def _typed_export(project, flows, kinds, *, snapshot=False):
    session = _snapshot_session_for_flows(project, flows) if snapshot else _session_with_flows(flows)
    with (
        patch(f"{MODULE}.authorized_or_owner_scoped", new_callable=AsyncMock, return_value=project),
        patch(f"{MODULE}.ensure_project_permission", new_callable=AsyncMock),
        patch(f"{MODULE}.ensure_flows_permission", new_callable=AsyncMock),
        patch(
            f"{MODULE}.get_settings_service",
            return_value=SimpleNamespace(
                settings=SimpleNamespace(
                    deployment_typed_variables_enabled=True,
                )
            ),
        ),
        patch(f"{MODULE}._known_variable_kinds", new_callable=AsyncMock, return_value=kinds),
    ):
        build = builder.build_project_deployment_snapshot if snapshot else builder.build_project_artifact
        return await build(session, SimpleNamespace(id=uuid4(), is_superuser=False), project.id)


def _manifest(artifact):
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        return json.loads(archive.read("manifest.json"))


@pytest.mark.asyncio
async def test_typed_artifact_has_deterministic_declarations_and_keeps_legacy_names():
    owner_id = uuid4()
    project = Folder(id=uuid4(), name="Typed requirements", user_id=owner_id)
    first = _bound_flow(owner_id, project.id, ["SECRET_KEY", "PLAIN_URL", "LEGACY_NAME", "SECRET_KEY"])
    second = _bound_flow(owner_id, project.id, ["PLAIN_URL"])
    kinds = {
        "SECRET_KEY": "secret",  # pragma: allowlist secret
        "PLAIN_URL": "plain",
        "LEGACY_NAME": None,
        "UNUSED": "secret",
    }
    artifact = await _typed_export(project, [first, second], kinds)
    manifest = _manifest(artifact)
    expected = [
        {"name": "LEGACY_NAME", "kind": None},
        {"name": "PLAIN_URL", "kind": "plain"},
        {"name": "SECRET_KEY", "kind": "secret"},
    ]
    assert manifest["schema_version"] == 7
    assert manifest["required_variable_declarations"] == expected
    assert manifest["required_variables"] == ["LEGACY_NAME", "PLAIN_URL", "SECRET_KEY"]
    entries = {item["id"]: item for item in manifest["flows"]}
    assert entries[str(first.id)]["required_variable_declarations"] == expected
    assert entries[str(second.id)]["required_variable_declarations"] == [{"name": "PLAIN_URL", "kind": "plain"}]
    assert _manifest(await _typed_export(project, [second, first], dict(reversed(list(kinds.items()))))) == manifest


@pytest.mark.asyncio
async def test_typed_snapshot_and_artifact_declarations_match_through_route():
    owner_id = uuid4()
    project = Folder(id=uuid4(), name="Snapshot requirements", user_id=owner_id)
    flow = _bound_flow(owner_id, project.id, ["OWNER_KEY", "OWNER_URL", "UNKNOWN_KIND"])
    kinds = {"OWNER_KEY": "secret", "OWNER_URL": "plain", "UNKNOWN_KIND": None}
    manifest = _manifest(await _typed_export(project, [flow], kinds))
    snapshot = await _typed_export(project, [flow], kinds, snapshot=True)
    with (
        patch.object(projects, "_begin_deployment_snapshot_transaction", new_callable=AsyncMock),
        patch.object(projects, "build_project_deployment_snapshot", new_callable=AsyncMock, return_value=snapshot),
    ):
        response = await projects.read_project_deployment_snapshot(
            session=AsyncMock(), project_id=project.id, current_user=SimpleNamespace(id=owner_id), response=Response()
        )
    body = response.model_dump(mode="json")
    assert body["schema_version"] == 7
    assert body["required_variable_declarations"] == manifest["required_variable_declarations"]
    assert body["required_variables"] == manifest["required_variables"]
    assert "required_variable_declarations" not in body["flows"][0]
    assert "required_variables" not in body["flows"][0]


@pytest.mark.asyncio
async def test_enabled_typed_export_without_bindings_keeps_legacy_schema():
    owner_id = uuid4()
    project = Folder(id=uuid4(), name="No requirements", user_id=owner_id)
    manifest = _manifest(await _typed_export(project, [_flow(owner_id=owner_id, project_id=project.id)], {}))
    assert manifest["schema_version"] == 1
    assert "required_variable_declarations" not in manifest
    assert "required_variable_declarations" not in manifest["flows"][0]


@pytest.mark.asyncio
async def test_typed_metadata_query_selects_only_owner_names_and_types():
    owner_id = uuid4()
    result = MagicMock()
    result.all.return_value = [
        ("SECRET_KEY", CREDENTIAL_TYPE),
        ("PLAIN_URL", GENERIC_TYPE),
        ("LEGACY", None),
        ("FUTURE", "Future"),
    ]
    session = AsyncMock()
    session.exec.return_value = result

    assert await builder._known_variable_kinds(session, owner_id) == {
        "SECRET_KEY": "secret",  # pragma: allowlist secret
        "PLAIN_URL": "plain",
        "LEGACY": None,
        "FUTURE": None,
    }

    statement = session.exec.await_args.args[0]
    assert [column.name for column in statement.selected_columns] == ["name", "type"]
    assert owner_id in statement.compile().params.values()
    assert "variable.user_id =" in str(statement)


@pytest.mark.asyncio
async def test_typed_metadata_without_owner_does_not_query():
    session = AsyncMock()
    assert await builder._known_variable_kinds(session, None) == {}
    session.exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_typed_metadata_rejects_conflicting_kinds_without_exposing_names():
    result = MagicMock()
    result.all.return_value = [("PRIVATE_NAME", CREDENTIAL_TYPE), ("PRIVATE_NAME", GENERIC_TYPE)]
    session = AsyncMock()
    session.exec.return_value = result
    with pytest.raises(builder.ProjectArtifactError, match="conflicting variable kinds") as raised:
        await builder._known_variable_kinds(session, uuid4())
    assert "PRIVATE_NAME" not in str(raised.value)


def test_merge_variable_declarations_rejects_conflicting_kinds():
    requirement = builder.ProjectArtifactRequiredVariable
    with pytest.raises(builder.ProjectArtifactError, match="conflicting variable kinds"):
        builder._merge_variable_declarations(
            [
                (requirement(name="SAME_NAME", kind="secret"),),
                (requirement(name="SAME_NAME", kind="plain"),),
            ]
        )


def test_typed_declarations_refuse_unverified_mcp_names_without_echoing_them():
    with pytest.raises(builder.ProjectArtifactError, match="required variable metadata is unavailable") as raised:
        builder._variable_declarations(["UNVERIFIED_PRIVATE_NAME"], {})
    assert "UNVERIFIED_PRIVATE_NAME" not in str(raised.value)


@pytest.mark.asyncio
async def test_typed_declarations_include_mcp_requirements_without_changing_legacy_names():
    owner_id = uuid4()
    project = Folder(id=uuid4(), name="MCP requirements", user_id=owner_id)
    flow = _bound_flow(owner_id, project.id, ["OWNER_URL"])
    flow.data["nodes"][0]["data"]["node"]["template"]["mcp_server"] = {
        "name": "mcp_server",
        "type": "mcp",
        "value": {
            "name": "demo",
            "config": {"url": "https://example.com/mcp", "headers": {"Authorization": "{{MCP_KEY}}"}},
        },
    }
    kinds = {"OWNER_URL": "plain", "MCP_KEY": "secret"}
    manifest = _manifest(await _typed_export(project, [flow], kinds))
    snapshot = await _typed_export(project, [flow], kinds, snapshot=True)
    assert manifest["required_variables"] == ["OWNER_URL"]
    assert manifest["required_mcp_variables"] == ["MCP_KEY"]
    assert manifest["required_variable_declarations"] == [
        {"name": "MCP_KEY", "kind": "secret"},
        {"name": "OWNER_URL", "kind": "plain"},
    ]
    assert snapshot.required_variable_declarations == tuple(
        builder.ProjectArtifactRequiredVariable(**entry) for entry in manifest["required_variable_declarations"]
    )
