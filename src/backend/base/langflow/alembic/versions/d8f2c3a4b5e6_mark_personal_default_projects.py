"""Mark per-user default projects as personal.

Revision ID: d8f2c3a4b5e6
Revises: f2a7c9e4b681

Phase: EXPAND
Safe to rollback: YES
Services compatible: Versions that do not read folder.is_personal
"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "d8f2c3a4b5e6"  # pragma: allowlist secret
down_revision = "f2a7c9e4b681"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {column["name"] for column in sa.inspect(connection).get_columns("folder")}
    if "is_personal" not in columns:
        with op.batch_alter_table("folder") as batch_op:
            batch_op.add_column(sa.Column("is_personal", sa.Boolean(), nullable=False, server_default=sa.false()))

    indexes = {index["name"] for index in sa.inspect(connection).get_indexes("folder")}
    if "ix_folder_is_personal" not in indexes:
        op.create_index("ix_folder_is_personal", "folder", ["is_personal"])

    # The stock description survives a rename unless the user edits it. Include
    # the configured name used by deployments with a custom default project.
    default_names = {"Starter Project", "My Collection", os.getenv("DEFAULT_FOLDER_NAME", "Starter Project")}
    folder = sa.table(
        "folder",
        sa.column("user_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_personal", sa.Boolean()),
    )
    connection.execute(
        sa.update(folder)
        .where(
            folder.c.user_id.is_not(None),
            sa.or_(
                folder.c.name.in_(default_names),
                folder.c.description == "Manage your own flows. Download and upload projects.",
            ),
        )
        .values(is_personal=True)
    )


def downgrade() -> None:
    connection = op.get_bind()
    indexes = {index["name"] for index in sa.inspect(connection).get_indexes("folder")}
    if "ix_folder_is_personal" in indexes:
        op.drop_index("ix_folder_is_personal", table_name="folder")
    columns = {column["name"] for column in sa.inspect(connection).get_columns("folder")}
    if "is_personal" in columns:
        with op.batch_alter_table("folder") as batch_op:
            batch_op.drop_column("is_personal")
