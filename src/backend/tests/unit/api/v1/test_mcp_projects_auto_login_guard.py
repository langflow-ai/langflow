"""AUTO_LOGIN guard coverage for the per-project MCP credential resolver.

``verify_project_auth`` historically fell back to the configured superuser whenever a
project carried no explicit MCP auth settings and ``AUTO_LOGIN`` was on — regardless of
``skip_auth_auto_login``. Every other authenticated entrypoint (``api_key_security``,
``ws_api_key_security``, ``authenticate_with_credentials``) rejects credential-less
callers in that configuration, so the MCP transport endpoints must do the same.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from langflow.api.v1.mcp_projects import verify_project_auth
from langflow.services.auth.constants import AUTO_LOGIN_ERROR

MODULE = "langflow.api.v1.mcp_projects"


def _settings(*, auto_login: bool, skip_auth: bool, superuser: str = "admin") -> SimpleNamespace:
    return SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTO_LOGIN=auto_login,
            skip_auth_auto_login=skip_auth,
            SUPERUSER=superuser,
        )
    )


def _session_scope_yielding(project) -> object:
    """Build a ``session_scope`` replacement whose session resolves to ``project``."""

    @asynccontextmanager
    async def _scope():
        session = MagicMock()
        session.exec = AsyncMock(return_value=SimpleNamespace(first=lambda: project))
        session.get = AsyncMock(return_value=None)
        yield session

    return _scope


@pytest.mark.anyio
async def test_verify_project_auth_auto_login_alone_rejects_credential_less_caller():
    """Default config (AUTO_LOGIN on, skip_auth_auto_login off) must not resolve to the superuser."""
    project = SimpleNamespace(id=uuid4(), user_id=uuid4(), auth_settings=None)
    superuser = SimpleNamespace(id=uuid4(), username="admin")

    with (
        patch(f"{MODULE}.get_settings_service", return_value=_settings(auto_login=True, skip_auth=False)),
        patch(f"{MODULE}.session_scope", _session_scope_yielding(project)),
        patch(f"{MODULE}.get_user_by_username", new=AsyncMock(return_value=superuser)) as mock_lookup,
        pytest.raises(HTTPException) as exc,
    ):
        await verify_project_auth(project.id, query_param=None, header_param=None)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc.value.detail == AUTO_LOGIN_ERROR
    mock_lookup.assert_not_awaited()


@pytest.mark.anyio
async def test_verify_project_auth_auto_login_skip_keeps_superuser_fallback():
    """AUTO_LOGIN + skip_auth_auto_login preserves the documented single-user MCP fallback."""
    project = SimpleNamespace(id=uuid4(), user_id=uuid4(), auth_settings=None)
    superuser = SimpleNamespace(id=uuid4(), username="admin")

    with (
        patch(f"{MODULE}.get_settings_service", return_value=_settings(auto_login=True, skip_auth=True)),
        patch(f"{MODULE}.session_scope", _session_scope_yielding(project)),
        patch(f"{MODULE}.get_user_by_username", new=AsyncMock(return_value=superuser)),
    ):
        result = await verify_project_auth(project.id, query_param=None, header_param=None)

    assert result is superuser
