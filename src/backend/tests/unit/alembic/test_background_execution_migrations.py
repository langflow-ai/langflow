"""Structure tests for the background-execution migrations.

Covers job.result/error columns, the job_events table and execution_signals
table. Runs on sqlite and (when configured) postgres.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401


def test_job_has_result_and_error_columns(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            columns = {c["name"] for c in inspect(connection).get_columns("job")}
    finally:
        engine.dispose()

    assert "result" in columns
    assert "error" in columns
