"""Persistence, fencing, and pool isolation for the independent UPDATE path."""

import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.database import autocommit
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.jobs.service import JobService
from sqlalchemy import event, literal_column, make_url, schema, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.fixture(params=["sqlite", "postgresql", "postgresql-psycopg"])
async def write_engine(request, tmp_path, monkeypatch):
    """Give every test its own database namespace and production helper engine."""
    namespace = f"independent_{uuid4().hex}"
    if request.param.startswith("postgresql"):
        url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
        if not url:
            pytest.skip("LANGFLOW_TEST_DATABASE_URI is required for PostgreSQL")
        url = make_url(url).set(drivername="postgresql+asyncpg")
        connect_args = {"server_settings": {"search_path": namespace}}
        if request.param == "postgresql-psycopg":
            pytest.importorskip("psycopg")
            url = url.set(drivername="postgresql+psycopg")
            connect_args = {"options": f"-csearch_path={namespace}"}
        engine = create_async_engine(url, connect_args=connect_args, pool_size=1)
        async with engine.begin() as connection:
            await connection.execute(schema.CreateSchema(namespace))
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'writes.db'}")
    monkeypatch.setattr(autocommit, "get_db_service", lambda: SimpleNamespace(engine=engine))
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Job.__table__.create)
        yield engine
    finally:
        if request.param.startswith("postgresql"):
            async with engine.begin() as connection:
                await connection.execute(schema.DropSchema(namespace, cascade=True))
        await engine.dispose()


async def seed_job(engine, status=JobStatus.IN_PROGRESS):
    """Insert a job without invoking unrelated service operations."""
    job = Job(job_id=uuid4(), flow_id=uuid4(), user_id=uuid4(), status=status, job_metadata={"owner": "worker:a"})
    async with engine.begin() as connection:
        await connection.execute(Job.__table__.insert().values(**job.model_dump()))
    return job.job_id


async def payload(engine, job_id):
    """Read committed payloads through another checkout."""
    async with engine.connect() as connection:
        return (await connection.execute(select(Job.result, Job.error).where(Job.job_id == job_id))).one()


@pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.COMPLETED, JobStatus.SUSPENDED])
@pytest.mark.parametrize("owner", [None, "worker:a", "worker:b"])
@pytest.mark.parametrize("field", ["result", "error"])
async def test_live_payload_preserves_fences(write_engine, status, owner, field):
    """Status and lease ownership are checked in the payload's one statement."""
    job_id = await seed_job(write_engine, status)
    service = JobService()
    method = service.set_live_result if field == "result" else service.set_live_error
    expected = status in (JobStatus.QUEUED, JobStatus.IN_PROGRESS) and owner != "worker:b"
    assert await method(job_id, {"value": 1}, owner=owner) is expected
    result, error = await payload(write_engine, job_id)
    assert (result if field == "result" else error) == ({"value": 1} if expected else None)
    assert (error if field == "result" else result) is None


@pytest.mark.usefixtures("write_engine")
async def test_missing_job_returns_false():
    """No matching row retains the service's false result."""
    assert await JobService().set_live_result(uuid4(), {"value": 1}) is False


async def test_waiting_payload_rechecks_changed_owner(write_engine):
    """A blocked writer cannot overwrite a job after another worker claims it."""
    job_id = await seed_job(write_engine)
    attempted = asyncio.Event()

    def observe(_connection, _cursor, statement, *_args):
        """Signal the payload attempt while the lease-changing writer holds the row."""
        if "SET result=" in statement:
            attempted.set()

    event.listen(write_engine.sync_engine, "before_cursor_execute", observe)
    pending = None
    try:
        async with write_engine.begin() as connection:
            await connection.execute(update(Job).where(Job.job_id == job_id).values(job_metadata={"owner": "worker:b"}))
            pending = asyncio.create_task(JobService().set_live_result(job_id, {"stale": True}, owner="worker:a"))
            await asyncio.wait_for(attempted.wait(), timeout=5)
        assert await asyncio.wait_for(pending, timeout=5) is False
    finally:
        event.remove(write_engine.sync_engine, "before_cursor_execute", observe)
        if pending is not None and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
    assert (await payload(write_engine, job_id))[0] is None


