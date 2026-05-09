"""fix_memory_base_fk_names

Ensures FK constraints on memory-base tables use explicit names that match
the Alembic naming convention (fk_<table>_<col>_<ref_table>).

Previous installs created these constraints via inline sa.ForeignKey() without
an explicit name, so PostgreSQL auto-assigned names (e.g.
message_ingestion_record_message_id_fkey). Alembic's autogenerate then detects
a mismatch because the naming convention expects
fk_message_ingestion_record_message_id_message, causing startup to fail.

Phase: EXPAND

Revision ID: mb01fix_memory_base_fk_names
Revises: mb00a1b2c3d4
Create Date: 2026-05-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "mb01fix_memory_base_fk_names"  # pragma: allowlist secret
down_revision: str | None = "mb00a1b2c3d4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_fk_for_column(conn, table_name: str, column_name: str) -> dict | None:
    """Return the FK entry for a given column, or None if not found."""
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk["constrained_columns"]:
            return fk
    return None


def _ensure_fk(
    conn,
    table_name: str,
    column_name: str,
    ref_table: str,
    ref_col: str,
    correct_name: str,
    ondelete: str,
) -> None:
    """Drop any existing FK on column_name and (re)create it with correct_name."""
    fk = _get_fk_for_column(conn, table_name, column_name)
    if fk is not None and fk["name"] == correct_name:
        return  # already correct — nothing to do

    with op.batch_alter_table(table_name, schema=None) as batch_op:
        if fk is not None:
            batch_op.drop_constraint(fk["name"], type_="foreignkey")
        batch_op.create_foreign_key(correct_name, ref_table, [column_name], [ref_col], ondelete=ondelete)


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------ #
    #  message_ingestion_record                                            #
    # ------------------------------------------------------------------ #
    if migration.table_exists("message_ingestion_record", conn):
        _ensure_fk(
            conn,
            "message_ingestion_record",
            "message_id",
            "message",
            "id",
            "fk_message_ingestion_record_message_id_message",
            "CASCADE",
        )
        _ensure_fk(
            conn,
            "message_ingestion_record",
            "memory_base_id",
            "memory_base",
            "id",
            "fk_message_ingestion_record_memory_base_id_memory_base",
            "CASCADE",
        )
        _ensure_fk(
            conn,
            "message_ingestion_record",
            "job_id",
            "job",
            "job_id",
            "fk_message_ingestion_record_job_id_job",
            "SET NULL",
        )

    # ------------------------------------------------------------------ #
    #  memory_base_session                                                 #
    # ------------------------------------------------------------------ #
    if migration.table_exists("memory_base_session", conn):
        _ensure_fk(
            conn,
            "memory_base_session",
            "memory_base_id",
            "memory_base",
            "id",
            "fk_memory_base_session_memory_base_id_memory_base",
            "CASCADE",
        )

    # ------------------------------------------------------------------ #
    #  memory_base_workflow_run                                            #
    # ------------------------------------------------------------------ #
    if migration.table_exists("memory_base_workflow_run", conn):
        _ensure_fk(
            conn,
            "memory_base_workflow_run",
            "memory_base_id",
            "memory_base",
            "id",
            "fk_memory_base_workflow_run_memory_base_id_memory_base",
            "CASCADE",
        )
        _ensure_fk(
            conn,
            "memory_base_workflow_run",
            "workflow_job_id",
            "job",
            "job_id",
            "fk_memory_base_workflow_run_workflow_job_id_job",
            "SET NULL",
        )
        _ensure_fk(
            conn,
            "memory_base_workflow_run",
            "ingestion_job_id",
            "job",
            "job_id",
            "fk_memory_base_workflow_run_ingestion_job_id_job",
            "SET NULL",
        )


def downgrade() -> None:
    # FK constraint renames are not reversed — the named constraints are correct
    # and any prior names were auto-generated artefacts with no stable identity.
    pass
