"""job flow_id nullable and deployment_copy job type.

Adds JobType.DEPLOYMENT_COPY to job_type_enum, and lets that one type leave job.flow_id
empty: a deployment copy belongs to a deployment, which spans every flow in a project.

Revision ID: c14fe0b7508c
Revises: 1d8d193028c8
Create Date: 2026-10-21 15:13:50.460965

Phase: EXPAND
Safe to rollback: YES, except that deployment_copy rows are deleted, since NOT NULL cannot
    come back while one is there. They record a copy's progress and redeploying recreates them.
Services compatible: All versions. Older services always write a flow_id and never write the
    new type, so neither the relaxed column nor the check constraint refuses anything they send.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c14fe0b7508c"  # pragma: allowlist secret
down_revision: str | None = "1d8d193028c8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Only Postgres needs DDL for the new ``JobType`` member. 169b35510b37 created
# ``job_type_enum`` as a named type, which is native there, but on SQLite it is a plain
# VARCHAR: SQLAlchemy has not emitted the CHECK constraint by default since 1.4, so the
# member list is enforced in Python only and nothing in the schema mentions it.
_OLD_TYPES = ("workflow", "ingestion", "evaluation")
_NEW_TYPES = (*_OLD_TYPES, "deployment_copy")


def _job_type(*members: str) -> sa.Enum:
    """``job_type_enum`` with the given members, rendered as the model renders it.

    On SQLite this is a VARCHAR as wide as the longest member, so the column has to be widened
    for ``deployment_copy`` at 15 characters: the old one is VARCHAR(10), sized for
    ``evaluation``. SQLite does not enforce the width, so the value would store either way, but
    the declared type would stop matching the model and the phantom-migration check says so.
    """
    return sa.Enum(*members, name="job_type_enum")


# Relaxing NOT NULL would otherwise let a workflow job be inserted with no flow at all. The
# column has to accept a null for a deployment copy, so the requirement moves to a constraint
# that knows which type is allowed to leave it empty. ``type`` is itself nullable, and a CHECK
# is satisfied when its expression is NULL rather than FALSE, so the null is excluded
# explicitly: "type = 'deployment_copy'" alone would accept a row with neither a type nor a flow.
#
# Passed through ``op.f()`` at every call site. env.py installs
# ``ck_%(table_name)s_%(constraint_name)s`` on the metadata, which renders an already-prefixed
# name as ``ck_job_ck_job_...``; op.f() marks it final (GH #15006).
_FLOW_REQUIRED = "ck_job_flow_id_required_unless_deployment_copy"
_FLOW_REQUIRED_SQL = "flow_id IS NOT NULL OR (type IS NOT NULL AND type = 'deployment_copy')"


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # IF NOT EXISTS so a re-run is a no-op. Transaction-safe since PG12 as long as
        # nothing in the same transaction writes the new value, which nothing here does.
        op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'deployment_copy'")
        op.alter_column("job", "flow_id", existing_type=sa.Uuid(), nullable=True)
        op.create_check_constraint(op.f(_FLOW_REQUIRED), "job", _FLOW_REQUIRED_SQL)
        return

    # SQLite cannot relax NOT NULL in place, so the table is rebuilt. Both changes go in one
    # batch: a second batch would rebuild it again for no reason.
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.alter_column("flow_id", existing_type=sa.Uuid(), nullable=True)
        batch_op.alter_column("type", existing_type=_job_type(*_OLD_TYPES), type_=_job_type(*_NEW_TYPES))
        batch_op.create_check_constraint(op.f(_FLOW_REQUIRED), _FLOW_REQUIRED_SQL)


def downgrade() -> None:
    conn = op.get_bind()
    # A deployment-copy row is the only thing that can hold a null flow_id, and NOT NULL
    # cannot be restored while one exists. These rows record a copy's progress and are
    # recreated by redeploying, so dropping them is recoverable; nothing else is touched.
    op.execute(sa.text("DELETE FROM job WHERE type = 'deployment_copy'"))

    if conn.dialect.name == "postgresql":
        # Dropped before the type is rebuilt: the constraint names the enum value being removed.
        op.drop_constraint(op.f(_FLOW_REQUIRED), "job", type_="check")
        # Postgres cannot drop a member, so the type is rebuilt without it.
        op.execute("ALTER TYPE job_type_enum RENAME TO job_type_enum_old")
        sa.Enum(*_OLD_TYPES, name="job_type_enum").create(conn, checkfirst=False)
        op.execute("ALTER TABLE job ALTER COLUMN type TYPE job_type_enum USING type::text::job_type_enum")
        op.execute("DROP TYPE job_type_enum_old")
        op.alter_column("job", "flow_id", existing_type=sa.Uuid(), nullable=False)
        return

    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.drop_constraint(op.f(_FLOW_REQUIRED), type_="check")
        batch_op.alter_column("type", existing_type=_job_type(*_NEW_TYPES), type_=_job_type(*_OLD_TYPES))
        batch_op.alter_column("flow_id", existing_type=sa.Uuid(), nullable=False)
