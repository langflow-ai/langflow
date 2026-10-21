"""Retention rollup migration preserves jobs and creates durable bigint counters."""

from uuid import uuid4

from alembic import command
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import BigInteger, Integer, create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_REVISION = "b8e1f3a5c709"  # pragma: allowlist secret
_PARENT = "d6f8a0c2e4b9"  # pragma: allowlist secret
_TABLE = "background_job_metric_totals"
_COUNTERS = (
    "started",
    "completed",
    "failed_error",
    "failed_worker_lost",
    "failed_input_timeout",
    "timed_out",
    "cancelled",
)


def test_bg_metric_totals_upgrade_preserves_jobs_and_defaults(db_url):  # noqa: F811
    """Existing job history survives and every unprovided counter defaults to zero."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PARENT)
    engine = create_engine(_engine_url(db_url))
    job_id = str(uuid4())
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO job (job_id, flow_id, status, type, created_timestamp) "
                    "VALUES (:job_id, :flow_id, 'completed', 'workflow', CURRENT_TIMESTAMP)"
                ),
                {"job_id": job_id, "flow_id": str(uuid4())},
            )
        command.upgrade(config, _REVISION)
        with engine.begin() as connection:
            inspector = inspect(connection)
            columns = {column["name"]: column for column in inspector.get_columns(_TABLE)}
            assert set(columns) == {"id", *_COUNTERS}
            assert isinstance(columns["id"]["type"], Integer)
            assert inspector.get_pk_constraint(_TABLE)["constrained_columns"] == ["id"]
            for name in _COUNTERS:
                assert isinstance(columns[name]["type"], BigInteger)
                assert columns[name]["nullable"] is False
                assert columns[name]["default"] is not None
            assert connection.execute(text("SELECT COUNT(*) FROM background_job_metric_totals")).scalar_one() == 0
            connection.execute(text("INSERT INTO background_job_metric_totals (id) VALUES (1)"))
            totals = connection.execute(text("SELECT * FROM background_job_metric_totals")).mappings().one()
            assert {name: totals[name] for name in _COUNTERS} == dict.fromkeys(_COUNTERS, 0)
            assert (
                connection.execute(
                    text("SELECT status FROM job WHERE job_id = :job_id"), {"job_id": job_id}
                ).scalar_one()
                == "completed"
            )
    finally:
        engine.dispose()


def test_bg_metric_totals_upgrade_is_idempotent(db_url):  # noqa: F811
    """Repeating upgrade against an existing rollup never clears archived counts."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _REVISION)
    module = ScriptDirectory.from_config(config).get_revision(_REVISION).module
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO background_job_metric_totals (id, started) VALUES (1, 5000000000)"))
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
            assert (
                connection.execute(text("SELECT started FROM background_job_metric_totals")).scalar_one() == 5000000000
            )
    finally:
        engine.dispose()


def test_bg_metric_totals_downgrade_and_upgrade(db_url):  # noqa: F811
    """Downgrade drops only the rollup, and re-upgrade starts with no archived totals."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _REVISION)
    engine = create_engine(_engine_url(db_url))
    job_id = str(uuid4())
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO job (job_id, flow_id, status, type, created_timestamp) "
                    "VALUES (:job_id, :flow_id, 'completed', 'workflow', CURRENT_TIMESTAMP)"
                ),
                {"job_id": job_id, "flow_id": str(uuid4())},
            )
            connection.execute(text("INSERT INTO background_job_metric_totals (id, started) VALUES (1, 42)"))
        command.downgrade(config, _PARENT)
        with engine.connect() as connection:
            assert not inspect(connection).has_table(_TABLE)
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM job WHERE job_id = :job_id"), {"job_id": job_id}
                ).scalar_one()
                == 1
            )
        command.upgrade(config, _REVISION)
        with engine.connect() as connection:
            assert inspect(connection).has_table(_TABLE)
            assert connection.execute(text("SELECT COUNT(*) FROM background_job_metric_totals")).scalar_one() == 0
    finally:
        engine.dispose()
