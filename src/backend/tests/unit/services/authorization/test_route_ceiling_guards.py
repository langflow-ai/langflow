"""Regression tests for access-ceiling guards added to execution / mutation routes.

PR #13293 added ``ensure_*_permission`` guards to four route areas that
previously escaped the external access ceiling:

* ``mcp_utils.handle_call_tool`` (flow EXECUTE)
* ``flow_version`` create/activate/delete (flow WRITE/DELETE)
* ``files`` upload/delete (flow WRITE)
* ``memories`` create/update/delete/flush/regenerate (knowledge-base actions)

These tests drive the real route handlers with the data services mocked,
verifying two invariants for each newly-guarded action:

1. A viewer-ceiling caller is denied with HTTP 403 *before* the data service is
   touched (the deny-only ceiling fires ahead of owner-override and the
   ``AUTHZ_ENABLED`` gate).
2. With no ceiling installed, the owner-override path returns early and the
   route proceeds to the underlying service — preserving feature-off behavior.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.authorization.access_ceiling import (
    ExternalAccessContext,
    set_current_external_access_context,
)

from ._common import (
    _StubAuthorizationService,
    install_audit_recorder,
    install_authz,
    install_settings,
)


@pytest.fixture
def owner():
    """A non-superuser acting as the resource owner."""
    return SimpleNamespace(id=uuid4(), username="owner", is_superuser=False)


@pytest.fixture(autouse=True)
def _wire_guard_services(monkeypatch):
    """Install pass-through authz services so guards run the real ceiling path.

    ``AUTHZ_ENABLED=False`` mirrors the OSS default: the only thing that can deny
    is the external access ceiling, which is checked before the gate.
    """
    install_settings(monkeypatch, authz_enabled=False, audit_enabled=True)
    install_authz(monkeypatch, _StubAuthorizationService(allow=True))
    install_audit_recorder(monkeypatch)


def _viewer_ceiling() -> ExternalAccessContext:
    return ExternalAccessContext(provider="openrag", subject="s-1", level="viewer")


def _make_flow(owner_id):
    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        workspace_id=None,
        folder_id=None,
        data={"nodes": [], "edges": []},
        name="flow",
    )


# --------------------------------------------------------------------------- #
# C1 — mcp_utils.handle_call_tool (flow EXECUTE)
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_mcp_call_tool_viewer_denied_before_run(monkeypatch, owner):
    from langflow.api.v1 import mcp_utils

    flow = _make_flow(owner.id)
    monkeypatch.setattr(mcp_utils, "get_flow_snake_case", AsyncMock(return_value=flow))
    monkeypatch.setattr(mcp_utils, "get_mcp_config", lambda: SimpleNamespace(enable_progress_notifications=False))
    run_spy = AsyncMock()
    monkeypatch.setattr(mcp_utils, "simple_run_flow", run_spy)
    monkeypatch.setattr(mcp_utils, "with_db_session", lambda fn: fn(MagicMock()))
    mcp_utils.current_user_ctx.set(owner)

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await mcp_utils.handle_call_tool(name="flow", arguments={}, server=MagicMock())
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    run_spy.assert_not_awaited()


@pytest.mark.anyio
async def test_mcp_call_tool_owner_runs_without_ceiling(monkeypatch, owner):
    from langflow.api.v1 import mcp_utils

    flow = _make_flow(owner.id)
    monkeypatch.setattr(mcp_utils, "get_flow_snake_case", AsyncMock(return_value=flow))
    monkeypatch.setattr(mcp_utils, "get_mcp_config", lambda: SimpleNamespace(enable_progress_notifications=False))
    run_spy = AsyncMock(return_value=SimpleNamespace(outputs=[]))
    monkeypatch.setattr(mcp_utils, "simple_run_flow", run_spy)
    monkeypatch.setattr(mcp_utils, "with_db_session", lambda fn: fn(MagicMock()))
    mcp_utils.current_user_ctx.set(owner)

    await mcp_utils.handle_call_tool(name="flow", arguments={}, server=MagicMock())

    run_spy.assert_awaited_once()


# --------------------------------------------------------------------------- #
# H2 — flow_version create / activate / delete
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_flow_version_create_snapshot_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import flow_version

    flow = _make_flow(owner.id)
    monkeypatch.setattr(flow_version, "_get_user_flow", AsyncMock(return_value=flow))
    create_spy = AsyncMock()
    monkeypatch.setattr(flow_version, "create_flow_version_entry", create_spy)

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await flow_version.create_snapshot(flow_id=flow.id, current_user=owner, session=MagicMock(), body=None)
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    create_spy.assert_not_awaited()


@pytest.mark.anyio
async def test_flow_version_delete_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import flow_version

    flow = _make_flow(owner.id)
    monkeypatch.setattr(flow_version, "_get_user_flow", AsyncMock(return_value=flow))
    delete_spy = AsyncMock()
    monkeypatch.setattr(flow_version, "delete_flow_version_entry", delete_spy)
    monkeypatch.setattr(flow_version, "get_flow_version_entry_or_raise", AsyncMock())

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await flow_version.delete_version_entry(
                flow_id=flow.id, version_id=uuid4(), current_user=owner, session=MagicMock()
            )
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    delete_spy.assert_not_awaited()


@pytest.mark.anyio
async def test_flow_version_create_snapshot_owner_proceeds(monkeypatch, owner):
    from langflow.api.v1 import flow_version

    flow = _make_flow(owner.id)
    monkeypatch.setattr(flow_version, "_get_user_flow", AsyncMock(return_value=flow))
    entry = SimpleNamespace(id=uuid4())
    create_spy = AsyncMock(return_value=entry)
    monkeypatch.setattr(flow_version, "create_flow_version_entry", create_spy)
    monkeypatch.setattr(flow_version, "_version_to_read", lambda e: e)

    result = await flow_version.create_snapshot(flow_id=flow.id, current_user=owner, session=MagicMock(), body=None)

    create_spy.assert_awaited_once()
    assert result is entry


# --------------------------------------------------------------------------- #
# F19 — files upload / delete (flow WRITE)
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_files_upload_viewer_denied(owner):
    from langflow.api.v1 import files

    flow = _make_flow(owner.id)
    storage = MagicMock(save_file=AsyncMock())
    settings_service = SimpleNamespace(settings=SimpleNamespace(max_file_size_upload=100))
    upload = SimpleNamespace(size=1, filename="x.txt", read=AsyncMock(return_value=b"data"))

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await files.upload_file(
                file=upload,
                flow=flow,
                current_user=owner,
                storage_service=storage,
                settings_service=settings_service,
            )
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    storage.save_file.assert_not_awaited()


@pytest.mark.anyio
async def test_files_delete_viewer_denied(owner):
    from langflow.api.v1 import files

    flow = _make_flow(owner.id)
    storage = MagicMock(delete_file=AsyncMock())

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await files.delete_file(file_name="x.txt", flow=flow, current_user=owner, storage_service=storage)
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    storage.delete_file.assert_not_awaited()


@pytest.mark.anyio
async def test_files_delete_owner_proceeds(owner):
    from langflow.api.v1 import files

    flow = _make_flow(owner.id)
    storage = MagicMock(delete_file=AsyncMock())

    result = await files.delete_file(file_name="x.txt", flow=flow, current_user=owner, storage_service=storage)

    storage.delete_file.assert_awaited_once()
    assert "deleted successfully" in result["message"]


# --------------------------------------------------------------------------- #
# F20 — memories create / update / delete / flush / regenerate
# --------------------------------------------------------------------------- #


def _install_memory_service(monkeypatch, **methods):
    from langflow.api.v1 import memories

    service = SimpleNamespace(**methods)
    monkeypatch.setattr(memories, "get_memory_base_service", lambda: service)
    return service


@pytest.mark.anyio
async def test_memory_create_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import memories

    create_spy = AsyncMock()
    _install_memory_service(monkeypatch, create=create_spy)
    payload = SimpleNamespace()

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await memories.create_memory_base(current_user=owner, payload=payload)
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    create_spy.assert_not_awaited()


@pytest.mark.anyio
async def test_memory_delete_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import memories

    delete_spy = AsyncMock(return_value=True)
    mb = SimpleNamespace(user_id=owner.id, kb_name="kb")
    _install_memory_service(monkeypatch, delete=delete_spy, get=AsyncMock(return_value=mb))

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await memories.delete_memory_base(memory_base_id=uuid4(), current_user=owner)
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    delete_spy.assert_not_awaited()


@pytest.mark.anyio
async def test_memory_flush_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import memories

    trigger_spy = AsyncMock(return_value=uuid4())
    mb = SimpleNamespace(user_id=owner.id, kb_name="kb")
    _install_memory_service(monkeypatch, trigger_ingestion=trigger_spy, get=AsyncMock(return_value=mb))

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await memories.flush_memory_base(
                memory_base_id=uuid4(), current_user=owner, body=SimpleNamespace(session_id="s")
            )
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    trigger_spy.assert_not_awaited()


@pytest.mark.anyio
async def test_memory_regenerate_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import memories

    regen_spy = AsyncMock(return_value=[])
    mb = SimpleNamespace(user_id=owner.id, kb_name="kb")
    _install_memory_service(monkeypatch, regenerate=regen_spy, get=AsyncMock(return_value=mb))

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await memories.regenerate_memory_base(memory_base_id=uuid4(), current_user=owner)
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    regen_spy.assert_not_awaited()


@pytest.mark.anyio
async def test_memory_delete_owner_proceeds(monkeypatch, owner):
    """An editor (delete is now in the editor ceiling) deletes their own memory base."""
    from langflow.api.v1 import memories

    delete_spy = AsyncMock(return_value=True)
    mb = SimpleNamespace(user_id=owner.id, kb_name="kb")
    _install_memory_service(monkeypatch, delete=delete_spy, get=AsyncMock(return_value=mb))

    set_current_external_access_context(ExternalAccessContext(provider="openrag", subject="s-1", level="editor"))
    try:
        await memories.delete_memory_base(memory_base_id=uuid4(), current_user=owner)
    finally:
        set_current_external_access_context(None)

    delete_spy.assert_awaited_once()


# --------------------------------------------------------------------------- #
# endpoints.custom_component / custom_component_update (direct ceiling, "create")
#
# These routes instantiate posted component code and are not tied to a single
# owned resource, so they enforce the deny-only ceiling primitive directly
# instead of an ``ensure_*_permission`` guard.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_custom_component_viewer_denied_before_build(monkeypatch, owner):
    from langflow.api.v1 import endpoints

    build_spy = MagicMock()
    monkeypatch.setattr(endpoints, "build_custom_component_template", build_spy)
    raw_code = SimpleNamespace(code="print('x')", frontend_node=None)

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await endpoints.custom_component(raw_code=raw_code, user=owner, request=MagicMock())
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    build_spy.assert_not_called()


@pytest.mark.anyio
async def test_custom_component_update_viewer_denied_before_build(monkeypatch, owner):
    from langflow.api.v1 import endpoints

    build_spy = MagicMock()
    monkeypatch.setattr(endpoints, "build_custom_component_template", build_spy)
    code_request = SimpleNamespace(code="print('x')", tool_mode=False, get_template=dict)

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await endpoints.custom_component_update(code_request=code_request, user=owner, request=MagicMock())
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    build_spy.assert_not_called()


@pytest.mark.anyio
async def test_custom_component_editor_passes_ceiling(monkeypatch, owner):
    """An editor ceiling allows component instantiation (create is in the editor set)."""
    from langflow.api.v1 import endpoints

    # Stub the build pipeline so the route returns without real execution; the
    # point is that the ceiling check does NOT short-circuit for an editor.
    instance = MagicMock()
    instance.update_frontend_node = AsyncMock(return_value={"tool_mode": False})
    monkeypatch.setattr(
        endpoints,
        "build_custom_component_template",
        MagicMock(return_value=({"tool_mode": False}, instance)),
    )
    monkeypatch.setattr(endpoints, "get_instance_name", lambda _i: "MyComponent")
    monkeypatch.setattr(endpoints, "_requires_component_hash_lookups", lambda *_a, **_k: False)
    # Settings: custom components allowed, no admin-only gate.
    settings = SimpleNamespace(allow_custom_components=True, custom_component_admin_only=False)
    monkeypatch.setattr(endpoints, "get_settings_service", lambda: SimpleNamespace(settings=settings))
    # ``isinstance(instance, Component)`` must be False so the optional
    # run_and_validate_update_outputs branch is skipped for this MagicMock.
    raw_code = SimpleNamespace(code="print('x')", frontend_node=None)
    request = SimpleNamespace(state=SimpleNamespace(locale="en"))

    set_current_external_access_context(ExternalAccessContext(provider="openrag", subject="s-1", level="editor"))
    try:
        result = await endpoints.custom_component(raw_code=raw_code, user=owner, request=request)
    finally:
        set_current_external_access_context(None)

    assert result.type == "MyComponent"


# --------------------------------------------------------------------------- #
# endpoints.create_upload_file — deprecated upload (flow WRITE)
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_deprecated_upload_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import endpoints

    flow = _make_flow(owner.id)
    save_spy = MagicMock()
    monkeypatch.setattr(endpoints, "save_uploaded_file", save_spy)
    settings_service = SimpleNamespace(settings=SimpleNamespace(max_file_size_upload=100))
    upload = SimpleNamespace(size=1, filename="x.txt")

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await endpoints.create_upload_file(
                file=upload, flow=flow, current_user=owner, settings_service=settings_service
            )
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    save_spy.assert_not_called()


@pytest.mark.anyio
async def test_deprecated_upload_owner_proceeds(monkeypatch, owner):
    from pathlib import Path

    from langflow.api.v1 import endpoints

    flow = _make_flow(owner.id)
    save_spy = MagicMock(return_value=Path("flow/x.txt"))
    monkeypatch.setattr(endpoints, "save_uploaded_file", save_spy)
    settings_service = SimpleNamespace(settings=SimpleNamespace(max_file_size_upload=100))
    upload = SimpleNamespace(size=1, filename="x.txt")

    result = await endpoints.create_upload_file(
        file=upload, flow=flow, current_user=owner, settings_service=settings_service
    )

    save_spy.assert_called_once()
    assert result.flow_id == str(flow.id)


# --------------------------------------------------------------------------- #
# mcp_projects.update_project_mcp_settings — project WRITE
# --------------------------------------------------------------------------- #


def _install_mcp_session(monkeypatch, project):
    """Patch ``session_scope`` so the route's project fetch returns ``project``."""
    from contextlib import asynccontextmanager

    from langflow.api.v1 import mcp_projects

    exec_result = SimpleNamespace(first=lambda: project, all=list)
    session = SimpleNamespace(
        exec=AsyncMock(return_value=exec_result),
        flush=AsyncMock(),
        add=MagicMock(),
    )

    @asynccontextmanager
    async def _scope():
        yield session

    monkeypatch.setattr(mcp_projects, "session_scope", _scope)
    return session


