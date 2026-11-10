"""Authentication stays read-only while the explicit security audit exception commits."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from langflow.services.database.models.auth import AuthzAuditLog, SSOUserProfile
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_auth_service, get_settings_service, session_scope
from sqlmodel import select

from tests.unit.api.v1 import test_maintenance as maintenance_fixtures

logged_in_headers_super_user = maintenance_fixtures.logged_in_headers_super_user
without_instance_migration = maintenance_fixtures.without_instance_migration


async def _snapshot(models):
    async with session_scope() as session:
        return {
            model.__name__: [row.model_dump() for row in (await session.exec(select(model))).all()] for model in models
        }


@pytest.mark.parametrize("credential", ["valid", "invalid", "disabled"])
async def test_local_login_preserves_rows_and_still_checks_credentials(
    client, active_user, logged_in_headers_super_user, credential
):
    if credential == "disabled":
        async with session_scope() as session:
            (await session.get(User, active_user.id)).is_active = False
    assert (
        await client.post(maintenance_fixtures.ON, json={}, headers=logged_in_headers_super_user)
    ).status_code == 200
    before = await _snapshot((User, Folder, Variable))
    response = await client.post(
        "/api/v1/login",
        data={
            "username": active_user.username,
            "password": "invalid" if credential == "invalid" else "testpassword",  # pragma: allowlist secret
        },
    )
    assert response.status_code == (200 if credential == "valid" else 401 if credential == "invalid" else 400)
    assert await _snapshot((User, Folder, Variable)) == before


@pytest.mark.parametrize("existing", [False, True])
<<<<<<< HEAD
@pytest.mark.parametrize("endpoint", [maintenance_fixtures.STATUS, "/api/v1/session"])
async def test_external_bearer_returns_retryable_503_without_jit_or_directory_writes(
    client, active_user, logged_in_headers_super_user, monkeypatch, endpoint, *, existing
=======
async def test_external_bearer_returns_retryable_503_without_jit_or_directory_writes(
    client, active_user, logged_in_headers_super_user, monkeypatch, *, existing
>>>>>>> origin/release-1.14.0
):
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "EXTERNAL_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "EXTERNAL_AUTH_TRUSTED_JWT_DECODE", True)
    monkeypatch.setattr(settings, "EXTERNAL_AUTH_PROVIDER", "maintenance-provider")
    if existing:
        async with session_scope() as session:
            session.add(
                SSOUserProfile(user_id=active_user.id, sso_provider="maintenance-provider", sso_user_id="subject")
            )
    token = jwt.encode(
        {
            "sub": "subject",
            "email": "new@example.com",
            "preferred_username": "external-new-name",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )
    reconcile = AsyncMock()
    monkeypatch.setattr(get_auth_service(), "_reconcile_verified_external_groups", reconcile)
    assert (
        await client.post(maintenance_fixtures.ON, json={}, headers=logged_in_headers_super_user)
    ).status_code == 200
    before = await _snapshot((User, SSOUserProfile, Folder, Variable))
<<<<<<< HEAD
    response = await client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
=======
    response = await client.get(maintenance_fixtures.STATUS, headers={"Authorization": f"Bearer {token}"})
>>>>>>> origin/release-1.14.0
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert response.json()["detail"]["code"] == "external_auth_maintenance"
    assert "External SSO/OIDC" in response.json()["detail"]["message"]
    assert await _snapshot((User, SSOUserProfile, Folder, Variable)) == before
    reconcile.assert_not_awaited()


@pytest.mark.parametrize("durable", [False, True])
async def test_audit_exception_commits_real_rows_without_acknowledging_before_commit(
    client, active_user, logged_in_headers_super_user, monkeypatch, *, durable
):
    from langflow.services.authorization import audit

    assert (
        await client.post(maintenance_fixtures.ON, json={}, headers=logged_in_headers_super_user)
    ).status_code == 200
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_ENABLED", False)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_DURABLE", durable)
    started, release = asyncio.Event(), asyncio.Event()
    original = audit._flush_audit_batch

    async def held_flush(batch):
        started.set()
        await release.wait()
        await original(batch)

    monkeypatch.setattr(audit, "_flush_audit_batch", held_flush)
    call = asyncio.create_task(
        audit.audit_decision(user_id=active_user.id, action="maintenance:read-audit", obj="flow:*", result="allow")
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        assert call.done() is (not durable)
        async with session_scope() as session:
            assert (
                await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.action == "maintenance:read-audit"))
            ).all() == []
        release.set()
        await asyncio.wait_for(call, timeout=5)
        await audit.drain_pending_audit_writes(timeout=5)
        async with session_scope() as session:
            rows = (
                await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.action == "maintenance:read-audit"))
            ).all()
        assert len(rows) == 1
        assert audit.get_audit_producer_health()["persisted_count"] >= 1
    finally:
        release.set()
        await audit.drain_pending_audit_writes(timeout=5)
