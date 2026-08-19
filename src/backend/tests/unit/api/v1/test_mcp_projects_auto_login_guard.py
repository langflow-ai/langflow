"""AUTO_LOGIN guard coverage for the per-project MCP credential resolver.

``verify_project_auth`` historically fell back to the configured superuser whenever a
project carried no explicit MCP auth settings and ``AUTO_LOGIN`` was on — regardless of
``skip_auth_auto_login``. Every other authenticated entrypoint (``api_key_security``,
``ws_api_key_security``, ``authenticate_with_credentials``) rejects credential-less
callers in that configuration, so the MCP transport endpoints must do the same.
"""

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


def _db_yielding(project) -> MagicMock:
    """Build the ``db`` session 1.11.x passes into ``verify_project_auth`` directly."""
    db = MagicMock()
    db.exec = AsyncMock(return_value=SimpleNamespace(first=lambda: project))
    db.get = AsyncMock(return_value=None)
    return db


@pytest.mark.anyio
async def test_verify_project_auth_auto_login_alone_rejects_credential_less_caller():
    """Default config (AUTO_LOGIN on, skip_auth_auto_login off) must not resolve to the superuser."""
    project = SimpleNamespace(id=uuid4(), user_id=uuid4(), auth_settings=None)
    superuser = SimpleNamespace(id=uuid4(), username="admin")

    with (
        patch(f"{MODULE}.get_settings_service", return_value=_settings(auto_login=True, skip_auth=False)),
        patch(f"{MODULE}.get_user_by_username", new=AsyncMock(return_value=superuser)) as mock_lookup,
        pytest.raises(HTTPException) as exc,
    ):
        await verify_project_auth(_db_yielding(project), project.id, query_param=None, header_param=None)

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
        patch(f"{MODULE}.get_user_by_username", new=AsyncMock(return_value=superuser)),
    ):
        result = await verify_project_auth(_db_yielding(project), project.id, query_param=None, header_param=None)

    assert result is superuser


@pytest.mark.anyio
async def test_verify_project_auth_honours_presented_api_key_under_auto_login():
    """A presented API key must authenticate even when policy would not have demanded one.

    Under MCP Composer with a default project (no ``auth_settings``) and ``AUTO_LOGIN`` on,
    ``requires_api_key`` is False. Before the presented-key branch existed, a key minted by
    ``POST /{id}/install`` was ignored and the caller fell through to the now-rejecting
    superuser fallback, so the generated client config could never authenticate.
    """
    owner_id = uuid4()
    project = SimpleNamespace(id=uuid4(), user_id=owner_id, auth_settings=None)
    owner = SimpleNamespace(id=owner_id, username="owner")
    api_key_result = SimpleNamespace(user=owner)

    with (
        patch(f"{MODULE}.get_settings_service", return_value=_settings(auto_login=True, skip_auth=False)),
        patch(f"{MODULE}.authenticate_api_key", new=AsyncMock(return_value=api_key_result)),
        patch(f"{MODULE}.AuthCredentialContext.from_api_key_result", return_value=MagicMock()),
        patch(f"{MODULE}.get_user_by_username", new=AsyncMock()) as mock_lookup,
    ):
        result = await verify_project_auth(
            _db_yielding(project), project.id, query_param=None, header_param="generated-key"
        )

    assert result is owner
    mock_lookup.assert_not_awaited()


@pytest.mark.anyio
async def test_verify_project_auth_rejects_presented_key_from_another_owner():
    """A valid key belonging to a different user must not unlock this project."""
    project = SimpleNamespace(id=uuid4(), user_id=uuid4(), auth_settings=None)
    other_user = SimpleNamespace(id=uuid4(), username="someone-else")
    # 1.11.x proves ownership with a second, owner-scoped Folder query rather than an
    # in-memory comparison, so that lookup must return nothing for another user's key.
    db = MagicMock()
    db.exec = AsyncMock(
        side_effect=[
            SimpleNamespace(first=lambda: project),  # initial project fetch
            SimpleNamespace(first=lambda: None),  # owner-scoped re-fetch misses
        ]
    )
    db.get = AsyncMock(return_value=None)

    with (
        patch(f"{MODULE}.get_settings_service", return_value=_settings(auto_login=True, skip_auth=False)),
        patch(f"{MODULE}.authenticate_api_key", new=AsyncMock(return_value=SimpleNamespace(user=other_user))),
        patch(f"{MODULE}.AuthCredentialContext.from_api_key_result", return_value=MagicMock()),
        pytest.raises(HTTPException) as exc,
    ):
        await verify_project_auth(db, project.id, query_param=None, header_param="someone-elses-key")

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
