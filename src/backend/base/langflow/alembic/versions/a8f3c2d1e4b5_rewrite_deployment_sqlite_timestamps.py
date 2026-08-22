"""Rewrite deployment-family SQLite timestamps; drop now() server defaults

Phase: EXPAND

Bug
---
On SQLite, ``func.now()`` / ``datetime('now')`` store second-level precision
(``YYYY-MM-DD HH:MM:SS``). When that same value is loaded into Python and
SQLAlchemy later sends it as a query parameter, it is formatted with
microsecond precision (``...SS.ffffff``). Comparisons then fail when one
side is the stored ORM column value (still second-level text) and the
other is SQLAlchemy's DateTime formatting of a previously loaded ORM
datetime used as a parameter — even if both represent the same
wall-clock second.

An app-only fix (normalize the value in every query, cast/format in SQL,
special-case whole-second equality) would have to live in every reader
forever, and would still leave mixed formats (``YYYY-MM-DD HH:MM:SS`` and
``...SS.ffffff``) in the table. Rewriting once through
``DateTime(timezone=True)``, plus changing the deployment-family models to
write UTC via Column ``default`` / ``onupdate`` (with no
``server_default=func.now()``; Field stays ``default=None``), makes what
is stored match what SQLAlchemy sends later, so ordinary
equality/ordering work without per-query workarounds, and keeps a single
predictable storage format for timestamps.

This migration:
1. On SQLite: re-reads each timestamp as ``DateTime(timezone=True)`` and
   writes it back through the same type (idempotent).
2. On all dialects: drops ``server_default`` / ``DEFAULT CURRENT_TIMESTAMP``
   from these columns so the DB schema matches the models (ORM must supply
   Python UTC; raw inserts must too).

No-op data rewrite on PostgreSQL (real timestamp comparisons).

Revision ID: a8f3c2d1e4b5
Revises: 247308ce2598
Create Date: 2026-07-09 23:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "a8f3c2d1e4b5"  # pragma: allowlist secret
down_revision: str | None = "247308ce2598"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES_AND_COLUMNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("deployment", ("created_at", "updated_at")),
    ("deployment_provider_account", ("created_at", "updated_at")),
    ("flow_version_deployment_attachment", ("created_at", "updated_at")),
)


def _rewrite_table_timestamps(conn, table_name: str, column_names: tuple[str, ...]) -> None:
    if not migration.table_exists(table_name, conn):
        return
    # Leave ``id`` untyped so SQLite's CHAR/BLOB UUID storage round-trips as-is.
    columns = [sa.column("id")]
    columns.extend(
        sa.column(name, sa.DateTime(timezone=True))
        for name in column_names
        if migration.column_exists(table_name, name, conn)
    )
    if len(columns) == 1:
        return

    table = sa.table(table_name, *columns)
    timestamp_cols = [c for c in columns if c.name != "id"]
    rows = conn.execute(sa.select(table.c.id, *timestamp_cols)).all()
    params = [
        {"b_id": row.id, **{col.name: getattr(row, col.name) for col in timestamp_cols}}
        for row in rows
        if not all(getattr(row, col.name) is None for col in timestamp_cols)
    ]
    if not params:
        return
    # One executemany: DateTime bind formatting still runs per parameter set.
    stmt = (
        sa.update(table)
        .where(table.c.id == sa.bindparam("b_id"))
        .values(**{col.name: sa.bindparam(col.name) for col in timestamp_cols})
    )
    conn.execute(stmt, params)


def _drop_timestamp_server_defaults(conn, table_name: str, column_names: tuple[str, ...]) -> None:
    if not migration.table_exists(table_name, conn):
        return
    existing = [name for name in column_names if migration.column_exists(table_name, name, conn)]
    if not existing:
        return
    # Single batch_alter_table so SQLite recreates the table once for all columns.
    with op.batch_alter_table(table_name) as batch_op:
        for name in existing:
            batch_op.alter_column(
                name,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=None,
            )


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        for table_name, column_names in _TABLES_AND_COLUMNS:
            _rewrite_table_timestamps(conn, table_name, column_names)
    for table_name, column_names in _TABLES_AND_COLUMNS:
        _drop_timestamp_server_defaults(conn, table_name, column_names)


def downgrade() -> None:
    # Format normalization is forward-only; padded microsecond strings remain valid.
    # Restoring server_default=func.now() would reintroduce the SQLite whole-second bug.
    pass
