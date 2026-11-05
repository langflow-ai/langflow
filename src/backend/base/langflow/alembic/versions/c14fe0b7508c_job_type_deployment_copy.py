"""deployment_copy job type.

Adds JobType.DEPLOYMENT_COPY to job_type_enum, for the job that copies a deployment's
documents into the plane that serves it. One such job per flow, so ``flow_id`` stays required
for every job type.

Revision ID: c14fe0b7508c
Revises: c6a81d3e9502
Create Date: 2026-10-21 15:13:50.460965

Phase: EXPAND
Safe to rollback: YES, except that deployment_copy rows are deleted, since the old type has no
    member to hold them. They record a copy's progress and redeploying recreates them.
Services compatible: New versions only, once anything creates deployment_copy jobs. Older
    services never write the new type, but they cannot load a row that holds it, and their
    orphan sweep loads every in-progress job. Roll this out to every replica before the
    deploy copy that creates these jobs (IBM-Langflow) is turned on.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c14fe0b7508c"  # pragma: allowlist secret
down_revision: str | None = "c6a81d3e9502"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_TYPES = ("workflow", "ingestion", "evaluation")
_NEW_TYPES = (*_OLD_TYPES, "deployment_copy")


def _job_type(*members: str) -> sa.Enum:
    """``job_type_enum`` with the given members, rendered as the model renders it.

    169b35510b37 created it as a named type, native on Postgres. On SQLite it is a VARCHAR as
    wide as the longest member, with no CHECK (SQLAlchemy stopped emitting one in 1.4), so the
    column has to be widened for ``deployment_copy`` at 15 characters: the old one is
    VARCHAR(10), sized for ``evaluation``. SQLite does not enforce the width, so the value would
    store either way, but the declared type would stop matching the model and the
    phantom-migration check says so.
    """
    return sa.Enum(*members, name="job_type_enum")


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # Committed on its own, as c7412b389256 does: env.py runs a whole ``upgrade head`` in
        # one transaction, and Postgres refuses any later use of a value added in the same
        # transaction. IF NOT EXISTS so a re-run is a no-op.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'deployment_copy'")
        return

    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.alter_column("type", existing_type=_job_type(*_OLD_TYPES), type_=_job_type(*_NEW_TYPES))


def downgrade() -> None:
    conn = op.get_bind()
    # The old type has no member for these rows. They record a copy's progress and are
    # recreated by redeploying, so dropping them is recoverable; nothing else is touched.
    op.execute(sa.text("DELETE FROM job WHERE type = 'deployment_copy'"))

    if conn.dialect.name == "postgresql":
        # Postgres cannot drop a member, so the type is rebuilt without it.
        op.execute("ALTER TYPE job_type_enum RENAME TO job_type_enum_old")
        sa.Enum(*_OLD_TYPES, name="job_type_enum").create(conn, checkfirst=False)
        op.execute("ALTER TABLE job ALTER COLUMN type TYPE job_type_enum USING type::text::job_type_enum")
        op.execute("DROP TYPE job_type_enum_old")
        return

    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.alter_column("type", existing_type=_job_type(*_NEW_TYPES), type_=_job_type(*_OLD_TYPES))
