"""Round-trip contract for the INT-7 policy-bundle integration columns (LE-2465)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import command
from alembic.migration import MigrationContext
from alembic.operations import Operations

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "a7d8e9f0b1c2"  # pragma: allowlist secret
_REVISION = "b4c7d2e8f1a3"  # pragma: allowlist secret
_COLUMNS = ("approved_integration_provider_ids", "blocked_integration_action_keys")


def _revision_columns(connection: sa.Connection) -> dict[str, dict]:
    return {column["name"]: column for column in sa.inspect(connection).get_columns("policy_bundle_revision")}


def test_integration_columns_upgrade_downgrade_and_preserve_pre_expand_rows(db_url):  # noqa: F811
    """A revision written before the columns existed reads back as governing nothing."""
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            assert set(_COLUMNS).isdisjoint(_revision_columns(connection))
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            existing = connection.execute(sa.select(revisions)).mappings().all()
            assert existing, "the shared bundle migration seeds an initial revision"
            preserved_hash = existing[0]["content_hash"]

        command.upgrade(alembic_cfg, _REVISION)

        with engine.begin() as connection:
            columns = _revision_columns(connection)
            for name in _COLUMNS:
                assert name in columns
                assert columns[name]["nullable"] is True
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            row = connection.execute(sa.select(revisions)).mappings().first()
            # Pre-expand rows are not backfilled; the server default and the
            # non-empty-only hash rule keep them valid and unchanged.
            assert row["approved_integration_provider_ids"] in (None, [])
            assert row["blocked_integration_action_keys"] in (None, [])
            assert row["content_hash"] == preserved_hash

            connection.execute(
                revisions.update().values(
                    approved_integration_provider_ids=["google"],
                    blocked_integration_action_keys=["integrations.google.drive.delete"],
                )
            )

        with engine.begin() as connection:
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            row = connection.execute(sa.select(revisions)).mappings().first()
            assert row["approved_integration_provider_ids"] == ["google"]
            assert row["blocked_integration_action_keys"] == ["integrations.google.drive.delete"]

        command.downgrade(alembic_cfg, _PRIOR_REVISION)

        with engine.begin() as connection:
            assert set(_COLUMNS).isdisjoint(_revision_columns(connection))
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            assert connection.execute(sa.select(sa.func.count()).select_from(revisions)).scalar_one() == len(existing)

        command.upgrade(alembic_cfg, _REVISION)

        with engine.begin() as connection:
            assert set(_COLUMNS) <= set(_revision_columns(connection))
    finally:
        engine.dispose()


def test_upgrade_is_idempotent_when_the_columns_already_exist(db_url):  # noqa: F811
    """The guarded add_column re-runs cleanly on a partially upgraded database."""
    import importlib.util
    from pathlib import Path

    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _REVISION)

    path = Path(__file__).parents[3] / "base/langflow/alembic/versions/b4c7d2e8f1a3_add_policy_bundle_integrations.py"
    spec = importlib.util.spec_from_file_location("policy_bundle_integrations_migration", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            original_op = module.op
            module.op = Operations(MigrationContext.configure(connection))
            try:
                module.upgrade()
            finally:
                module.op = original_op
            assert set(_COLUMNS) <= set(_revision_columns(connection))
    finally:
        engine.dispose()
