"""The deployment_copy job type and the release must reach one head from either side."""

from uuid import uuid4

import pytest
from alembic import command
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401


def _insert_job(connection, job_type: str) -> None:
    connection.execute(
        text(
            "INSERT INTO job (job_id, flow_id, status, type, created_timestamp) "
            "VALUES (:job_id, :flow_id, 'queued', :job_type, CURRENT_TIMESTAMP)"
        ),
        {"job_id": str(uuid4()), "flow_id": str(uuid4()), "job_type": job_type},
    )


def test_deployment_copy_and_release_have_single_head():
    """Startup upgrades to "head", which Alembic refuses while there are two."""
    script = ScriptDirectory.from_config(_make_alembic_cfg("sqlite+aiosqlite://"))
    assert script.get_heads() == ["b7e1d4a92c60"]  # pragma: allowlist secret


@pytest.mark.parametrize(
    "prior_revision",
    [
        "base",
        "c14fe0b7508c",  # pragma: allowlist secret
        "f2d6b8c4a901",  # pragma: allowlist secret
    ],
)
def test_upgrading_from_either_side_keeps_jobs_and_accepts_a_copy_job(db_url, prior_revision):  # noqa: F811
    """A database on the release or on this branch's earlier head both end up able to store the new type."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, prior_revision)
    engine = create_engine(_engine_url(db_url))
    try:
        if prior_revision != "base":
            with engine.begin() as connection:
                _insert_job(connection, "workflow")
        command.upgrade(config, "head")
        with engine.begin() as connection:
            _insert_job(connection, "deployment_copy")
        with engine.connect() as connection:
            jobs = connection.execute(text("SELECT COUNT(*) FROM job")).scalar()
            assert jobs == (1 if prior_revision == "base" else 2)
            assert MigrationContext.configure(connection).get_current_heads() == (
                "b7e1d4a92c60",  # pragma: allowlist secret
            )
    finally:
        engine.dispose()
