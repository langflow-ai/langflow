"""Maintenance admission at queue, cleanup, and protocol boundaries."""

import asyncio
import inspect
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_job_service, get_queue_service, get_settings_service, session_scope
from langflow.services.maintenance.state import set_maintenance
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlmodel import select

from tests.unit.api.v1 import test_maintenance as maintenance_fixtures

logged_in_headers_super_user = maintenance_fixtures.logged_in_headers_super_user
without_instance_migration = maintenance_fixtures.without_instance_migration
pytestmark = pytest.mark.usefixtures("client")


async def _toggle(*, enabled: bool) -> None:
    async with session_scope() as session:
        await set_maintenance(session, enabled=enabled)


async def _eventually(check) -> None:
    async def poll():
        while not await check():  # noqa: ASYNC110 - database changes have no local event
            await asyncio.sleep(0.02)

    await asyncio.wait_for(poll(), timeout=5)


async def test_editor_queue_defers_direct_production_until_unfreeze():
    queue = get_queue_service()
    task_id = str(uuid4())
    started = asyncio.Event()

    async def build():
        started.set()

    await _toggle(enabled=True)
    queue.create_queue(task_id)
    try:
        queue.start_job(task_id, build())
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(started.wait(), timeout=0.1)
        await _toggle(enabled=False)
        await asyncio.wait_for(started.wait(), timeout=5)
    finally:
        await queue.cleanup_job(task_id)


async def test_canceling_a_held_editor_job_closes_the_unstarted_coroutine():
    queue = get_queue_service()
    task_id = str(uuid4())

    async def build():
        pytest.fail("A held task must not start")

    await _toggle(enabled=True)
    queue.create_queue(task_id)
    pending = build()
    queue.start_job(task_id, pending)
    await asyncio.sleep(0)
    with pytest.raises(asyncio.CancelledError, match="LANGFLOW_USER_CANCELLED"):
        await queue.cleanup_job(task_id)
    await asyncio.sleep(0)
    assert inspect.getcoroutinestate(pending) == inspect.CORO_CLOSED


@pytest.mark.parametrize("method", ["fire_and_forget_task", "launch_task", "launch_and_await_task"])
async def test_task_service_refuses_before_calling_a_producer(method):
    from langflow.exceptions.api import WorkflowServiceUnavailableError
    from langflow.services.task.service import TaskService

    service = TaskService(get_settings_service())
    work = AsyncMock()
    await _toggle(enabled=True)
    with pytest.raises(WorkflowServiceUnavailableError, match="maintenance mode"):
        await getattr(service, method)(work)
    work.assert_not_called()


async def test_task_service_runs_the_local_backend_after_unfreeze():
    from langflow.services.task.service import TaskService

    service = TaskService(get_settings_service())
    work = AsyncMock(return_value="finished")
    _task_id, result = await service.launch_task(work)
    assert result.ready() is True
    assert result.result == "finished"
    work.assert_awaited_once()


async def test_retention_preserves_rows_during_the_freeze_and_resumes(monkeypatch):
    from langflow.services.background_execution import service as background

    settings = get_settings_service()
    monkeypatch.setattr(settings.settings, "background_retention_days", 1)
    monkeypatch.setattr(background, "_RETENTION_INITIAL_DELAY_S", 0.02)
    monkeypatch.setattr(background, "_RETENTION_INTERVAL_S", 0.02)
    job_id = uuid4()
    old = datetime.now(timezone.utc) - timedelta(days=10)
    async with session_scope() as session:
        session.add(Job(job_id=job_id, flow_id=uuid4(), status=JobStatus.COMPLETED, finished_timestamp=old))
    await _toggle(enabled=True)
    service = background.BackgroundExecutionService(settings)
    service._start_retention_sweep()
    try:
        await asyncio.sleep(0.1)
        assert await get_job_service().get_job_by_job_id(job_id) is not None
        await _toggle(enabled=False)

        async def purged():
            return await get_job_service().get_job_by_job_id(job_id) is None

        await _eventually(purged)
    finally:
        await service.stop()


