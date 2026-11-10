"""Release and feature migrations must reach one head without losing jobs or maintenance state."""

from uuid import uuid4

import pytest
from alembic import command
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

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
    heads = script.get_heads()
    assert len(heads) == 1
    assert "b7e1d4a92c60" in {  # pragma: allowlist secret
        revision.revision for revision in script.iterate_revisions(heads, "base")
    }


@pytest.mark.parametrize(
    "prior_revision",
    [
        "base",
        "c14fe0b7508c",  # pragma: allowlist secret
        "f2d6b8c4a901",  # pragma: allowlist secret
        "c4e6f8a0b2d9",  # pragma: allowlist secret
        "b7e1d4a92c60",  # pragma: allowlist secret
        "4d6e8f0a2b3c",  # pragma: allowlist secret
        "f4b8c1d2e3a6",  # pragma: allowlist secret
        "a8c2e6f4b9d1",  # pragma: allowlist secret
        "d7e9a1c3f5b8",  # pragma: allowlist secret
        "53e9b7a2c614",  # pragma: allowlist secret
        "e9c5a1b7d3f6",  # pragma: allowlist secret
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
            assert MigrationContext.configure(connection).get_current_heads() == tuple(
                ScriptDirectory.from_config(config).get_heads()
            )
            assert "permissions" in {column["name"] for column in inspect(connection).get_columns("apikey")}
            assert connection.execute(text("SELECT id, enabled, reason FROM maintenance_state")).one() == (
                1,
                False,
                None,
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "intermediate_revision",
    [None, "f4b8c1d2e3a6", "a8c2e6f4b9d1"],  # pragma: allowlist secret
)
def test_upgrading_maintenance_preserves_existing_state(db_url, intermediate_revision):  # noqa: F811
    """Upgrading from maintenance alone or with earlier release migrations preserves an active freeze."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, "4d6e8f0a2b3c")  # pragma: allowlist secret
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE maintenance_state SET enabled = :enabled, reason = :reason WHERE id = 1"),
                {"enabled": True, "reason": "Upgrade rehearsal"},
            )
            state = connection.execute(text("SELECT * FROM maintenance_state")).one()
        if intermediate_revision is not None:
            command.upgrade(config, intermediate_revision)
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.execute(text("SELECT * FROM maintenance_state")).one() == state
            assert MigrationContext.configure(connection).get_current_heads() == tuple(
                ScriptDirectory.from_config(config).get_heads()
            )
    finally:
        engine.dispose()
