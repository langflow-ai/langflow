"""The trigger policy expansion preserves existing bundle identity and rolls back."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.migration import MigrationContext
from alembic.operations import Operations

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "f6a2c8e4b901"  # pragma: allowlist secret
_REVISION = "c6e8a2f4b901"  # pragma: allowlist secret


def test_trigger_governance_round_trip_preserves_existing_bundle_hash(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PRIOR_REVISION)
    engine = sa.create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            before = dict(connection.execute(sa.select(revisions.c.revision, revisions.c.content_hash)).all())
            assert before

        command.upgrade(config, _REVISION)
        with engine.begin() as connection:
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            after = connection.execute(sa.select(revisions)).mappings().all()
            assert {row["revision"]: row["content_hash"] for row in after} == before
            assert all(row["approved_trigger_kinds"] is None for row in after)
            columns = {column["name"] for column in sa.inspect(connection).get_columns("trigger_renewal_observation")}
            assert {"previous_expires_at", "expires_at", "outcome", "gap_seconds"} <= columns
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            connection.execute(revisions.update().values(approved_trigger_kinds=[]))

        # Re-entering the guarded expansion is safe for a partially upgraded DB.
        path = Path(__file__).parents[3] / "base/langflow/alembic/versions/c6e8a2f4b901_trigger_governance.py"
        spec = importlib.util.spec_from_file_location("trigger_governance_migration", path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as connection:
            module.op = Operations(MigrationContext.configure(connection))
            module.upgrade()

        command.downgrade(config, _PRIOR_REVISION)
        with engine.begin() as connection:
            inspector = sa.inspect(connection)
            assert "trigger_renewal_observation" not in inspector.get_table_names()
            assert "approved_trigger_kinds" not in {
                column["name"] for column in inspector.get_columns("policy_bundle_revision")
            }
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            assert dict(connection.execute(sa.select(revisions.c.revision, revisions.c.content_hash)).all()) == before
        command.upgrade(config, _REVISION)
    finally:
        engine.dispose()
