"""Expand represented identity without losing history or old-writer compatibility."""

from __future__ import annotations

import base64
import importlib
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from langflow.services.audit.represented import decode_identity_value
from langflow.services.database.models.audit_event.model import (
    REPRESENTED_ISSUER_MAX_LENGTH,
    REPRESENTED_SUBJECT_MAX_LENGTH,
    AuditEvent,
)

from .test_migration_execution import (  # noqa: F401
    _create_pg_test_database,
    _drop_pg_test_database,
    _engine_url,
    _pg_url,
    db_url,
)

OLD = importlib.import_module("langflow.alembic.versions.df1410b1eefa_add_audit_events")
NEW = importlib.import_module("langflow.alembic.versions.a6f81c2d903b_add_represented_audit_identity")
BOUNDED = importlib.import_module("langflow.alembic.versions.d9a2c7e4f610_bound_audit_identity_indexes")


def _upgrade(module, connection):
    """Run one revision against the supplied real database connection."""
    previous = module.op
    try:
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
    finally:
        module.op = previous


def _event(table, **identity):
    """Build a complete audit insert with optional independent identity fields."""
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


def test_migration_preserves_acting_history_without_inventing_represented_identity(db_url):  # noqa: F811
    """Keep old acting history and reject incomplete identity pairs after repeated upgrades."""
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
            assert all(row.represented_issuer is None and row.represented_subject is None for row in rows)
            assert [(row.acting_issuer, row.acting_subject) for row in rows if row.acting_issuer] == [
                ("issuer", "用户")
            ]
            # Both independent identity pairs remain valid after migration.
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


@pytest.mark.parametrize("schema", ["migration", "model"])
@pytest.mark.parametrize("prefix", ["acting", "represented"])
def test_maximum_unicode_identity_commits_with_mutation(db_url, schema, prefix):  # noqa: F811
    """Commit maximum UTF-8 identities and resource changes together on both schema paths."""
    engine = sa.create_engine(_engine_url(db_url))
    # Distinct four-byte characters avoid compression hiding an oversized B-tree key.
    issuer = "".join(chr(0x10000 + index) for index in range(REPRESENTED_ISSUER_MAX_LENGTH))
    subject = "".join(chr(0x18000 + index) for index in range(REPRESENTED_SUBJECT_MAX_LENGTH))
    for value, limit in ((issuer, REPRESENTED_ISSUER_MAX_LENGTH), (subject, REPRESENTED_SUBJECT_MAX_LENGTH)):
        encoded = "v1." + base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")
        assert decode_identity_value(encoded, limit) == value
    try:
        with engine.begin() as conn:
            if schema == "migration":
                _upgrade(OLD, conn)
                _upgrade(NEW, conn)
                _upgrade(BOUNDED, conn)
            else:
                AuditEvent.__table__.create(conn)
            table = sa.Table("audit_events", sa.MetaData(), autoload_with=conn)
            mutation = sa.Table("deployment_write", sa.MetaData(), sa.Column("id", sa.Integer, primary_key=True))
            mutation.create(conn)
        with engine.begin() as conn:
            conn.execute(sa.insert(mutation).values(id=1))
            conn.execute(_event(table, **{f"{prefix}_issuer": issuer, f"{prefix}_subject": subject}))
            conn.execute(_event(table, **{f"{prefix}_issuer": "different-issuer", f"{prefix}_subject": subject}))
        with engine.connect() as conn:
            assert conn.scalar(sa.select(sa.func.count()).select_from(mutation)) == 1
            issuer_column, subject_column = table.c[f"{prefix}_issuer"], table.c[f"{prefix}_subject"]
            identities = list(conn.execute(sa.select(issuer_column, subject_column)))
            assert (issuer, subject) in identities
            assert ("different-issuer", subject) in identities
            assert (
                conn.scalar(
                    sa.select(sa.func.count())
                    .select_from(table)
                    .where(issuer_column == issuer, subject_column == subject)
                )
                == 1
            )
    finally:
        engine.dispose()


def test_bounded_indexes_repair_draft_shapes_without_changing_history(db_url):  # noqa: F811
    """Preserve existing audit rows when repairing both legacy issuer indexes."""
    engine = sa.create_engine(_engine_url(db_url))
    try:
        with engine.begin() as conn:
            _upgrade(OLD, conn)
            _upgrade(NEW, conn)
            table = sa.Table("audit_events", sa.MetaData(), autoload_with=conn)
            for prefix in ("acting", "represented"):
                name = f"ix_audit_events_{prefix}_timeline"
                conn.execute(sa.schema.DropIndex(sa.Index(name)))
                sa.Index(name, table.c[f"{prefix}_issuer"], table.c[f"{prefix}_subject"], table.c.timestamp).create(
                    conn
                )
                conn.execute(_event(table, **{f"{prefix}_issuer": "original-issuer", f"{prefix}_subject": prefix}))
            before = list(conn.execute(sa.select(table).order_by(table.c.id)))
            if conn.dialect.name == "postgresql":
                # Reproduce the original failure before applying the repair.
                issuer = "".join(chr(0x10000 + index) for index in range(1024))
                for prefix in ("acting", "represented"):
                    with pytest.raises(sa.exc.DBAPIError) as rejected, conn.begin_nested():
                        conn.execute(_event(table, **{f"{prefix}_issuer": issuer, f"{prefix}_subject": prefix}))
                    assert rejected.value.orig.sqlstate == "54000"
            _upgrade(BOUNDED, conn)
            _upgrade(BOUNDED, conn)
            indexes = {item["name"]: item["column_names"] for item in sa.inspect(conn).get_indexes("audit_events")}
            for prefix in ("acting", "represented"):
                assert indexes[f"ix_audit_events_{prefix}_timeline"] == [f"{prefix}_subject", "timestamp"]
            assert list(conn.execute(sa.select(table).order_by(table.c.id))) == before
            BOUNDED.downgrade()
            assert list(conn.execute(sa.select(table).order_by(table.c.id))) == before
    finally:
        engine.dispose()


def test_represented_identity_and_release_migrations_have_one_head():
    """Keep the repair, represented identity, and release revisions on one migration head."""
    scripts = ScriptDirectory(str(Path(NEW.__file__).resolve().parents[1]))
    head = scripts.get_current_head()
    assert head is not None
    revisions = {revision.revision for revision in scripts.iterate_revisions(head, "base")}
    assert NEW.revision in revisions
    assert BOUNDED.revision in revisions
    assert "1d8d193028c8" in revisions  # pragma: allowlist secret
