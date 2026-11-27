"""Index the vertex_build columns flow-scoped reads and the per-vertex trim filter on.

Revision ID: b3e7d1f5a9c2
Revises: 7a4c2e9b6d15
Create Date: 2026-11-18

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

revision: str = "b3e7d1f5a9c2"  # pragma: allowlist secret
down_revision: str | None = "7a4c2e9b6d15"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ``flow_id`` narrows the flow-scoped read and the per-vertex trim to one flow,
# ``id`` lets them group and look up rows per vertex, and ``timestamp`` last
# lets the trim read one vertex's builds in timestamp order. The ``build_id``
# tie-break in the trim is still sorted.
_INDEX_NAME = "ix_vertex_build_flow_id_id_timestamp"
_INDEX_COLUMNS = ["flow_id", "id", "timestamp"]


def _existing_index_names(conn) -> set[str]:
    return {index["name"] for index in sa.inspect(conn).get_indexes("vertex_build")}


def _invalid_postgres_indexes(conn, names: set[str]) -> set[str]:
    """Names among ``names`` that Postgres left INVALID after a failed concurrent build.

    A cancelled ``CREATE INDEX CONCURRENTLY`` leaves the index in place but unusable,
    and it still shows up in the inspector. Without this the retry would consider the
    index present and skip it, leaving a dead index the planner never uses.
    """
    if not names:
        return set()
    rows = conn.execute(
        sa.text(
            "SELECT c.relname FROM pg_class c "
            "JOIN pg_index i ON i.indexrelid = c.oid "
            "WHERE i.indrelid = 'vertex_build'::regclass AND NOT i.indisvalid AND c.relname = ANY(:names)"
        ),
        {"names": sorted(names)},
    )
    return {row[0] for row in rows}


def upgrade() -> None:
    """Add the read-path index without blocking writes on a large vertex_build table."""
    conn = op.get_bind()
    if not migration.table_exists("vertex_build", conn):
        return
    is_postgres = conn.dialect.name == "postgresql"
    existing = _existing_index_names(conn)

    if is_postgres:
        invalid = _invalid_postgres_indexes(conn, existing & {_INDEX_NAME})
        if invalid:
            # Drop before rebuilding, otherwise the name is taken by a dead index.
            with op.get_context().autocommit_block():
                for name in sorted(invalid):
                    op.drop_index(name, table_name="vertex_build", postgresql_concurrently=True)
            existing -= invalid

    if _INDEX_NAME in existing:
        return

    if is_postgres:
        # A plain CREATE INDEX holds a write lock for the whole build, and every
        # logged build writes this table. CONCURRENTLY cannot run in the
        # migration transaction.
        with op.get_context().autocommit_block():
            op.create_index(_INDEX_NAME, "vertex_build", _INDEX_COLUMNS, postgresql_concurrently=True)
    else:
        op.create_index(_INDEX_NAME, "vertex_build", _INDEX_COLUMNS)


def downgrade() -> None:
    """Drop the read-path index, leaving vertex_build rows untouched."""
    conn = op.get_bind()
    if not migration.table_exists("vertex_build", conn):
        return
    if _INDEX_NAME not in _existing_index_names(conn):
        return

    if conn.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(_INDEX_NAME, table_name="vertex_build", postgresql_concurrently=True)
    else:
        op.drop_index(_INDEX_NAME, table_name="vertex_build")
