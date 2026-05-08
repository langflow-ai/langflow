"""rename deployment name to display_name

Revision ID: b7c4d8e9f012
Revises: mb00a1b2c3d4
Create Date: 2026-05-08 00:00:00.000000

Phase: EXPAND + CONTRACT

Renames the Langflow-owned deployment label column from ``name`` to
``display_name`` and removes the provider-scoped uniqueness constraint on
that label. ``resource_key`` remains the provider-scoped deployment identity.

This is intentionally an atomic expand/contract migration, matching the
deployment-table migration style used on this branch.
"""

from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "b7c4d8e9f012"  # pragma: allowlist secret
down_revision: str | None = "mb00a1b2c3d4"  # pragma: allowlist secret
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


def _dedupe_labels_for_unique_name(conn, column_name: str) -> None:
    """Suffix duplicate labels so downgrade can restore the old unique name constraint."""
    rows = (
        conn.execute(
            sa.text(
                f"""
                SELECT id, deployment_provider_account_id, {column_name} AS label
                FROM deployment
                ORDER BY deployment_provider_account_id, {column_name}, id
                """  # noqa: S608 - column_name is selected from migration constants only.
            )
        )
        .mappings()
        .all()
    )
    used_by_provider: dict[str, set[str]] = defaultdict(set)
    updates: list[dict[str, str]] = []

    for row in rows:
        provider_id = str(row["deployment_provider_account_id"])
        deployment_id = str(row["id"])
        label = str(row["label"] or "")
        used_labels = used_by_provider[provider_id]

        if label not in used_labels:
            used_labels.add(label)
            continue

        candidate = f"{label} ({deployment_id})"
        counter = 2
        while candidate in used_labels:
            candidate = f"{label} ({deployment_id}-{counter})"
            counter += 1

        used_labels.add(candidate)
        updates.append({"id": deployment_id, "label": candidate})

    if not updates:
        return

    conn.execute(
        sa.text(
            f"""
            UPDATE deployment
            SET {column_name} = :label
            WHERE id = :id
            """  # noqa: S608 - column_name is selected from migration constants only.
        ),
        updates,
    )


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
                nullable=False,
            )
        elif old_column_exists and display_name_exists:
            batch_op.drop_column(OLD_NAME_COLUMN)


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(DEPLOYMENT_TABLE, conn):
        return

    old_column_exists = migration.column_exists(DEPLOYMENT_TABLE, OLD_NAME_COLUMN, conn)
    display_name_exists = migration.column_exists(DEPLOYMENT_TABLE, DISPLAY_NAME_COLUMN, conn)

    if display_name_exists and old_column_exists:
        conn.execute(
            sa.text(
                """
                UPDATE deployment
                SET name = display_name
                WHERE name IS NULL AND display_name IS NOT NULL
                """
            )
        )
        _dedupe_labels_for_unique_name(conn, OLD_NAME_COLUMN)
    elif display_name_exists:
        _dedupe_labels_for_unique_name(conn, DISPLAY_NAME_COLUMN)

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
        if (old_column_exists or display_name_exists) and not migration.constraint_exists(
            DEPLOYMENT_TABLE, NAME_UNIQUE_CONSTRAINT, conn
        ):
            batch_op.create_unique_constraint(
                NAME_UNIQUE_CONSTRAINT,
                ["deployment_provider_account_id", OLD_NAME_COLUMN],
            )

    if not _index_exists(conn, DEPLOYMENT_TABLE, NAME_INDEX):
        op.create_index(NAME_INDEX, DEPLOYMENT_TABLE, [OLD_NAME_COLUMN])
