"""Store flow version snapshots gzipped.

Phase: MIGRATE
Revision ID: d3b7c1e05f84
Revises: c9f2e5a7b1d4
Create Date: 2026-09-02
"""

from __future__ import annotations

import gzip
import json
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d3b7c1e05f84"  # pragma: allowlist secret
down_revision: str | None = "c9f2e5a7b1d4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BATCH_SIZE = 200
COMPRESS_LEVEL = 6

_flow_version = sa.table(
    "flow_version",
    sa.column("id"),
    sa.column("data", sa.JSON()),
    sa.column("data_gz", sa.LargeBinary()),
)


def _rows(conn, source: sa.Column):
    offset = 0
    while True:
        stmt = (
            sa.select(_flow_version.c.id, source)
            .where(source.is_not(None))
            .order_by(_flow_version.c.id)
            .limit(BATCH_SIZE)
            .offset(offset)
        )
        batch = conn.execute(stmt).fetchall()
        if not batch:
            return
        yield batch
        offset += BATCH_SIZE


def _set_external_storage(conn) -> None:
    if conn.dialect.name == "postgresql":
        op.execute("ALTER TABLE flow_version ALTER COLUMN data_gz SET STORAGE EXTERNAL")


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("flow_version", conn):
        return

    if not migration.column_exists("flow_version", "data_gz", conn):
        op.add_column("flow_version", sa.Column("data_gz", sa.LargeBinary(), nullable=True))
    _set_external_storage(conn)

    if migration.column_exists("flow_version", "data", conn):
        migrated = 0
        for batch in _rows(conn, _flow_version.c.data):
            for row in batch:
                payload = gzip.compress(
                    json.dumps(row.data, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
                    COMPRESS_LEVEL,
                )
                result = conn.execute(
                    _flow_version.update().where(_flow_version.c.id == row.id).values(data_gz=payload)
                )
                migrated += result.rowcount
        pending = conn.execute(
            sa.select(sa.func.count())
            .select_from(_flow_version)
            .where(_flow_version.c.data.is_not(None), _flow_version.c.data_gz.is_(None))
        ).scalar_one()
        if pending:
            msg = f"{pending} flow_version rows still hold uncompressed data after backfilling {migrated}"
            raise RuntimeError(msg)
        with op.batch_alter_table("flow_version") as batch_op:
            batch_op.drop_column("data")


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("flow_version", conn):
        return

    if not migration.column_exists("flow_version", "data", conn):
        op.add_column("flow_version", sa.Column("data", sa.JSON(), nullable=True))

    if migration.column_exists("flow_version", "data_gz", conn):
        for batch in _rows(conn, _flow_version.c.data_gz):
            for row in batch:
                payload = json.loads(gzip.decompress(row.data_gz))
                conn.execute(_flow_version.update().where(_flow_version.c.id == row.id).values(data=payload))
        with op.batch_alter_table("flow_version") as batch_op:
            batch_op.drop_column("data_gz")
