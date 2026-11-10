"""Telemetry identity survives queued execution and durable job replay."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import JobRunner
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import ExecutionSignal, Job, JobCheckpoint, JobEvent, JobStatus
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_settings_service
from langflow.services.jobs.service import JobService
from langflow.services.telemetry.context import (
    get_current_telemetry_user_id,
    reset_current_telemetry_user,
    set_current_telemetry_user,
)
from lfx.services.telemetry.identity import get_hashed_user_id, get_installation_user_id
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
async def job_service(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")

    @asynccontextmanager
    async def session_scope():
        async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
            yield session

    monkeypatch.setattr("langflow.services.jobs.service.session_scope", session_scope)
    tables = [model.__table__ for model in (Job, JobEvent, JobCheckpoint, ExecutionSignal)]
    async with engine.begin() as connection:
        await connection.run_sync(lambda connection: SQLModel.metadata.create_all(connection, tables=tables))
    token = set_current_telemetry_user(None)
    try:
        yield JobService()
    finally:
        reset_current_telemetry_user(token)
        await engine.dispose()


async def test_background_submission_carries_only_hashed_identity(job_service, monkeypatch):
    captured = []

    async def source(**_kwargs):
        captured.append(get_current_telemetry_user_id())
        yield b'{"event":"end","data":{}}', "end"

    service = BackgroundExecutionService(get_settings_service(), frame_source_factory=lambda **_kwargs: source)
    monkeypatch.setattr("langflow.services.background_execution.service.get_job_service", lambda: job_service)
    monkeypatch.setattr(service, "start", service._executor.start)
    await service._executor.start()
    user = UserRead.model_construct(id=uuid4(), username="alice")
    token = set_current_telemetry_user(user.id, "test-installation")
    try:
        job_id = await service.submit(flow_id=uuid4(), request={"stream_protocol": "langflow"}, user=user)
        await asyncio.wait_for(service._executor._queue.join(), timeout=5)
    finally:
        reset_current_telemetry_user(token)
        await service._executor.stop()

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    assert captured == [get_installation_user_id(user.id, "test-installation")]
    assert job.job_metadata["telemetry_user_id"] == get_installation_user_id(user.id, "test-installation")
    assert "alice" not in str(job.job_metadata)


@pytest.mark.parametrize(
    ("user_id", "expected_id"),
    [
        (None, None),
        (get_hashed_user_id("alice"), None),
        (
            get_installation_user_id(UUID(int=1), "test-installation"),
            get_installation_user_id(UUID(int=1), "test-installation"),
        ),
    ],
    ids=["missing", "legacy", "identified"],
)
@pytest.mark.parametrize("fail", [False, True], ids=["success", "failure"])
async def test_replayed_job_restores_identity_and_resets_worker_context(job_service, user_id, expected_id, fail):
    job_id = uuid4()
    metadata = {"telemetry_user_id": user_id} if user_id else None
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), initial_metadata=metadata)
    captured = []

    async def source(**_kwargs):
        captured.append(get_current_telemetry_user_id())
        if fail:
            msg = "workflow failed"
            raise RuntimeError(msg)
        yield b'{"event":"end","data":{}}', "end"

    runner = JobRunner(
        job_service=job_service,
        live_bus=InMemoryLiveBus(),
        adapter=get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="test")),
        frame_source=source,
    )
    token = set_current_telemetry_user(UUID(int=2), "test-installation")
    try:
        await runner.run(job_id=job_id, source_kwargs={})
        assert get_current_telemetry_user_id() == get_installation_user_id(UUID(int=2), "test-installation")
    finally:
        reset_current_telemetry_user(token)

    assert captured == [expected_id]
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == (JobStatus.FAILED if fail else JobStatus.COMPLETED)
