"""Expand represented identity without losing history or old-writer compatibility."""

from __future__ import annotations

import importlib
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from .test_migration_execution import (  # noqa: F401
    _create_pg_test_database,
    _drop_pg_test_database,
    _engine_url,
    _pg_url,
    db_url,
)

OLD = importlib.import_module("langflow.alembic.versions.df1410b1eefa_add_audit_events")
NEW = importlib.import_module("langflow.alembic.versions.a6f81c2d903b_add_represented_audit_identity")


def _upgrade(module, connection):
    previous = module.op
    try:
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
    finally:
        module.op = previous


def _event(table, **identity):
    return sa.insert(table).values(
        id=str(uuid4()),
        resource_type="project",
        resource_id=str(uuid4()),
        actor_type="api_key",
        action="project:write",
        operation="patch",
        event_type="action",
        result="succeeded",
        request_id=str(uuid4()),
        details={},
        **identity,
    )


def test_migration_backfills_history_and_keeps_both_pairs_valid(db_url):  # noqa: F811
    engine = sa.create_engine(_engine_url(db_url))
    try:
        with engine.begin() as conn:
            _upgrade(OLD, conn)
            table = sa.Table("audit_events", sa.MetaData(), autoload_with=conn)
            conn.execute(_event(table, acting_issuer="issuer", acting_subject="用户"))
            conn.execute(_event(table))
            _upgrade(NEW, conn)
            _upgrade(NEW, conn)
            table = sa.Table("audit_events", sa.MetaData(), autoload_with=conn)
            rows = list(conn.execute(sa.select(table)))
            assert len(rows) == 2
            represented = [row for row in rows if row.represented_issuer]
            assert [(row.represented_issuer, row.represented_subject) for row in represented] == [("issuer", "用户")]
            # An old process may still insert only acting_* after migration.
            conn.execute(_event(table, acting_issuer="old-writer", acting_subject="later"))
            conn.execute(_event(table, represented_issuer="new-writer", represented_subject="later"))
            indexes = {item["name"] for item in sa.inspect(conn).get_indexes("audit_events")}
            assert {"ix_audit_events_acting_timeline", "ix_audit_events_represented_timeline"} <= indexes
        for identity in ({"represented_issuer": "partial"}, {"acting_subject": "partial"}):
            with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
                conn.execute(_event(table, **identity))
        # Additive downgrade deliberately retains audit history.
        NEW.downgrade()
        with engine.connect() as conn:
            assert conn.scalar(sa.select(sa.func.count()).select_from(table)) == 4
    finally:
        engine.dispose()
