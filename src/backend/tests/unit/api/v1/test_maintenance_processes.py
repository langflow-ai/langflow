"""Independent API processes see the shared switch on SQLite and PostgreSQL."""

import asyncio
import importlib
import json
import os
import sys
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from langflow.services.database.models.jobs.model import Job
from langflow.services.maintenance.state import maintenance_status, set_maintenance
from sqlalchemy import schema
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.no_blockbuster

PROBE = r"""
import asyncio
import sys
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langflow.api.utils.migration_pause import MigrationPauseMiddleware
from langflow.services.deps import get_db_service
from lfx.services.settings.feature_flags import FEATURE_FLAGS

FEATURE_FLAGS.instance_migration = False
database = get_db_service()
app = FastAPI()
app.add_middleware(MigrationPauseMiddleware)

@app.post("/write")
async def write():
    return {"accepted": True}

async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://independent") as client:
        print("PROBE ready", flush=True)
        while await asyncio.to_thread(sys.stdin.readline):
            response = await client.post("/write")
            print(f"PROBE {response.status_code}", flush=True)
    await database.engine.dispose()

asyncio.run(main())
"""


@pytest.fixture(params=["sqlite", "postgres"])
async def shared_database(request, tmp_path):
    parent_engine = None
    namespace = None
    if request.param == "sqlite":
        url = f"sqlite+aiosqlite:///{tmp_path / 'shared.db'}"
    else:
        raw = os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
        if not raw:
            pytest.skip("LANGFLOW_TEST_POSTGRES_URL is not set")
        pytest.importorskip("psycopg")
        parent_url = make_url(raw).set(drivername="postgresql+psycopg")
        parent_engine = create_async_engine(parent_url)
        namespace = f"maintenance_{uuid4().hex}"
        async with parent_engine.begin() as connection:
            await connection.execute(schema.CreateSchema(namespace))
        url = parent_url.update_query_dict({"options": f"-csearch_path={namespace}"}).render_as_string(
            hide_password=False
        )
    engine = create_async_engine(url)

    def initialize(connection):
        migration = importlib.import_module("langflow.alembic.versions.4d6e8f0a2b3c_add_database_maintenance")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        Job.__table__.create(connection)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(initialize)
        yield url, engine
    finally:
        await engine.dispose()
        if parent_engine is not None:
            try:
                async with parent_engine.begin() as connection:
                    await connection.execute(schema.DropSchema(namespace, cascade=True))
            finally:
                await parent_engine.dispose()


async def _message(process):
    while True:
        line = await asyncio.wait_for(process.stdout.readline(), timeout=30)
        assert line, "The independent maintenance probe exited unexpectedly"
        if line.startswith(b"PROBE "):
            return line.decode().strip().removeprefix("PROBE ")


async def test_two_independent_processes_observe_pause_and_unfreeze_without_restart(shared_database, tmp_path):
    url, engine = shared_database
    processes = []
    try:
        for index in range(2):
            config = tmp_path / f"independent-config-{index}"
            config.mkdir()
            environment = {
                **os.environ,
                "LANGFLOW_DATABASE_URL": url,
                "LANGFLOW_AUTO_LOGIN": "false",
                "LANGFLOW_CONFIG_DIR": str(config),
                "LANGFLOW_LOG_LEVEL": "error",
                "PYTHONDONTWRITEBYTECODE": "1",
                "DO_NOT_TRACK": "true",
            }
            if options := make_url(url).query.get("options"):
                # The service's explicit driver settings take precedence over
                # URL options, including its default timezone setting.
                environment["LANGFLOW_DB_DRIVER_CONNECTION_SETTINGS"] = json.dumps(
                    {"options": f"{options} -c timezone=utc", "prepare_threshold": None}
                )
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                PROBE,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
            )
            processes.append(process)
            assert await _message(process) == "ready"

        for enabled, expected in ((False, "200"), (True, "503"), (False, "200")):
            async with async_sessionmaker(engine, class_=AsyncSession)() as session:
                await set_maintenance(session, enabled=enabled)
                await session.commit()
                assert (await maintenance_status(session)).maintenance is enabled
            for process in processes:
                process.stdin.write(b"request\n")
                await process.stdin.drain()
                assert await _message(process) == expected
    finally:
        for process in processes:
            if process.returncode is None:
                process.stdin.close()
                try:
                    _out, error = await asyncio.wait_for(process.communicate(), timeout=15)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.communicate()
                    raise
                assert process.returncode == 0, error.decode()