@pytest.mark.anyio
async def test_mcp_update_settings_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import mcp_projects

    project = SimpleNamespace(
        id=uuid4(),
        user_id=owner.id,
        workspace_id=None,
        auth_settings=None,
        flows=[],
        name="proj",
    )
    session = _install_mcp_session(monkeypatch, project)
    request = SimpleNamespace(settings=[], auth_settings=None, model_fields_set=set())

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await mcp_projects.update_project_mcp_settings(project_id=project.id, request=request, current_user=owner)
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    session.flush.assert_not_awaited()


# --------------------------------------------------------------------------- #
# models.py variable-mutating routes (variable WRITE / DELETE)
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_update_enabled_models_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import models

    svc_spy = MagicMock()
    monkeypatch.setattr(models, "get_variable_service", svc_spy)

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await models.update_enabled_models(session=MagicMock(), current_user=owner, updates=[])
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    svc_spy.assert_not_called()


@pytest.mark.anyio
async def test_set_default_model_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import models

    svc_spy = MagicMock()
    monkeypatch.setattr(models, "get_variable_service", svc_spy)
    request = SimpleNamespace(model_type="language", model_name="m", provider="OpenAI")

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await models.set_default_model(session=MagicMock(), current_user=owner, request=request)
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    svc_spy.assert_not_called()


