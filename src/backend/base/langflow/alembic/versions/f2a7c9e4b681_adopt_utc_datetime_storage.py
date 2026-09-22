"""Adopt SQLModel's timezone-aware datetime storage.

Phase: CONTRACT
Revision ID: f2a7c9e4b681
Revises: e6f9a2b4c8d1

SQLModel 0.0.45 changed inferred datetime columns to UTCDateTime. Freeze the
affected columns here rather than importing models that may change later.
Known Langflow writers use UTC; interpret historical naive values as UTC in
both directions, independently of the PostgreSQL session timezone.

Stop all older application instances before upgrading or downgrading: their
schema checks expect the previous types. PostgreSQL takes exclusive table
locks and may rewrite populated tables. SELECT COUNT checks preserve row and
non-null value counts under those locks. SQLite storage already holds UTC
without an offset and needs no DDL; the new type restores UTC when reading.
"""

import sqlalchemy as sa
from alembic import op

revision = "f2a7c9e4b681"  # pragma: allowlist secret
down_revision = "e6f9a2b4c8d1"  # pragma: allowlist secret
branch_labels = None
depends_on = None

_TIMESTAMP_COLUMNS = {
    "apikey": ("last_used_at",),
    "file": ("created_at", "updated_at"),
    "flow": ("updated_at",),
    "mcp_server": ("created_at", "updated_at"),
    "message": ("timestamp",),
    "span": ("start_time", "end_time"),
    "sso_user_profile": ("sso_last_login_at", "created_at", "updated_at"),
    "trace": ("start_time", "end_time"),
    "transaction": ("timestamp",),
    "user": ("create_at", "updated_at", "last_login_at"),
    "vertex_build": ("timestamp",),
}


def _convert_timestamps(connection: sa.Connection, *, timezone_aware: bool) -> None:
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    quote = connection.dialect.identifier_preparer.quote
    for table_name, names in _TIMESTAMP_COLUMNS.items():
        if table_name not in tables:
            continue
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        to_convert = [
            name
            for name in names
            if name in columns
            and isinstance(columns[name]["type"], sa.DateTime)
            and columns[name]["type"].timezone != timezone_aware
        ]
        if not to_convert:
            continue

        # Lock before counting so concurrent writes cannot invalidate verification.
        connection.execute(sa.text(f"LOCK TABLE {quote(table_name)} IN ACCESS EXCLUSIVE MODE"))
        table = sa.table(table_name, *(sa.column(name) for name in to_convert))
        counts = sa.select(sa.func.count(), *(sa.func.count(column) for column in table.c)).select_from(table)
        before = connection.execute(counts).one()
        for name in to_convert:
            op.alter_column(
                table_name,
                name,
                existing_type=columns[name]["type"],
                type_=sa.DateTime(timezone=timezone_aware),
                postgresql_using=f"{quote(name)} AT TIME ZONE 'UTC'",
            )
        if connection.execute(counts).one() != before:
            msg = f"Timestamp conversion changed row or non-null counts in {table_name}"
            raise RuntimeError(msg)


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        return
    if connection.dialect.name != "postgresql":
        msg = "UTC datetime migration supports PostgreSQL and SQLite only"
        raise NotImplementedError(msg)
    _convert_timestamps(connection, timezone_aware=True)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        return
    if connection.dialect.name != "postgresql":
        msg = "UTC datetime downgrade supports PostgreSQL and SQLite only"
        raise NotImplementedError(msg)
    _convert_timestamps(connection, timezone_aware=False)
