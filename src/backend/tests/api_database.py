"""Disposable databases for API tests; never clear the database supplied by the caller."""

import os
import tempfile
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


@asynccontextmanager
async def api_test_database(backend: str):
    if backend == "sqlite":
        with tempfile.TemporaryDirectory(prefix="langflow-api-test-") as directory:
            yield f"sqlite+aiosqlite:///{directory}/test.db"
        return
    if backend != "postgres":
        msg = f"Unknown API test database: {backend}"
        raise ValueError(msg)
    raw = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not raw:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")
    base = make_url(raw)
    if base.get_backend_name() not in {"postgres", "postgresql"}:
        pytest.fail("LANGFLOW_TEST_DATABASE_URI must select PostgreSQL")
    base = base.set(drivername="postgresql+psycopg")
    engine = create_async_engine(base, isolation_level="AUTOCOMMIT")
    name = f"lf_api_test_{uuid4().hex}"
    created = False
    try:
        async with engine.connect() as connection:
            # The identifier is generated here, not derived from user input.
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        yield base.set(database=name).render_as_string(hide_password=False)
    finally:
        try:
            if created:
                async with engine.connect() as connection:
                    await connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        finally:
            await engine.dispose()
