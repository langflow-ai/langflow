"""Record explicit flow revocations for anonymous compatibility grants.

Revision ID: b7c9d1e3f508
Revises: a6b8c0d2e4f7
Phase: EXPAND
Safe to rollback: NO (compatibility grants no longer respect explicit revocations)
Services compatible: Older versions ignore the additional column.
"""

import sqlalchemy as sa
from alembic import op

revision = "b7c9d1e3f508"  # pragma: allowlist secret - Alembic revision
down_revision = "a6b8c0d2e4f7"  # pragma: allowlist secret - Alembic revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("flow")}
    if "anonymous_access_revoked" not in columns:
        op.add_column(
            "flow", sa.Column("anonymous_access_revoked", sa.Boolean(), nullable=True, server_default=sa.false())
        )
    if "revoked_public_share_id" not in columns:
        op.add_column("flow", sa.Column("revoked_public_share_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("flow")}
    with op.batch_alter_table("flow") as batch_op:
        if "anonymous_access_revoked" in columns:
            batch_op.drop_column("anonymous_access_revoked")
        if "revoked_public_share_id" in columns:
            batch_op.drop_column("revoked_public_share_id")
