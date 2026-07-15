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


def test_job_events_table_and_unique_seq(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert "job_events" in inspector.get_table_names()
            columns = {c["name"] for c in inspector.get_columns("job_events")}
            assert {"id", "job_id", "seq", "event_type", "payload", "created_at"} <= columns
            indexes = inspector.get_indexes("job_events")
            assert any(idx["column_names"] == ["job_id"] for idx in indexes)
            unique = inspector.get_unique_constraints("job_events")
            assert any(set(u["column_names"]) == {"job_id", "seq"} for u in unique)
    finally:
        engine.dispose()


def test_execution_signals_table(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert "execution_signals" in inspector.get_table_names()
            columns = {c["name"] for c in inspector.get_columns("execution_signals")}
            assert {"id", "job_id", "signal_type", "data", "created_at", "consumed_at"} <= columns
            indexes = inspector.get_indexes("execution_signals")
            assert any(idx["column_names"] == ["job_id"] for idx in indexes)
    finally:
        engine.dispose()


def test_signal_type_enum_has_stop():
    from langflow.services.database.models.jobs.model import SignalType

    assert SignalType.STOP.value == "stop"
