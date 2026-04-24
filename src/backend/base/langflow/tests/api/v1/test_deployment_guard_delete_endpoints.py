from __future__ import annotations

from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from langflow.api.utils import cascade_delete_flow
from langflow.api.v1.projects import delete_project
from langflow.services.database.models.deployment.exceptions import DeploymentGuardError


class _ExecResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value

    def all(self):
        return self._value


class _AsyncNullContext:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_delete_project_raises_guard_error_from_app_level_check(monkeypatch):
    project_id = uuid4()
    user_id = uuid4()

    monkeypatch.setattr(
        "langflow.api.v1.projects.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(add_projects_to_mcp_servers=False)),
    )
    monkeypatch.setattr("langflow.api.v1.projects.cleanup_mcp_on_delete", AsyncMock())
    monkeypatch.setattr("langflow.api.v1.mappers.deployments.sync.sync_project_deployments", AsyncMock())

    session = AsyncMock()
    project = SimpleNamespace(id=project_id, name="Test Project", auth_settings=None)
    session.exec = AsyncMock(
        side_effect=[
            _ExecResult(project),  # initial project lookup
            _ExecResult([]),  # first attempt: flows query
            _ExecResult(uuid4()),  # first attempt: check_project_has_deployments
            _ExecResult([]),  # second attempt: flows query
            _ExecResult(uuid4()),  # second attempt: check_project_has_deployments
        ]
    )
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.begin_nested = lambda: _AsyncNullContext()

    with pytest.raises(
        DeploymentGuardError,
        match=(
            r"project cannot be deleted because it has deployments\. "
            r"Please delete its deployments first\."
        ),
    ):
        await delete_project(
            session=session,
            project_id=project_id,
            current_user=SimpleNamespace(id=user_id),
        )

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_project_remaps_flow_guard_to_project_guard(monkeypatch):
    project_id = uuid4()
    user_id = uuid4()
    flow_id = uuid4()

    monkeypatch.setattr(
        "langflow.api.v1.projects.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(add_projects_to_mcp_servers=False)),
    )
    monkeypatch.setattr("langflow.api.v1.projects.cleanup_mcp_on_delete", AsyncMock())
    monkeypatch.setattr("langflow.api.v1.mappers.deployments.sync.sync_project_deployments", AsyncMock())
    monkeypatch.setattr(
        "langflow.api.v1.projects.cascade_delete_flow",
        AsyncMock(
            side_effect=DeploymentGuardError(
                code="FLOW_HAS_DEPLOYED_VERSIONS",
                technical_detail=(
                    "DELETE flow_version blocked: dependent rows exist in flow_version_deployment_attachment "
                    "for the target flow."
                ),
                detail=(
                    "This flow cannot be deleted because it has deployed versions. "
                    "Please remove its versions from deployments first."
                ),
            )
        ),
    )

    session = AsyncMock()
    project = SimpleNamespace(id=project_id, name="Test Project", auth_settings=None)
    session.exec = AsyncMock(
        side_effect=[
            _ExecResult(project),  # initial project lookup
            _ExecResult([SimpleNamespace(id=flow_id)]),  # first attempt: flows query
            _ExecResult([SimpleNamespace(id=flow_id)]),  # second attempt: flows query
        ]
    )
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.begin_nested = lambda: _AsyncNullContext()

    with pytest.raises(
        DeploymentGuardError,
        match=(
            r"project cannot be deleted because it has deployments\. "
            r"Please delete its deployments first\."
        ),
    ) as exc_info:
        await delete_project(
            session=session,
            project_id=project_id,
            current_user=SimpleNamespace(id=user_id),
        )

    assert exc_info.value.code == "PROJECT_HAS_DEPLOYMENTS"
    assert "DELETE folder blocked while deleting project flows" in exc_info.value.technical_detail
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_cascade_delete_flow_raises_guard_error_from_app_level_check():
    """cascade_delete_flow should run app-level guard checks before issuing deletes."""
    flow_id = uuid4()

    session = AsyncMock()
    session.exec = AsyncMock(return_value=_ExecResult(uuid4()))

    with pytest.raises(
        DeploymentGuardError,
        match=(
            r"flow cannot be deleted because it has deployed versions\. "
            r"Please remove its versions from deployments first\."
        ),
    ):
        await cascade_delete_flow(session, flow_id)
    assert session.exec.await_count == 1


@pytest.mark.asyncio
async def test_cascade_delete_flow_prunes_orphan_attachments_before_delete_statements():
    """cascade_delete_flow should remove stale attachment rows before deleting flow rows."""
    flow_id = uuid4()

    session = AsyncMock()
    session.exec = AsyncMock(
        side_effect=[
            _ExecResult(None),  # live deployment attachment lookup
            _ExecResult([uuid4()]),  # stale attachment lookup
            _ExecResult(None),  # stale attachment delete
            _ExecResult(None),  # message delete
            _ExecResult(None),  # transaction delete
            _ExecResult(None),  # vertex_build delete
            _ExecResult(None),  # flow_version delete
            _ExecResult([]),  # trace id lookup
            _ExecResult(None),  # flow delete
        ]
    )

    await cascade_delete_flow(session, flow_id)

    assert session.exec.await_count == 9