async def test_deadline_watchdog_leaves_suspended_jobs_unchanged_until_unfreeze(monkeypatch):
    from langflow.services.background_execution.service import BackgroundExecutionService

    settings = get_settings_service()
    monkeypatch.setattr(settings.settings, "background_input_deadline_s", 1)
    monkeypatch.setattr(settings.settings, "background_watchdog_interval_s", 0.02)
    job_id = uuid4()
    async with session_scope() as session:
        session.add(
            Job(
                job_id=job_id,
                flow_id=uuid4(),
                status=JobStatus.SUSPENDED,
                job_metadata={"input_deadline_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
            )
        )
    await _toggle(enabled=True)
    service = BackgroundExecutionService(settings)
    service._start_deadline_watchdog()
    try:
        await asyncio.sleep(0.1)
        assert (await get_job_service().get_job_by_job_id(job_id)).status == JobStatus.SUSPENDED
        await _toggle(enabled=False)

        async def failed():
            return (await get_job_service().get_job_by_job_id(job_id)).status == JobStatus.FAILED

        await _eventually(failed)
    finally:
        await service.stop()


@pytest.mark.parametrize(
    ("caller", "expected"),
    [("admin", None), ("ordinary", "maintenance mode"), (None, "maintenance mode")],
)
@pytest.mark.usefixtures("logged_in_headers_super_user")
async def test_mcp_admission_uses_the_transport_caller_not_the_resource_owner(
    active_user, monkeypatch, caller, expected
):
    from langflow.api.v1 import mcp_utils

    async with session_scope() as session:
        admin = (await session.exec(select(User).where(User.username == "maintenance-admin"))).one()
    caller_id = admin.id if caller == "admin" else active_user.id if caller == "ordinary" else None
    await _toggle(enabled=True)
    execute = AsyncMock(return_value=[])
    monkeypatch.setattr(mcp_utils, "with_db_session", execute)
    monkeypatch.setattr(mcp_utils.get_mcp_config(), "enable_progress_notifications", False)
    owner_token = mcp_utils.current_user_ctx.set(admin)
    caller_token = mcp_utils.authenticated_caller_ctx.set(caller_id)
    try:
        if expected:
            with pytest.raises(RuntimeError, match=expected):
                await mcp_utils.handle_call_tool("tool", {}, SimpleNamespace(), project_id=uuid4())
            execute.assert_not_awaited()
        else:
            assert await mcp_utils.handle_call_tool("tool", {}, SimpleNamespace(), project_id=uuid4()) == []
            execute.assert_awaited_once()
    finally:
        mcp_utils.authenticated_caller_ctx.reset(caller_token)
        mcp_utils.current_user_ctx.reset(owner_token)


@pytest.mark.usefixtures("logged_in_headers_super_user")
async def test_mcp_superuser_never_bypasses_the_file_pause(monkeypatch, tmp_path):
    from langflow.api.v1 import mcp_utils

    async with session_scope() as session:
        admin = (await session.exec(select(User).where(User.username == "maintenance-admin"))).one()
    await _toggle(enabled=True)
    monkeypatch.setattr(FEATURE_FLAGS, "instance_migration", True)
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    folder = tmp_path / "migrations"
    folder.mkdir()
    (folder / "migration.json").write_text(json.dumps({"pause": {"frozen_at": "2026-11-04T20:00:00+00:00"}}))
    monkeypatch.setattr(mcp_utils.get_mcp_config(), "enable_progress_notifications", False)
    owner_token = mcp_utils.current_user_ctx.set(admin)
    caller_token = mcp_utils.authenticated_caller_ctx.set(admin.id)
    try:
        with pytest.raises(RuntimeError, match="being migrated"):
            await mcp_utils.handle_call_tool("tool", {}, SimpleNamespace())
    finally:
        mcp_utils.authenticated_caller_ctx.reset(caller_token)
        mcp_utils.current_user_ctx.reset(owner_token)


async def test_verified_superuser_request_carries_repair_access_into_its_editor_task(logged_in_headers_super_user):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from langflow.api.utils.migration_pause import MigrationPauseMiddleware, admitted_maintenance_caller

    app = FastAPI()
    app.add_middleware(MigrationPauseMiddleware)
    queue = get_queue_service()
    job_id = str(uuid4())
    started = asyncio.Event()

    async def repair():
        started.set()

    @app.post("/repair-task")
    async def submit_repair():
        queue.create_queue(job_id)
        queue.start_job(job_id, repair())
        await asyncio.wait_for(started.wait(), timeout=5)
        return {"started": True}

    await _toggle(enabled=True)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://repair") as browser:
            response = await browser.post("/repair-task", headers=logged_in_headers_super_user)
        assert response.status_code == 200
        assert response.json() == {"started": True}
        assert admitted_maintenance_caller() is None
    finally:
        await queue.cleanup_job(job_id)


async def test_startup_job_recovery_waits_without_blocking_app_startup(monkeypatch, tmp_path):
    from langflow.services.background_execution import service as background

    file_lock = background.FileLock
    monkeypatch.setattr(background, "FileLock", lambda _path, **kwargs: file_lock(tmp_path / "recovery.lock", **kwargs))
    job_id = uuid4()
    async with session_scope() as session:
        session.add(Job(job_id=job_id, flow_id=uuid4(), status=JobStatus.IN_PROGRESS))
    await _toggle(enabled=True)
    service = background.BackgroundExecutionService(get_settings_service())
    try:
        await asyncio.wait_for(service.sweep_orphans_on_startup(), timeout=5)
        await asyncio.sleep(0.1)
        assert (await get_job_service().get_job_by_job_id(job_id)).status == JobStatus.IN_PROGRESS
        await _toggle(enabled=False)

        async def recovered():
            return (await get_job_service().get_job_by_job_id(job_id)).status == JobStatus.FAILED

        await _eventually(recovered)
    finally:
        await service.stop()


async def test_automatic_storage_upgrade_waits_for_unfreeze(monkeypatch):
    from contextlib import asynccontextmanager

    from langflow.services.knowledge_base_storage import coordinator

    entered = asyncio.Event()

    @asynccontextmanager
    async def backup_pass():
        entered.set()
        yield

    work = AsyncMock()
    monkeypatch.setattr(coordinator.application_backup, "upgrade_pass", backup_pass)
    monkeypatch.setattr(coordinator.application_backup, "discard_if_finished", AsyncMock())
    monkeypatch.setattr(coordinator, "_resume_pending", work)
    await _toggle(enabled=True)
    task = coordinator.schedule_upgrade()
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(entered.wait(), timeout=0.1)
        work.assert_not_awaited()
        await _toggle(enabled=False)
        await asyncio.wait_for(task, timeout=5)
        work.assert_awaited_once()
    finally:
        await coordinator.stop_upgrade()
