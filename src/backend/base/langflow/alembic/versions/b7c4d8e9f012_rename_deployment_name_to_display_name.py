"""rename deployment name to display_name

Revision ID: b7c4d8e9f012
Revises: c35e9db03a66
Create Date: 2026-05-08 00:00:00.000000

Phase: EXPAND + CONTRACT

Renames the Langflow-owned deployment label column from ``name`` to
``display_name`` and removes the provider-scoped uniqueness constraint on
that label. ``resource_key`` remains the provider-scoped deployment identity.

This is intentionally an atomic expand/contract migration, matching the
deployment-table migration style used on this branch.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "b7c4d8e9f012"  # pragma: allowlist secret
down_revision: str | None = "c35e9db03a66"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEPLOYMENT_TABLE = "deployment"
OLD_NAME_COLUMN = "name"
DISPLAY_NAME_COLUMN = "display_name"

NAME_UNIQUE_CONSTRAINT = "uq_deployment_name_in_provider"
NAME_INDEX = "ix_deployment_name"


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(conn)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(DEPLOYMENT_TABLE, conn):
        return

    old_column_exists = migration.column_exists(DEPLOYMENT_TABLE, OLD_NAME_COLUMN, conn)
    display_name_exists = migration.column_exists(DEPLOYMENT_TABLE, DISPLAY_NAME_COLUMN, conn)

    if _index_exists(conn, DEPLOYMENT_TABLE, NAME_INDEX):
        op.drop_index(NAME_INDEX, table_name=DEPLOYMENT_TABLE)

    if old_column_exists and display_name_exists:
        conn.execute(
            sa.text(
                """
                UPDATE deployment
                SET display_name = name
                WHERE display_name IS NULL AND name IS NOT NULL
                """
            )
        )

    with op.batch_alter_table(DEPLOYMENT_TABLE, schema=None) as batch_op:
        if migration.constraint_exists(DEPLOYMENT_TABLE, NAME_UNIQUE_CONSTRAINT, conn):
            batch_op.drop_constraint(NAME_UNIQUE_CONSTRAINT, type_="unique")
        if old_column_exists and not display_name_exists:
            batch_op.alter_column(
                OLD_NAME_COLUMN,
                new_column_name=DISPLAY_NAME_COLUMN,
                existing_type=sa.String(),
                nullable=True,
            )
        elif old_column_exists and display_name_exists:
            batch_op.drop_column(OLD_NAME_COLUMN)

    # Keep display_name nullable on every upgrade path.
    if migration.column_exists(DEPLOYMENT_TABLE, DISPLAY_NAME_COLUMN, conn):
        with op.batch_alter_table(DEPLOYMENT_TABLE, schema=None) as batch_op:
            batch_op.alter_column(
                DISPLAY_NAME_COLUMN,
                existing_type=sa.String(),
                nullable=True,
            )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(DEPLOYMENT_TABLE, conn):
        return

    old_column_exists = migration.column_exists(DEPLOYMENT_TABLE, OLD_NAME_COLUMN, conn)
    display_name_exists = migration.column_exists(DEPLOYMENT_TABLE, DISPLAY_NAME_COLUMN, conn)
    should_restore_name_unique_constraint = old_column_exists or display_name_exists
    id_to_text = "CAST(id AS TEXT)"

    if display_name_exists and old_column_exists:
        # Deterministically suffix every restored name with deployment ID so
        # per-provider uniqueness can be recreated without collision scanning.
        # Use a single UPDATE so partial/intermediate states never expose
        # transient duplicate `name` values.
        conn.execute(
            sa.text(
                f"""
                UPDATE deployment
                SET name = CASE
                    WHEN name IS NOT NULL THEN name || ' (' || {id_to_text} || ')'
                    WHEN display_name IS NOT NULL THEN display_name || ' (' || {id_to_text} || ')'
                    ELSE {id_to_text}
                END
                """  # noqa: S608 - id_to_text is a migration-local constant.
            )
        )
    elif display_name_exists:
        conn.execute(
            sa.text(
                f"""
                UPDATE deployment
                SET display_name = CASE
                    WHEN display_name IS NOT NULL THEN display_name || ' (' || {id_to_text} || ')'
                    ELSE {id_to_text}
                END
                """  # noqa: S608 - id_to_text is a migration-local constant.
            )
        )

    with op.batch_alter_table(DEPLOYMENT_TABLE, schema=None) as batch_op:
        if display_name_exists and not old_column_exists:
            batch_op.alter_column(
                DISPLAY_NAME_COLUMN,
                new_column_name=OLD_NAME_COLUMN,
                existing_type=sa.String(),
                nullable=False,
            )
        elif display_name_exists and old_column_exists:
            batch_op.drop_column(DISPLAY_NAME_COLUMN)

    # Create the constraint after the rename/drop batch has materialized the old column.
    if should_restore_name_unique_constraint and not migration.constraint_exists(
        DEPLOYMENT_TABLE, NAME_UNIQUE_CONSTRAINT, conn
    ):
        with op.batch_alter_table(DEPLOYMENT_TABLE, schema=None) as batch_op:
            batch_op.create_unique_constraint(
                NAME_UNIQUE_CONSTRAINT,
                ["deployment_provider_account_id", OLD_NAME_COLUMN],
            )

    if not _index_exists(conn, DEPLOYMENT_TABLE, NAME_INDEX):
        op.create_index(NAME_INDEX, DEPLOYMENT_TABLE, [OLD_NAME_COLUMN])
