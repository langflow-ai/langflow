"""Published metrics and release migration branches must reach one head safely."""

from uuid import uuid4

import pytest
from alembic import command
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401


@pytest.mark.parametrize(
    "prior_revision",
    ["b3f7c2a91d48", "d8f2c3a4b5e6", "c7e9b2d4f6a8", "4e7a2b9c1d05"],  # pragma: allowlist secret
)
def test_job_metrics_and_personal_projects_upgrade_to_single_head(db_url, prior_revision):  # noqa: F811
    """Upgrade each prior head without losing jobs or skipping a schema change."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, prior_revision)
    engine = create_engine(_engine_url(db_url))
    job_id = str(uuid4())
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO job (job_id, flow_id, status, type, created_timestamp) "
                    "VALUES (:job_id, :flow_id, 'queued', 'workflow', CURRENT_TIMESTAMP)"
                ),
                {"job_id": job_id, "flow_id": str(uuid4())},
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            inspector = inspect(connection)
            indexes = {index["name"] for index in inspector.get_indexes("job")}
            assert {"ix_job_status_created", "ix_job_finished_timestamp"} <= indexes
            assert "is_personal" in {column["name"] for column in inspector.get_columns("folder")}
            assert "version_token" in {column["name"] for column in inspector.get_columns("flow")}
            assert (
                connection.execute(text("SELECT COUNT(*) FROM job WHERE job_id = :job_id"), {"job_id": job_id}).scalar()
                == 1
            )
            assert MigrationContext.configure(connection).get_current_heads() == (
                ScriptDirectory.from_config(config).get_current_head(),
            )
    finally:
        engine.dispose()
