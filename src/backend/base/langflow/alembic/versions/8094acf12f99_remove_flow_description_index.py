"""Remove the flow description index that rejects long PostgreSQL text values.

Revision ID: 8094acf12f99
Revises: 7fd2c80e5a39
Create Date: 2026-11-15

Phase: MIGRATE
Safe to rollback: NO (when flow descriptions exceeding PostgreSQL B-tree limits exist)

Recreating the B-tree index on flow.description during downgrade will fail on
PostgreSQL if any rows contain descriptions exceeding 1/3 of the buffer page size
(~2,704 bytes for 8KB pages). The downgrade intentionally does not truncate, alter,
or delete existing user data to force index creation; existing oversized descriptions
must be manually resolved prior to rollback if recreating this index is required.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8094acf12f99"  # pragma: allowlist secret
down_revision: str | None = "7fd2c80e5a39"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("flow", schema=None) as batch_op:
        # SQLite batch mode requires index reflection; drop if exists safely
        batch_op.drop_index("ix_flow_description", if_exists=True)


def downgrade() -> None:
    # Caveat: Recreating the B-tree index on flow.description will fail on PostgreSQL
    # if any rows contain descriptions exceeding 1/3 of the buffer page size (~2,704 bytes).
    # The downgrade preserves all user data intact without truncation.
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.create_index(
            "ix_flow_description",
            ["description"],
            unique=False,
        )
