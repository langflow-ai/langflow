"""Database-backed dedupe tests, optionally also run on PostgreSQL.

Set LANGFLOW_TEST_POSTGRES_URL to a postgresql+psycopg URL for a test database
whose user can create schemas. Each PostgreSQL case owns a temporary schema.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.jobs.exceptions import DuplicateJobError
from langflow.services.jobs.service import JobService
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(params=["sqlite", "postgresql", "postgresql-repeatable-read"])
async def job_database(request, tmp_path, monkeypatch):
    admin = None
    schema = f"dedupe_{uuid4().hex}"
    if request.param == "sqlite":
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    else:
        url = os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("LANGFLOW_TEST_POSTGRES_URL is not set")
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = create_async_engine(
            url,
            connect_args={"options": f"-csearch_path={schema}"},
            isolation_level="REPEATABLE READ" if request.param.endswith("repeatable-read") else "READ COMMITTED",
        )

    class DelayedInsertSession(AsyncSession):
        async def flush(self, *args, **kwargs):
            # Inject insert latency so concurrent callers can finish a stale
            # read-before-write check unless it is protected by the database.
            await asyncio.sleep(0.05)
            return await super().flush(*args, **kwargs)

    @asynccontextmanager
    async def session_scope():
        async with DelayedInsertSession(engine, expire_on_commit=False) as session, session.begin():
            yield session

    monkeypatch.setattr("langflow.services.jobs.service.session_scope", session_scope)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Job.__table__.create)
        yield engine
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
            await admin.dispose()


@pytest.mark.parametrize("owner", [None, UUID(int=0)])
@pytest.mark.parametrize("key", ["batch", ""])
async def test_concurrent_same_owner_and_key_create_one_job(job_database, owner, key):
    results = await asyncio.wait_for(
        asyncio.gather(
            *(
                JobService().create_job(job_id=uuid4(), flow_id=uuid4(), user_id=owner, dedupe_key=key)
                for _ in range(4)
            ),
            return_exceptions=True,
        ),
        timeout=10,
    )

    assert sum(isinstance(result, Job) for result in results) == 1
    assert sum(isinstance(result, DuplicateJobError) for result in results) == 3
    async with AsyncSession(job_database) as session:
        assert len((await session.exec(select(Job))).all()) == 1


@pytest.mark.parametrize("status", list(JobStatus))
@pytest.mark.usefixtures("job_database")
async def test_dedupe_keeps_existing_retry_policy(status):
    owner = uuid4()
    service = JobService()
    first = await service.create_job(job_id=uuid4(), flow_id=uuid4(), user_id=owner, dedupe_key="retry")
    await service.update_job_status(first.job_id, status)
    retry = service.create_job(job_id=uuid4(), flow_id=uuid4(), user_id=owner, dedupe_key="retry")
    if status in {JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT}:
        assert (await retry).job_id != first.job_id
    else:
        with pytest.raises(DuplicateJobError):
            await retry


@pytest.mark.usefixtures("job_database")
async def test_different_owners_and_unkeyed_jobs_remain_independent():
    owner = uuid4()
    requests = [(owner, "key"), (uuid4(), "key"), (None, "key"), (owner, "other"), (owner, None), (owner, None)]
    jobs = await asyncio.gather(
        *(
            JobService().create_job(job_id=uuid4(), flow_id=uuid4(), user_id=user, dedupe_key=key)
            for user, key in requests
        )
    )
    assert len({job.job_id for job in jobs}) == len(requests)


@pytest.mark.parametrize("cancel", [False, True], ids=["rollback", "cancellation"])
async def test_failed_creation_releases_dedupe_lock(job_database, monkeypatch, cancel):
    reached_insert = asyncio.Event()

    class FailedInsertSession(AsyncSession):
        async def flush(self, *_args, **_kwargs):
            reached_insert.set()
            if cancel:
                await asyncio.Event().wait()
            msg = "injected insert failure"
            raise RuntimeError(msg)

    @asynccontextmanager
    async def failed_session_scope():
        async with FailedInsertSession(job_database) as session, session.begin():
            yield session

    owner = uuid4()
    with monkeypatch.context() as patch:
        patch.setattr("langflow.services.jobs.service.session_scope", failed_session_scope)
        task = asyncio.create_task(
            JobService().create_job(job_id=uuid4(), flow_id=uuid4(), user_id=owner, dedupe_key="retry")
        )
        await asyncio.wait_for(reached_insert.wait(), timeout=5)
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
            await task

    job = await asyncio.wait_for(
        JobService().create_job(job_id=uuid4(), flow_id=uuid4(), user_id=owner, dedupe_key="retry"), timeout=5
    )
    assert job.status == JobStatus.QUEUED


async def test_creation_preserves_connection_default_isolation(job_database):
    async with job_database.connect() as connection:
        original = await connection.get_isolation_level()
    await JobService().create_job(job_id=uuid4(), flow_id=uuid4(), dedupe_key="isolation")
    async with job_database.connect() as connection:
        assert await connection.get_isolation_level() == original
