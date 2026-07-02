"""lothal: add the LF-project → PM-project link table (Story P.4)

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f0a1b2
Create Date: 2026-07-02 00:00:00.000000

Phase: EXPAND

The plan stage bridges to the standalone Lothal PM service, which issues its own
project ids and has no lookup-by-external-key — so the Langflow-id → PM-id
mapping must be persisted on the langflow side. ``lothal_pm_project_link`` holds
one row per Langflow project, written on first use of the plan stage; the
primary key on ``lf_project_id`` is what makes concurrent first use race-safe
(``_ensure_pm_project`` in ``api/v1/lothal.py``). FK to ``lothal_project`` with
``ondelete=CASCADE``, matching the other lothal child tables (f2e57d2327a2).

Every statement is guarded (table existence) so it applies cleanly on both
SQLite (the test DB) and Postgres, on a fresh as well as an existing database,
and re-runs as a no-op.

Downgrade drops the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("lothal_project", conn):
        return

    if not migration.table_exists("lothal_pm_project_link", conn):
        op.create_table(
            "lothal_pm_project_link",
            sa.Column("lf_project_id", sa.Uuid(), nullable=False),
            sa.Column("pm_project_id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["lf_project_id"],
                ["lothal_project.id"],
                name="fk_lothal_pm_project_link_lf_project_id_lothal_project",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("lf_project_id"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists("lothal_pm_project_link", conn):
        op.drop_table("lothal_pm_project_link")
