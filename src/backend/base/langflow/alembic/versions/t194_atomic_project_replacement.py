"""Add durable project replacement receipts and shared flow write guard.

Revision ID: f194a1b2c3d4
Revises: e6f9a2b4c8d1
Create Date: 2026-09-21

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "f194a1b2c3d4"  # pragma: allowlist secret -- migration revision identifier
down_revision: str | None = "e6f9a2b4c8d1"  # pragma: allowlist secret -- migration revision identifier
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FLOW_LOCK_FUNCTION = "langflow_lock_project_for_flow_mutation"
_FLOW_LOCK_TRIGGER = "trg_flow_lock_project_for_mutation"


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("project_replacement_operation", conn):
        op.create_table(
            "project_replacement_operation",
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("operation_id", sa.Uuid(), nullable=False),
            sa.Column("request_digest", sa.String(length=64), nullable=False),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("project_user_id", sa.Uuid(), nullable=True),
            sa.Column("workspace_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("project_id", "operation_id", name="pk_project_replacement_operation"),
        )
    else:
        expected_columns = {
            "project_id",
            "operation_id",
            "request_digest",
            "result",
            "project_user_id",
            "workspace_id",
            "created_at",
        }
        missing_columns = {
            column
            for column in expected_columns
            if not migration.column_exists("project_replacement_operation", column, conn)
        }
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            message = f"Existing 'project_replacement_operation' table is missing columns: {missing}"
            raise RuntimeError(message)

    if conn.dialect.name == "postgresql":
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {_FLOW_LOCK_TRIGGER} ON flow"))
        op.execute(
            sa.text(
                f"""
                CREATE OR REPLACE FUNCTION {_FLOW_LOCK_FUNCTION}()
                RETURNS trigger AS $$
                DECLARE
                    project_to_lock uuid;
                BEGIN
                    IF TG_OP = 'INSERT' THEN
                        PERFORM 1 FROM folder WHERE id = NEW.folder_id FOR UPDATE;
                    ELSIF TG_OP = 'DELETE' THEN
                        PERFORM 1 FROM folder WHERE id = OLD.folder_id FOR UPDATE;
                    ELSE
                        FOR project_to_lock IN
                            SELECT DISTINCT project_id
                            FROM unnest(ARRAY[OLD.folder_id, NEW.folder_id]) AS projects(project_id)
                            WHERE project_id IS NOT NULL
                            ORDER BY project_id
                        LOOP
                            PERFORM 1 FROM folder WHERE id = project_to_lock FOR UPDATE;
                        END LOOP;
                    END IF;

                    IF TG_OP = 'DELETE' THEN
                        RETURN OLD;
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
                """  # noqa: S608 -- SQL identifiers above are fixed module constants.
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER {_FLOW_LOCK_TRIGGER}
                BEFORE INSERT OR UPDATE OR DELETE ON flow
                FOR EACH ROW EXECUTE FUNCTION {_FLOW_LOCK_FUNCTION}()
                """
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {_FLOW_LOCK_TRIGGER} ON flow"))
        op.execute(sa.text(f"DROP FUNCTION IF EXISTS {_FLOW_LOCK_FUNCTION}()"))
    op.drop_table("project_replacement_operation")
