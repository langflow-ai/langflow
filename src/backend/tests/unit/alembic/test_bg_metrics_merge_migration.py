"""Published metrics and release migration branches must reach one head safely."""

from uuid import uuid4

import pytest
from alembic import command
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401


def test_job_metrics_and_release_have_single_head():
    """Database startup must resolve head after independent release migrations."""
    script = ScriptDirectory.from_config(_make_alembic_cfg("sqlite+aiosqlite://"))
    assert len(script.get_heads()) == 1


@pytest.mark.parametrize(
    "prior_revision",
    [
        "base",
        "b3f7c2a91d48",  # pragma: allowlist secret
        "d8f2c3a4b5e6",  # pragma: allowlist secret
        "c7e9b2d4f6a8",  # pragma: allowlist secret
        "4e7a2b9c1d05",  # pragma: allowlist secret
        "e2c4a6f8b0d3",  # pragma: allowlist secret
        "f9d3b7a5c201",  # pragma: allowlist secret
        "c3e1d5a7f902",  # pragma: allowlist secret
        "f194a1b2c3d4",  # pragma: allowlist secret
        "a6d8e0f2b4c7",  # pragma: allowlist secret
        "b5d8e2a4c617",  # pragma: allowlist secret
        "f1a7c3e95d82",  # pragma: allowlist secret
        "f4b8c1d2e3a6",  # pragma: allowlist secret
        "c2e8b4f6a710",  # pragma: allowlist secret
        "8d4c7a2e9b61",  # pragma: allowlist secret
        "9e6b2c4a7d80",  # pragma: allowlist secret
        "a8e4c2f6b901",  # pragma: allowlist secret
        "7fd2c80e5a39",  # pragma: allowlist secret
        "f6a2c8e4b901",  # pragma: allowlist secret
        "f6b9d2e4a731",  # pragma: allowlist secret
        "c6e8a2f4b901",  # pragma: allowlist secret
        "f5a7b9c2d4e6",  # pragma: allowlist secret
        "e7b3d9a5c102",  # pragma: allowlist secret
        "d7e9a1c3f5b8",  # pragma: allowlist secret
    ],
)
def test_job_metrics_and_release_upgrade_to_single_head(db_url, prior_revision):  # noqa: F811
    """Upgrade each prior head without losing jobs or skipping a schema change."""
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, prior_revision)
    engine = create_engine(_engine_url(db_url))
    job_id = str(uuid4())
    try:
        if prior_revision != "base":
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
            assert {"ix_job_status_created", "ix_job_finished_timestamp", "ix_job_claim_scan"} <= indexes
            assert "lease_heartbeat_at" in {column["name"] for column in inspector.get_columns("job")}
            assert "is_personal" in {column["name"] for column in inspector.get_columns("folder")}
            assert "version_token" in {column["name"] for column in inspector.get_columns("flow")}
            assert "retired_at" in {column["name"] for column in inspector.get_columns("user")}
            assert inspector.has_table("project_replacement_operation")
            assert "project_name" in {
                column["name"] for column in inspector.get_columns("project_replacement_operation")
            }
            assert {"represented_issuer", "represented_subject"} <= {
                column["name"] for column in inspector.get_columns("audit_events")
            }
            assert inspector.has_table("worker_registry")
            assert inspector.has_table("refresh_token_session")
            assert inspector.has_table("trigger_renewal_observation")
            assert "approved_trigger_kinds" in {
                column["name"] for column in inspector.get_columns("policy_bundle_revision")
            }
            trigger_state_check = next(
                check
                for check in inspector.get_check_constraints("trigger_event")
                if check["name"] == "ck_trigger_event_state"
            )
            assert "'skipped'" in trigger_state_check["sqltext"]
            if prior_revision != "base":
                assert (
                    connection.execute(
                        text("SELECT COUNT(*) FROM job WHERE job_id = :job_id"), {"job_id": job_id}
                    ).scalar()
                    == 1
                )
            assert MigrationContext.configure(connection).get_current_heads() == (
                ScriptDirectory.from_config(config).get_current_head(),
            )
    finally:
        engine.dispose()
