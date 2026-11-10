"""Database maintenance applies across app instances without the migration feature."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from langflow.main import create_app
from langflow.services.background_execution.executor import InProcessExecutor
from langflow.services.database.models.api_key.crud import create_api_key
from langflow.services.database.models.api_key.model import ApiKey, ApiKeyCreate
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlmodel import select

STATUS = "/api/v1/maintenance/status"
ON = "/api/v1/maintenance/on"
OFF = "/api/v1/maintenance/off"


@pytest.fixture(autouse=True)
def without_instance_migration(monkeypatch):
    monkeypatch.setattr(FEATURE_FLAGS, "instance_migration", False)


@pytest.fixture
async def logged_in_headers_super_user(client):
    # The shared normal-user and superuser fixtures use the same username.
    async with session_scope() as session:
        session.add(
            User(
                username="maintenance-admin",
                password=get_auth_service().get_password_hash("testpassword"),
                is_active=True,
                is_superuser=True,
            )
        )
    response = await client.post(
        "/api/v1/login",
        data={
            "username": "maintenance-admin",
            "password": "testpassword",  # pragma: allowlist secret
        },
    )
    assert response.status_code == 200
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_only_superusers_control_maintenance(client, logged_in_headers, logged_in_headers_super_user):
    assert (await client.get(STATUS)).status_code in {401, 403}
    assert (await client.post(ON, json={}, headers=logged_in_headers)).status_code == 403
    assert (await client.post(ON, json={}, headers=logged_in_headers_super_user)).status_code == 200
    assert (await client.post(OFF, headers=logged_in_headers)).status_code == 503
    assert (await client.post(OFF, headers=logged_in_headers_super_user)).status_code == 200


async def test_second_app_blocks_writes_and_unfreezes_immediately(
    client, logged_in_headers, logged_in_headers_super_user, monkeypatch, tmp_path
):
    # A different config directory cannot share the file pause.
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    other = create_app()
    async with AsyncClient(transport=ASGITransport(app=other), base_url="http://second") as second:
        enabled = await client.post(ON, json={"reason": "upgrade rehearsal"}, headers=logged_in_headers_super_user)
        assert enabled.status_code == 200
        assert enabled.json()["maintenance"] is True
        refused = await second.post("/api/v1/flows/", json={"name": "ordinary"}, headers=logged_in_headers)
        assert refused.status_code == 503
        assert refused.json()["detail"] == "This instance is in maintenance mode."
        admin_write = await second.post("/api/v1/flows/", json={"name": "repair"}, headers=logged_in_headers_super_user)
        assert admin_write.status_code == 201
        assert (await second.get("/api/v1/flows/", headers=logged_in_headers)).status_code == 200
        assert (await client.post(OFF, headers=logged_in_headers_super_user)).status_code == 200
        assert (
            await second.post("/api/v1/flows/", json={"name": "resumed"}, headers=logged_in_headers)
        ).status_code == 201


async def test_status_reports_shared_jobs_and_does_not_cancel_them(client, logged_in_headers_super_user):
    queued, running = uuid4(), uuid4()
    async with session_scope() as session:
        session.add(Job(job_id=queued, flow_id=uuid4(), status=JobStatus.QUEUED))
        session.add(Job(job_id=running, flow_id=uuid4(), status=JobStatus.IN_PROGRESS))
        session.add(Job(job_id=uuid4(), flow_id=uuid4(), status=JobStatus.COMPLETED))
    response = await client.post(ON, json={}, headers=logged_in_headers_super_user)
    assert response.status_code == 200
    assert response.json()["queued_jobs"] == 1
    assert response.json()["running_jobs"] == 1
    async with session_scope() as session:
        assert (await session.get(Job, queued)).status == JobStatus.QUEUED
        assert (await session.get(Job, running)).status == JobStatus.IN_PROGRESS


async def test_pending_worker_starts_only_after_database_freeze_ends(client, logged_in_headers_super_user):
    await client.post(ON, json={}, headers=logged_in_headers_super_user)
    began = asyncio.Event()

    async def run():
        began.set()

    worker = InProcessExecutor(max_concurrency=1)
    await worker.start()
    try:
        await worker.submit("held-by-maintenance", run)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(began.wait(), timeout=0.1)
        await client.post(OFF, headers=logged_in_headers_super_user)
        await asyncio.wait_for(began.wait(), timeout=2)
    finally:
        await worker.stop()


async def test_invalid_credentials_never_gain_the_superuser_exception(client, logged_in_headers_super_user):
    await client.post(ON, json={}, headers=logged_in_headers_super_user)
    for headers in ({}, {"Authorization": "Bearer invalid"}, {"x-api-key": "invalid"}):
        assert (await client.post("/api/v1/flows/", json={"name": "refused"}, headers=headers)).status_code == 503


async def test_an_unavailable_flag_never_authorizes_a_superuser_write(
    client, logged_in_headers_super_user, monkeypatch
):
    from unittest.mock import AsyncMock

    from langflow.api.utils import migration_pause
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr(
        migration_pause, "maintenance_enabled", AsyncMock(side_effect=OperationalError("read", {}, None))
    )
    response = await client.post("/api/v1/flows/", json={"name": "refused"}, headers=logged_in_headers_super_user)
    assert response.status_code == 503


async def test_reason_is_bounded_before_storage(client, logged_in_headers_super_user):
    response = await client.post(ON, json={"reason": "x" * 1025}, headers=logged_in_headers_super_user)
    assert response.status_code == 422
    state = await client.get(STATUS, headers=logged_in_headers_super_user)
    assert state.json()["maintenance"] is False


async def test_api_keys_use_the_verified_owners_superuser_status(client, active_user, logged_in_headers_super_user):
    async with session_scope() as session:
        admin = (await session.exec(select(User).where(User.username == "maintenance-admin"))).one()
        admin_key = await create_api_key(session, ApiKeyCreate(name="repair"), admin.id)
        ordinary_key = await create_api_key(session, ApiKeyCreate(name="ordinary"), active_user.id)
    await client.post(ON, json={}, headers=logged_in_headers_super_user)
    refused = await client.post(
        "/api/v1/flows/", json={"name": "ordinary"}, headers={"x-api-key": ordinary_key.api_key}
    )
    repaired = await client.post("/api/v1/flows/", json={"name": "repair"}, headers={"x-api-key": admin_key.api_key})
    assert refused.status_code == 503
    assert repaired.status_code == 201


@pytest.mark.parametrize("legacy", [False, True])
async def test_api_key_reads_and_refused_writes_preserve_the_entire_key_row(
    client, active_user, logged_in_headers_super_user, *, legacy
):
    async with session_scope() as session:
        key = await create_api_key(session, ApiKeyCreate(name="frozen bookkeeping"), active_user.id)
        row = await session.get(ApiKey, key.id)
        if legacy:
            row.api_key_hash = None
        row.total_uses = 7
        row.last_used_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    async with session_scope() as session:
        before = (await session.get(ApiKey, key.id)).model_dump()
    await client.post(ON, json={}, headers=logged_in_headers_super_user)
    headers = {"x-api-key": key.api_key}
    assert (await client.post("/api/v1/flows/", json={"name": "blocked"}, headers=headers)).status_code == 503
    assert (await client.get("/api/v1/flows/", headers=headers)).status_code == 200
    async with session_scope() as session:
        assert (await session.get(ApiKey, key.id)).model_dump() == before
    await client.post(OFF, headers=logged_in_headers_super_user)
    assert (await client.get("/api/v1/flows/", headers=headers)).status_code == 200
    async with session_scope() as session:
        after = await session.get(ApiKey, key.id)
        assert after.total_uses == 8
        assert after.api_key_hash is not None


@pytest.mark.parametrize("denial", ["revoked", "expired", "inactive", "external", "invalid"])
async def test_maintenance_readonly_key_auth_keeps_credential_denials(
    client, active_user, logged_in_headers_super_user, monkeypatch, denial
):
    from langflow.services.database.models.auth import SSOUserProfile
    from langflow.services.deps import get_settings_service

    async with session_scope() as session:
        key = await create_api_key(session, ApiKeyCreate(name="denied"), active_user.id)
        row = await session.get(ApiKey, key.id)
        if denial == "revoked":
            row.is_active = False
        elif denial == "expired":
            row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        elif denial == "inactive":
            (await session.get(User, active_user.id)).is_active = False
        elif denial == "external":
            auth = get_settings_service().auth_settings
            monkeypatch.setattr(auth, "EXTERNAL_AUTH_ACCESS_CEILING_ENABLED", True)
            monkeypatch.setattr(auth, "EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS", True)
            session.add(
                SSOUserProfile(user_id=active_user.id, sso_provider=auth.EXTERNAL_AUTH_PROVIDER, sso_user_id="subject")
            )
    await client.post(ON, json={}, headers=logged_in_headers_super_user)
    token = "sk-invalid" if denial == "invalid" else key.api_key
    assert (await client.get("/api/v1/flows/", headers={"x-api-key": token})).status_code in {401, 403}
    async with session_scope() as session:
        row = await session.get(ApiKey, key.id)
        assert row.total_uses == 0
        assert row.last_used_at is None


async def test_file_migration_pause_still_refuses_superuser_repairs(
    client, logged_in_headers_super_user, monkeypatch, tmp_path
):
    from langflow.services.deps import get_settings_service

    await client.post(ON, json={}, headers=logged_in_headers_super_user)
    monkeypatch.setattr(FEATURE_FLAGS, "instance_migration", True)
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    migration = tmp_path / "migrations"
    migration.mkdir()
    (migration / "migration.json").write_text(json.dumps({"pause": {"frozen_at": "2026-11-04T20:00:00+00:00"}}))
    response = await client.post("/api/v1/flows/", json={"name": "refused"}, headers=logged_in_headers_super_user)
    assert response.status_code == 503
    assert response.json()["detail"] == "This instance is being migrated."
    status = await client.get(STATUS, headers=logged_in_headers_super_user)
    assert status.json()["maintenance"] is True
    assert status.json()["migration"] is True


async def test_stale_author_save_is_refused_before_route_logic(client, logged_in_headers, logged_in_headers_super_user):
    saved = await client.post("/api/v1/flows/", json={"name": "before"}, headers=logged_in_headers)
    assert saved.status_code == 201
    await client.post(ON, json={}, headers=logged_in_headers_super_user)
    response = await client.patch(
        f"/api/v1/flows/{saved.json()['id']}", json={"name": "stale edit"}, headers=logged_in_headers
    )
    assert response.status_code == 503
    current = await client.get(f"/api/v1/flows/{saved.json()['id']}", headers=logged_in_headers)
    assert current.json()["name"] == "before"
<<<<<<< HEAD


async def test_status_keeps_actor_and_instance_job_counts_private(
    client, logged_in_headers, logged_in_headers_super_user
):
    async with session_scope() as session:
        session.add(Job(job_id=uuid4(), flow_id=uuid4(), status=JobStatus.QUEUED))
        session.add(Job(job_id=uuid4(), flow_id=uuid4(), status=JobStatus.IN_PROGRESS))
    enabled = await client.post(ON, json={"reason": "review rehearsal"}, headers=logged_in_headers_super_user)
    assert enabled.status_code == 200
    admin = await client.get(STATUS, headers=logged_in_headers_super_user)
    ordinary = await client.get(STATUS, headers=logged_in_headers)
    assert ordinary.status_code == 200
    assert admin.json()["set_by"] is not None
    assert (admin.json()["queued_jobs"], admin.json()["running_jobs"]) == (1, 1)
    public = ordinary.json()
    assert public["set_by"] is None
    assert (public["queued_jobs"], public["running_jobs"]) == (0, 0)
    assert (public["maintenance"], public["paused"], public["reason"]) == (True, True, "review rehearsal")


async def test_notice_status_does_not_query_other_users_jobs():
    from unittest.mock import AsyncMock

    from langflow.services.database.models.maintenance import MaintenanceState
    from langflow.services.maintenance.state import maintenance_status

    session = AsyncMock()
    session.get.return_value = MaintenanceState(
        id=1, enabled=True, reason="review rehearsal", set_by=uuid4(), set_at=datetime.now(timezone.utc)
    )
    status = await maintenance_status(session, include_details=False)
    session.exec.assert_not_awaited()
    assert status.maintenance is True
    assert status.set_by is None
    assert status.queued_jobs == status.running_jobs == 0
=======
>>>>>>> origin/release-1.14.0
