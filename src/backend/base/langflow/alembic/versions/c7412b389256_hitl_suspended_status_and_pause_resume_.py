"""hitl suspended status and pause resume signals.

Adds JobStatus.SUSPENDED to job_status_enum and SignalType.PAUSE/RESUME to
execution_signal_type_enum so a run can suspend for human input and resume.

Revision ID: c7412b389256
Revises: 8ce44e4858c6
Create Date: 2026-06-09 16:19:43.372632

Phase: EXPAND
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c7412b389256"  # pragma: allowlist secret
down_revision: str | None = "8ce44e4858c6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # ALTER TYPE ... ADD VALUE cannot run inside the migration env's transaction.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE job_status_enum ADD VALUE IF NOT EXISTS 'suspended'")
            op.execute("ALTER TYPE execution_signal_type_enum ADD VALUE IF NOT EXISTS 'pause'")
            op.execute("ALTER TYPE execution_signal_type_enum ADD VALUE IF NOT EXISTS 'resume'")
    else:
        # SQLite stores enums as VARCHAR and the base migration created signal_type via plain
        # sa.Enum (create_constraint defaults to False in SQLAlchemy 2.x), so there is no CHECK
        # constraint to widen — 'pause'/'resume' are accepted without DDL. A table rebuild here is
        # dead DDL (and job_status_enum, which also gains SUSPENDED, isn't rebuilt either).
        pass


def downgrade() -> None:
    # EXPAND: enum ADD VALUE is irreversible without rebuilding the type, so a no-op.
    pass
