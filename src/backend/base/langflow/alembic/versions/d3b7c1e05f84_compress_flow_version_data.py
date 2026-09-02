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


def _backfill(conn, source: sa.Column, target: sa.Column, convert) -> int:
    written = 0
    for batch in _rows(conn, source):
        for row in batch:
            value = convert(getattr(row, source.name))
            result = conn.execute(
                _flow_version.update().where(_flow_version.c.id == row.id).values({target.name: value})
            )
            written += result.rowcount
    return written


def _drop_when_nothing_is_pending(conn, source: sa.Column, target: sa.Column, written: int) -> None:
    pending = conn.execute(
        sa.select(sa.func.count()).select_from(_flow_version).where(source.is_not(None), target.is_(None))
    ).scalar_one()
    if pending:
        msg = (
            f"{pending} flow_version rows still hold data in {source.name} after backfilling "
            f"{written} into {target.name}"
        )
        raise RuntimeError(msg)
    with op.batch_alter_table("flow_version") as batch_op:
        batch_op.drop_column(source.name)


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("flow_version", conn):
        return

    if not migration.column_exists("flow_version", "data_gz", conn):
        op.add_column("flow_version", sa.Column("data_gz", sa.LargeBinary(), nullable=True))
    _set_external_storage(conn)

    if migration.column_exists("flow_version", "data", conn):
        written = _backfill(
            conn,
            _flow_version.c.data,
            _flow_version.c.data_gz,
            lambda data: gzip.compress(
                json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), COMPRESS_LEVEL
            ),
        )
        _drop_when_nothing_is_pending(conn, _flow_version.c.data, _flow_version.c.data_gz, written)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("flow_version", conn):
        return

    if not migration.column_exists("flow_version", "data", conn):
        op.add_column("flow_version", sa.Column("data", sa.JSON(), nullable=True))

    if migration.column_exists("flow_version", "data_gz", conn):
        written = _backfill(
            conn,
            _flow_version.c.data_gz,
            _flow_version.c.data,
            lambda blob: json.loads(gzip.decompress(blob)),
        )
        _drop_when_nothing_is_pending(conn, _flow_version.c.data_gz, _flow_version.c.data, written)
