"""hitl suspended status and pause resume signals.

Adds JobStatus.SUSPENDED to job_status_enum and SignalType.PAUSE/RESUME to
execution_signal_type_enum so a run can suspend for human input and resume.

Revision ID: c7412b389256
Revises: 8ce44e4858c6
Create Date: 2026-06-09 16:19:43.372632

Phase: EXPAND
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7412b389256"  # pragma: allowlist secret
down_revision: str | None = "8ce44e4858c6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_SIGNAL_ENUM = sa.Enum("stop", name="execution_signal_type_enum")
_NEW_SIGNAL_ENUM = sa.Enum("stop", "pause", "resume", name="execution_signal_type_enum")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # ALTER TYPE ... ADD VALUE cannot run inside the migration env's transaction.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE job_status_enum ADD VALUE IF NOT EXISTS 'suspended'")
            op.execute("ALTER TYPE execution_signal_type_enum ADD VALUE IF NOT EXISTS 'pause'")
            op.execute("ALTER TYPE execution_signal_type_enum ADD VALUE IF NOT EXISTS 'resume'")
    else:
        # SQLite rebuilds the column so its reflected VARCHAR length matches the model's widened
        # Enum(stop, pause, resume); without it the model/migration consistency check (autogenerate)
        # reports a phantom VARCHAR(4) -> Enum diff. job_status_enum needs no rebuild here.
        with op.batch_alter_table("execution_signals", recreate="always") as batch_op:
            batch_op.alter_column(
                "signal_type",
                existing_type=_OLD_SIGNAL_ENUM,
                type_=_NEW_SIGNAL_ENUM,
                existing_nullable=False,
            )


def downgrade() -> None:
    # EXPAND: enum ADD VALUE is irreversible without rebuilding the type, so a no-op.
    pass