@pytest.mark.anyio
async def test_clear_default_model_viewer_denied(monkeypatch, owner):
    from langflow.api.v1 import models

    svc_spy = MagicMock()
    monkeypatch.setattr(models, "get_variable_service", svc_spy)

    set_current_external_access_context(_viewer_ceiling())
    try:
        with pytest.raises(HTTPException) as exc_info:
            await models.clear_default_model(session=MagicMock(), current_user=owner, model_type="language")
    finally:
        set_current_external_access_context(None)

    assert exc_info.value.status_code == 403
    svc_spy.assert_not_called()


@pytest.mark.anyio
async def test_set_default_model_owner_proceeds(monkeypatch, owner):
    """Owner with no ceiling reaches the variable service (owner-override path)."""
    from langflow.api.v1 import models

    var_service = MagicMock(spec=models.DatabaseVariableService)
    var_service.get_variable_object = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    var_service.update_variable_fields = AsyncMock()
    monkeypatch.setattr(models, "get_variable_service", lambda: var_service)
    request = SimpleNamespace(model_type="language", model_name="m", provider="OpenAI")

    result = await models.set_default_model(session=MagicMock(), current_user=owner, request=request)

    var_service.update_variable_fields.assert_awaited_once()
    assert result["default_model"]["model_name"] == "m"
