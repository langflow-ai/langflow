from __future__ import annotations

from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from langflow.api.utils.core import cascade_delete_flow
from langflow.api.v1.projects import delete_project
from langflow.api.v1.users import delete_user
from langflow.services.database.models.deployment.exceptions import DeploymentGuardError


class _ExecResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value

    def all(self):
        return self._value


@pytest.mark.asyncio
async def test_delete_project_translates_guard_error_from_flush(monkeypatch):
    project_id = uuid4()
    user_id = uuid4()

    monkeypatch.setattr(
        "langflow.api.v1.projects.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(add_projects_to_mcp_servers=False)),
    )

    session = AsyncMock()
    project = SimpleNamespace(id=project_id, name="Test Project", auth_settings=None)
    session.exec = AsyncMock(
        side_effect=[
            _ExecResult([]),  # sync_project_deployments query
            _ExecResult([]),  # flows query
            _ExecResult(project),  # project query
        ]
    )
    session.delete = AsyncMock()
    session.flush = AsyncMock(
        side_effect=Exception(
            "DEPLOYMENT_GUARD:PROJECT_HAS_DEPLOYMENTS:Cannot delete project because it contains deployments."
        )
    )

    with pytest.raises(DeploymentGuardError, match="Cannot delete project"):
        await delete_project(
            session=session,
            project_id=project_id,
            current_user=SimpleNamespace(id=user_id),
        )

    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_user_translates_guard_error_from_flush():
    current_user_id = uuid4()
    target_user_id = uuid4()

    session = AsyncMock()
    session.exec = AsyncMock(return_value=_ExecResult(SimpleNamespace(id=target_user_id)))
    session.delete = AsyncMock()
    session.flush = AsyncMock(
        side_effect=Exception(
            "DEPLOYMENT_GUARD:PROJECT_HAS_DEPLOYMENTS:Cannot delete project because it contains deployments."
        )
    )

    with pytest.raises(DeploymentGuardError, match="Cannot delete project"):
        await delete_user(
            user_id=target_user_id,
            current_user=SimpleNamespace(id=current_user_id, is_superuser=True),
            session=session,
        )

    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_cascade_delete_flow_translates_guard_error():
    """cascade_delete_flow must translate a raw DB guard exception into DeploymentGuardError."""
    from langflow.services.database.models.flow_version.model import FlowVersion

    flow_id = uuid4()

    _guard_msg = (
        "DEPLOYMENT_GUARD:FLOW_VERSION_DEPLOYED:"
        "Cannot delete flow version because it is attached to one or more deployments. "
        "Detach it from all deployments first."
    )

    async def _exec_side_effect(stmt):
        stmt_str = str(stmt)
        if FlowVersion.__tablename__ in stmt_str and "DELETE" in stmt_str.upper():
            raise RuntimeError(_guard_msg)
        return _ExecResult(None)

    session = AsyncMock()
    session.exec = AsyncMock(side_effect=_exec_side_effect)

    with pytest.raises(DeploymentGuardError, match="Cannot delete flow version"):
        await cascade_delete_flow(session, flow_id)


@pytest.mark.asyncio
async def test_update_flow_translates_guard_error_from_flush(monkeypatch):
    """update_flow must translate a raw DB guard exception into DeploymentGuardError."""
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
    monkeypatch.setattr("langflow.api.v1.flows._try_flow_deployment_sync", AsyncMock())
    monkeypatch.setattr("langflow.api.v1.flows.get_webhook_component_in_flow", lambda _data: None)
    monkeypatch.setattr(
        "langflow.api.v1.flows.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(remove_api_keys=False)),
    )

    session = AsyncMock()
    session.exec = AsyncMock(return_value=_ExecResult(SimpleNamespace(id=new_folder_id)))
    session.add = AsyncMock()
    session.flush = AsyncMock(
        side_effect=Exception(
            "DEPLOYMENT_GUARD:FLOW_DEPLOYED_IN_PROJECT:"
            "Cannot move flow to a different project because it has versions deployed "
            "in the current project. Detach deployed versions first."
        )
    )

    flow_update = FlowUpdate(folder_id=new_folder_id)

    with pytest.raises(DeploymentGuardError, match="Cannot move flow"):
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

    monkeypatch.setattr("langflow.api.v1.flows._try_flow_deployment_sync", AsyncMock())
    monkeypatch.setattr(
        "langflow.api.v1.flows.cascade_delete_flow",
        AsyncMock(
            side_effect=DeploymentGuardError(
                "Cannot delete flow version because it is attached to one or more deployments. "
                "Detach it from all deployments first."
            )
        ),
    )

    session = AsyncMock()
    session.exec = AsyncMock(return_value=_ExecResult([fake_flow]))

    with pytest.raises(DeploymentGuardError, match="Cannot delete flow version"):
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
        raise DeploymentGuardError(_detail)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 409
    body = response.json()
    assert body == {"detail": _detail}
