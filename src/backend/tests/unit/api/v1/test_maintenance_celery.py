"""Exercise broker delivery and the real Celery task admission boundary."""

import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.maintenance.state import set_maintenance
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlalchemy.exc import OperationalError
from sqlmodel import select

from tests.unit.api.v1 import test_maintenance as maintenance_fixtures

logged_in_headers_super_user = maintenance_fixtures.logged_in_headers_super_user
without_instance_migration = maintenance_fixtures.without_instance_migration
pytestmark = [pytest.mark.no_blockbuster, pytest.mark.usefixtures("client")]


@pytest.fixture
def worker_app():
    pytest.importorskip("celery")
    from langflow.core.celery_app import make_celery

    app = make_celery(
        "maintenance-worker-test",
        SimpleNamespace(
            broker_url="memory://",
            result_backend="cache+memory://",
            task_default_queue=f"maintenance-{uuid4().hex}",
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
        ),
    )
    yield app
    app.close()


async def _set_flag(*, enabled):
    async with session_scope() as session:
        await set_maintenance(session, enabled=enabled)


def _writing_task(app, job_id):
    from asgiref.sync import async_to_sync

    @app.task(bind=True, name=f"maintenance-write-{job_id}")
    def write_job(self):
        async def persist():
            async with session_scope() as session:
                session.add(Job(job_id=job_id, flow_id=uuid4(), status=JobStatus.COMPLETED))

        async_to_sync(persist)()
        return self.request.id

    return write_job


@pytest.mark.parametrize("admin_repair", [False, True])
@pytest.mark.usefixtures("logged_in_headers_super_user")
async def test_brokered_work_is_requeued_or_uses_the_verified_repair_envelope(worker_app, monkeypatch, *, admin_repair):
    from celery.contrib.testing.worker import start_worker
    from celery.signals import task_postrun
    from langflow.api.utils.migration_pause import write_admission
    from langflow.services.task.backends.celery import CeleryBackend

    monkeypatch.setattr("langflow.worker.celery_app", worker_app)
    async with session_scope() as session:
        admin = (await session.exec(select(User).where(User.username == "maintenance-admin"))).one()
    job_id = uuid4()
    task = _writing_task(worker_app, job_id)
    caller_id = admin.id if admin_repair else None
    async with write_admission(caller_id=caller_id) as refusal:
        assert refusal is None
        task_id, result = CeleryBackend().launch_task(task)
    await _set_flag(enabled=True)
    rejected = threading.Event()

    def on_rejected(task_id=None, state=None, **_kwargs):
        if task_id == result.id and state == "REJECTED":
            rejected.set()

    task_postrun.connect(on_rejected, weak=False)
    try:
        with start_worker(worker_app, pool="solo", concurrency=1, perform_ping_check=False, shutdown_timeout=15):
            if not admin_repair:
                assert await asyncio.to_thread(rejected.wait, 15)
                async with session_scope() as session:
                    assert await session.get(Job, job_id) is None
                assert result.state == "PENDING"
                await _set_flag(enabled=False)
            assert await asyncio.to_thread(result.get, timeout=20, disable_sync_subtasks=False) == task_id
            async with session_scope() as session:
                assert (await session.get(Job, job_id)).status == JobStatus.COMPLETED
                assert len((await session.exec(select(Job).where(Job.job_id == job_id))).all()) == 1
    finally:
        task_postrun.disconnect(on_rejected)


@pytest.mark.parametrize("source", ["unavailable", "file", "tampered", "demoted"])
@pytest.mark.usefixtures("logged_in_headers_super_user")
async def test_worker_refuses_without_running_body_or_trusting_a_stale_envelope(
    worker_app, monkeypatch, tmp_path, source
):
    from celery.exceptions import Reject
    from langflow.api.utils import migration_pause
    from langflow.services.task.maintenance import MAINTENANCE_HEADER, maintenance_task_headers

    async with session_scope() as session:
        admin = (await session.exec(select(User).where(User.username == "maintenance-admin"))).one()
    job_id, task_id = uuid4(), str(uuid4())
    task = _writing_task(worker_app, job_id)
    async with migration_pause.write_admission(caller_id=admin.id):
        headers = maintenance_task_headers(task_id, task.name)
    await _set_flag(enabled=True)
    if source == "unavailable":
        monkeypatch.setattr(
            migration_pause, "maintenance_enabled", AsyncMock(side_effect=OperationalError("read", {}, None))
        )
    elif source == "file":
        monkeypatch.setattr(FEATURE_FLAGS, "instance_migration", True)
        monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
        folder = tmp_path / "migrations"
        folder.mkdir()
        (folder / "migration.json").write_text(json.dumps({"pause": {"frozen_at": "2026-11-04T20:00:00+00:00"}}))
    elif source == "tampered":
        headers[MAINTENANCE_HEADER]["caller"] = str(uuid4())
    else:
        async with session_scope() as session:
            (await session.get(User, admin.id)).is_superuser = False

    def deliver():
        task.push_request(id=task_id, headers=headers)
        try:
            with pytest.raises(Reject) as rejected:
                task()
            assert rejected.value.requeue is True
        finally:
            task.pop_request()

    await asyncio.to_thread(deliver)
    async with session_scope() as session:
        assert await session.get(Job, job_id) is None
