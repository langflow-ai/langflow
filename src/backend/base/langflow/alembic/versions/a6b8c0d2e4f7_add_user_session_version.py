"""Track native sessions across password changes.

Revision ID: a6b8c0d2e4f7
Revises: f5a7b9c2d4e6
Phase: EXPAND
Safe to rollback: YES (password changes no longer revoke native sessions)
Services compatible: Older versions ignore the additional column.
"""

import sqlalchemy as sa
from alembic import op

revision = "a6b8c0d2e4f7"  # pragma: allowlist secret - Alembic revision
down_revision = "f5a7b9c2d4e6"  # pragma: allowlist secret - Alembic revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("user")}
    if "session_version" not in columns:
        op.add_column("user", sa.Column("session_version", sa.String(64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("user")}
    if "session_version" in columns:
        # SQLite batch reflection omits expression indexes.
        username_index = None
        if bind.dialect.name == "sqlite":
            username_index = bind.execute(
                sa.text("SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'ix_user_username_lower'")
            ).scalar_one_or_none()
        with op.batch_alter_table("user") as batch_op:
            batch_op.drop_column("session_version")
        if username_index:
            op.create_index("ix_user_username_lower", "user", [sa.text("lower(username)")], unique=True)