async def test_concurrent_payload_fields_remain_independent(write_engine):
    """Concurrent result/error writes update only their own column."""
    job_id = await seed_job(write_engine)
    service = JobService()
    assert await asyncio.gather(
        service.set_live_result(job_id, {"value": 1}, owner="worker:a"),
        service.set_live_error(job_id, {"error": 2}, owner="worker:a"),
    ) == [True, True]
    assert tuple(await payload(write_engine, job_id)) == ({"value": 1}, {"error": 2})


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("when", ["before_cursor_execute", "after_cursor_execute"])
async def test_failure_persistence_and_retry(write_engine, when, failure):
    """Failures after execution cannot undo PostgreSQL autocommit; retry is idempotent."""
    job_id = await seed_job(write_engine)

    def fail(*_args):
        """Inject an application failure at a deterministic driver boundary."""
        message = "injected"
        raise failure(message)

    event.listen(write_engine.sync_engine, when, fail)
    try:
        with pytest.raises(failure):
            await JobService().set_live_result(job_id, {"value": 1})
    finally:
        event.remove(write_engine.sync_engine, when, fail)
    durable = when == "after_cursor_execute" and write_engine.dialect.name == "postgresql"
    assert (await payload(write_engine, job_id))[0] == ({"value": 1} if durable else None)
    assert await JobService().set_live_result(job_id, {"value": 1})
    assert (await payload(write_engine, job_id))[0] == {"value": 1}


async def test_database_failure_and_pool_reset(write_engine):
    """A failed statement does not poison a pooled connection or later rollback."""
    job_id = await seed_job(write_engine)
    with pytest.raises(DBAPIError):
        await autocommit.execute_independent_update(
            update(Job).where(Job.job_id == job_id).values(result=literal_column("missing_column"))
        )
    assert await JobService().set_live_result(job_id, {"value": 1})
    with pytest.raises(RuntimeError, match="rollback"):  # noqa: PT012
        async with write_engine.begin() as connection:
            assert await connection.get_isolation_level() != "AUTOCOMMIT"
            await connection.execute(update(Job).where(Job.job_id == job_id).values(result={"value": 2}))
            message = "rollback"
            raise RuntimeError(message)
    assert (await payload(write_engine, job_id))[0] == {"value": 1}


@pytest.mark.parametrize("configuration", ["execution_option", "engine_option"])
async def test_nondefault_isolation_stays_transactional(write_engine, monkeypatch, configuration):
    """Configured isolation is preserved instead of silently switching semantics."""
    if write_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL isolation override")
    engine = write_engine.execution_options(isolation_level="SERIALIZABLE")
    if configuration == "engine_option":
        async with write_engine.connect() as connection:
            namespace = (await connection.execute(text("SELECT current_schema()"))).scalar_one()
        connect_args = {"server_settings": {"search_path": namespace}}
        if write_engine.dialect.driver == "psycopg":
            connect_args = {"options": f"-csearch_path={namespace}"}
        engine = create_async_engine(write_engine.url, isolation_level="SERIALIZABLE", connect_args=connect_args)
    monkeypatch.setattr(autocommit, "get_db_service", lambda: SimpleNamespace(engine=engine))
    job_id = await seed_job(engine)

    def fail(*_args):
        """Fail after the statement, before its surrounding transaction commits."""
        message = "after execute"
        raise RuntimeError(message)

    event.listen(engine.sync_engine, "after_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="after execute"):
            await JobService().set_live_result(job_id, {"value": 1})
    finally:
        event.remove(engine.sync_engine, "after_cursor_execute", fail)
        if configuration == "engine_option":
            await engine.dispose()
    assert (await payload(engine, job_id))[0] is None


@pytest.mark.usefixtures("write_engine")
async def test_compound_text_is_rejected_before_checkout():
    """The helper accepts structured UPDATEs rather than arbitrary SQL strings."""
    with pytest.raises(TypeError, match="UPDATE"):
        await autocommit.execute_independent_update(text("UPDATE job SET result = NULL; DELETE FROM job"))