@pytest.mark.asyncio
async def test_delete_flow_remaps_guard_error_to_flow_delete_message(monkeypatch):
    from langflow.api.v1.flows import delete_flow

    flow_id = uuid4()
    user_id = uuid4()

    fake_flow = SimpleNamespace(id=flow_id, user_id=user_id)
    monkeypatch.setattr("langflow.api.v1.flows._read_flow", AsyncMock(return_value=fake_flow))
    monkeypatch.setattr(
        "langflow.api.v1.flows.retry_flow_operation_on_deployment_guard",
        AsyncMock(
            side_effect=DeploymentGuardError(
                code="FLOW_HAS_DEPLOYED_VERSIONS",
                technical_detail=(
                    "DELETE flow_version blocked: dependent rows exist in flow_version_deployment_attachment "
                    "for the target flow."
                ),
                detail=(
                    "This flow cannot be deleted because it has deployed versions. "
                    "Please remove its versions from deployments first."
                ),
            )
        ),
    )

    with pytest.raises(
        DeploymentGuardError,
        match=(
            r"cannot be deleted because it has deployed versions\. "
            r"Please remove its versions from deployments first\."
        ),
    ) as exc_info:
        await delete_flow(
            session=AsyncMock(),
            flow_id=flow_id,
            current_user=SimpleNamespace(id=user_id),
        )

    assert exc_info.value.code == "FLOW_HAS_DEPLOYED_VERSIONS"
    assert "DELETE flow_version blocked" in exc_info.value.technical_detail


@pytest.mark.asyncio
async def test_update_flow_translates_guard_error_from_flush(monkeypatch):
    """update_flow must propagate DeploymentGuardError from guarded operations."""
    from langflow.api.v1.flows import update_flow
    from langflow.services.database.models.flow.model import FlowUpdate

    flow_id = uuid4()
    user_id = uuid4()
    folder_id = uuid4()
    new_folder_id = uuid4()

    fake_flow = SimpleNamespace(
        id=flow_id,
        user_id=user_id,
        folder_id=folder_id,
        data={"nodes": [], "edges": []},
        fs_path=None,
        webhook=False,
        updated_at=None,
    )

    monkeypatch.setattr("langflow.api.v1.flows._read_flow", AsyncMock(return_value=fake_flow))
    monkeypatch.setattr(
        "langflow.api.v1.flows._patch_flow",
        AsyncMock(
            side_effect=DeploymentGuardError(
                code="FLOW_DEPLOYED_IN_PROJECT",
                technical_detail=(
                    "Cannot move flow to a different project because it has versions deployed in the current project."
                ),
                detail=(
                    "This flow cannot be moved to another project until its versions "
                    "are removed from deployments in its current project."
                ),
            )
        ),
    )
    monkeypatch.setattr("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", AsyncMock())
    monkeypatch.setattr(
        "langflow.api.v1.flows.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(remove_api_keys=False)),
    )

    session = AsyncMock()
    session.exec = AsyncMock(return_value=_ExecResult(SimpleNamespace(id=new_folder_id)))
    session.add = AsyncMock()
    session.begin_nested = lambda: _AsyncNullContext()

    flow_update = FlowUpdate(folder_id=new_folder_id)

    with pytest.raises(
        DeploymentGuardError,
        match=(
            r"cannot be moved to another project until its versions are "
            r"removed from deployments in its current project"
        ),
    ):
        await update_flow(
            session=session,
            flow_id=flow_id,
            flow=flow_update,
            current_user=SimpleNamespace(id=user_id),
            storage_service=AsyncMock(),
        )


@pytest.mark.asyncio
async def test_delete_multiple_flows_propagates_guard_error(monkeypatch):
    """delete_multiple_flows must let DeploymentGuardError propagate to the caller."""
    from langflow.api.v1.flows import delete_multiple_flows

    flow_id = uuid4()
    user_id = uuid4()

    fake_flow = SimpleNamespace(id=flow_id)

    monkeypatch.setattr(
        "langflow.api.v1.flows.cascade_delete_flow",
        AsyncMock(
            side_effect=DeploymentGuardError(
                code="FLOW_HAS_DEPLOYED_VERSIONS",
                technical_detail=(
                    "DELETE flow_version blocked: dependent rows exist in flow_version_deployment_attachment "
                    "for the target flow."
                ),
                detail=(
                    "This flow cannot be deleted because it has deployed versions. "
                    "Please remove its versions from deployments first."
                ),
            )
        ),
    )
    monkeypatch.setattr("langflow.api.v1.mappers.deployments.sync.sync_flow_deployment_state", AsyncMock())

    session = AsyncMock()
    session.exec = AsyncMock(return_value=_ExecResult([fake_flow]))
    session.begin_nested = lambda: _AsyncNullContext()

    with pytest.raises(
        DeploymentGuardError,
        match=(
            r"cannot be deleted because it has deployed versions\. "
            r"Please remove its versions from deployments first\."
        ),
    ):
        await delete_multiple_flows(
            flow_ids=[flow_id],
            user=SimpleNamespace(id=user_id),
            db=session,
        )


# ── Global exception handler ────────────────────────────────────────


@pytest.mark.asyncio
async def test_global_exception_handler_returns_409_for_deployment_guard_error():
    """The global exception handler must convert DeploymentGuardError to a 409 Conflict response."""

    async def _handler(_request, exc: Exception):
        if isinstance(exc, DeploymentGuardError):
            return JSONResponse(
                status_code=HTTPStatus.CONFLICT,
                content={"detail": exc.detail},
            )
        return JSONResponse(status_code=500, content={"message": str(exc)})

    app = FastAPI()
    app.add_exception_handler(DeploymentGuardError, _handler)

    _detail = "Cannot delete project because it contains deployments."

    @app.get("/boom")
    async def _boom():
        raise DeploymentGuardError(
            code="PROJECT_HAS_DEPLOYMENTS",
            technical_detail="DELETE folder blocked: dependent rows exist in deployment for the target project.",
            detail=_detail,
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 409
    body = response.json()
    assert body == {"detail": _detail}
