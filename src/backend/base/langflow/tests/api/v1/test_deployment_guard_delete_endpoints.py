from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
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
