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
from langflow.api.v1.mcp_projects import authenticated_caller_ctx, verify_project_auth
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


def _session_scope_yielding(project, *, user=None) -> object:
    """Build a ``session_scope`` replacement whose session resolves to ``project``."""

    @asynccontextmanager
    async def _scope():
        session = MagicMock()
        session.exec = AsyncMock(return_value=SimpleNamespace(first=lambda: project))
        session.get = AsyncMock(return_value=user)
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
        patch(f"{MODULE}.session_scope", _session_scope_yielding(project)),
        patch(f"{MODULE}.authenticate_api_key", new=AsyncMock(return_value=api_key_result)),
        patch(f"{MODULE}.AuthCredentialContext.from_api_key_result", return_value=MagicMock()),
        patch(f"{MODULE}.get_user_by_username", new=AsyncMock()) as mock_lookup,
    ):
        result = await verify_project_auth(project.id, query_param=None, header_param="generated-key")

    assert result is owner
    mock_lookup.assert_not_awaited()


@pytest.mark.anyio
async def test_verify_project_auth_rejects_presented_key_from_another_owner():
    """A valid key belonging to a different user must not unlock this project."""
    project = SimpleNamespace(id=uuid4(), user_id=uuid4(), auth_settings=None)
    other_user = SimpleNamespace(id=uuid4(), username="someone-else")

    with (
        patch(f"{MODULE}.get_settings_service", return_value=_settings(auto_login=True, skip_auth=False)),
        patch(f"{MODULE}.session_scope", _session_scope_yielding(project)),
        patch(f"{MODULE}.authenticate_api_key", new=AsyncMock(return_value=SimpleNamespace(user=other_user))),
        patch(f"{MODULE}.AuthCredentialContext.from_api_key_result", return_value=MagicMock()),
        pytest.raises(HTTPException) as exc,
    ):
        await verify_project_auth(project.id, query_param=None, header_param="someone-elses-key")

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.anyio
async def test_verify_project_auth_public_project_keeps_caller_anonymous():
    """A public project executes as its owner without authenticating the anonymous caller as that owner."""
    owner = SimpleNamespace(id=uuid4(), username="owner")
    project = SimpleNamespace(id=uuid4(), user_id=owner.id, auth_settings={"auth_type": "none"})
    token = authenticated_caller_ctx.set(uuid4())
    try:
        with (
            patch(f"{MODULE}.get_settings_service", return_value=_settings(auto_login=True, skip_auth=False)),
            patch(f"{MODULE}.session_scope", _session_scope_yielding(project, user=owner)),
        ):
            result = await verify_project_auth(project.id, query_param=None, header_param=None)

        assert authenticated_caller_ctx.get() is None
    finally:
        authenticated_caller_ctx.reset(token)

    assert result is owner


@pytest.mark.anyio
@pytest.mark.parametrize("auth_type", ["apikey", "oauth"])
async def test_verify_project_auth_records_presented_api_key_caller(auth_type):
    """API-key and OAuth project entrypoints record the credential's principal."""
    owner = SimpleNamespace(id=uuid4(), username="owner")
    project = SimpleNamespace(id=uuid4(), user_id=owner.id, auth_settings={"auth_type": auth_type})
    api_key_result = SimpleNamespace(user=owner)
    token = authenticated_caller_ctx.set(None)
    try:
        with (
            patch(f"{MODULE}.get_settings_service", return_value=_settings(auto_login=True, skip_auth=False)),
            patch(f"{MODULE}.session_scope", _session_scope_yielding(project)),
            patch(f"{MODULE}.authenticate_api_key", new=AsyncMock(return_value=api_key_result)),
            patch(f"{MODULE}.AuthCredentialContext.from_api_key_result", return_value=MagicMock()),
        ):
            result = await verify_project_auth(project.id, query_param=None, header_param="generated-key")

        assert authenticated_caller_ctx.get() == owner.id
    finally:
        authenticated_caller_ctx.reset(token)

    assert result is owner


@pytest.mark.anyio
async def test_verify_project_auth_records_auto_login_caller_and_resets_stale_context():
    """AUTO_LOGIN records the fallback principal after clearing stale request context."""
    project = SimpleNamespace(id=uuid4(), user_id=uuid4(), auth_settings=None)
    superuser = SimpleNamespace(id=uuid4(), username="admin")
    token = authenticated_caller_ctx.set(uuid4())
    try:
        with (
            patch(f"{MODULE}.get_settings_service", return_value=_settings(auto_login=True, skip_auth=True)),
            patch(f"{MODULE}.session_scope", _session_scope_yielding(project)),
            patch(f"{MODULE}.get_user_by_username", new=AsyncMock(return_value=superuser)),
        ):
            result = await verify_project_auth(project.id, query_param=None, header_param=None)

        assert authenticated_caller_ctx.get() == superuser.id
    finally:
        authenticated_caller_ctx.reset(token)

    assert result is superuser
