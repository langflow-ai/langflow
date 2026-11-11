"""Rolling-upgrade contract for persisted integration-provider ceilings."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import command
from lfx.services.policy_bundle.base import decode_integration_provider_ids, encode_integration_provider_ids

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "e5a7c9b1d3f2"  # pragma: allowlist secret
_REVISION = "f4b8c1d2e3a6"  # pragma: allowlist secret


def test_migration_preserves_legacy_ceilings_and_late_writes(db_url):  # noqa: F811
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
            values = list(connection.execute(sa.select(revisions.c.approved_integration_provider_ids)).scalars())
            assert values
            assert all(value == [] for value in values)
            column = next(
                column
                for column in sa.inspect(connection).get_columns("policy_bundle_revision")
                if column["name"] == "approved_integration_provider_ids"
            )
            assert column["default"] is not None

            # N-1 can still write an unrestricted empty list after migration.
            connection.execute(revisions.update().values(approved_integration_provider_ids=[]))
            value = connection.execute(sa.select(revisions.c.approved_integration_provider_ids)).scalars().first()
            assert decode_integration_provider_ids(value) is None

            # A new deny-all remains nonempty for old readers, including downgrade.
            encoded = encode_integration_provider_ids(frozenset())
            connection.execute(revisions.update().values(approved_integration_provider_ids=encoded))

        command.downgrade(alembic_cfg, _PRIOR_REVISION)

        with engine.begin() as connection:
            revisions = sa.Table("policy_bundle_revision", sa.MetaData(), autoload_with=connection)
            values = list(connection.execute(sa.select(revisions.c.approved_integration_provider_ids)).scalars())
            assert values
            assert all(value == encoded for value in values)
            assert all(not (set(value) & {"google", "slack"}) for value in values)
            assert all(decode_integration_provider_ids(value) == frozenset() for value in values)
    finally:
        engine.dispose()
