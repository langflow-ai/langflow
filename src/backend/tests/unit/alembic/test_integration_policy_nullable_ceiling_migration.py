"""Round-trip contract for nullable integration-provider ceilings."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import command

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "c6a81d3e9502"  # pragma: allowlist secret
_REVISION = "f4b8c1d2e3a6"  # pragma: allowlist secret


def test_empty_legacy_ceilings_become_unrestricted_null(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, _PRIOR_REVISION)

    engine = sa.create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            connection.execute(revisions.update().values(approved_integration_provider_ids=[]))

        command.upgrade(alembic_cfg, _REVISION)

        with engine.begin() as connection:
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            values = connection.execute(sa.select(revisions.c.approved_integration_provider_ids)).scalars()
            assert all(value is None for value in values)
            column = next(
                column
                for column in sa.inspect(connection).get_columns("policy_bundle_revision")
                if column["name"] == "approved_integration_provider_ids"
            )
            assert column["default"] is None

            # Empty lists written after the migration are explicit deny-all.
            connection.execute(revisions.update().values(approved_integration_provider_ids=[]))
            assert connection.execute(sa.select(revisions.c.approved_integration_provider_ids)).scalars().first() == []

        with engine.begin() as connection:
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            connection.execute(revisions.update().values(approved_integration_provider_ids=sa.null()))

        command.downgrade(alembic_cfg, _PRIOR_REVISION)

        with engine.begin() as connection:
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            values = list(connection.execute(sa.select(revisions.c.approved_integration_provider_ids)).scalars())
            assert all(value == [] for value in values), values
    finally:
        engine.dispose()
