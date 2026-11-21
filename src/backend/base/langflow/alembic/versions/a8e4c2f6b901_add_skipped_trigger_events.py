"""Retain filtered trigger deliveries without dispatching a flow.

Revision ID: a8e4c2f6b901
Revises: f4b8c1d2e3a6
Create Date: 2026-11-08

Phase: EXPAND
Safe to rollback: YES
Services compatible: Previous workers do not claim terminal skipped events.

Downgrade retains each filtered event's payload and reason while mapping its
terminal state to completed, which the previous API can deserialize.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8e4c2f6b901"  # pragma: allowlist secret
down_revision: str | None = "f4b8c1d2e3a6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "trigger_event"
_CONSTRAINT = "ck_trigger_event_state"
_OLD_STATES = "'pending', 'claimed', 'dispatched', 'completed', 'failed', 'dead'"


def _replace_state_check(*, skipped: bool) -> None:
    checks = sa.inspect(op.get_bind()).get_check_constraints(_TABLE)
    existing = next((check for check in checks if check.get("name") == _CONSTRAINT), None)
    if existing is not None and ("'skipped'" in (existing.get("sqltext") or "")) == skipped:
        return
    states = f"{_OLD_STATES}, 'skipped'" if skipped else _OLD_STATES
    with op.batch_alter_table(_TABLE) as batch:
        if existing is not None:
            batch.drop_constraint(batch.f(_CONSTRAINT), type_="check")
        batch.create_check_constraint(batch.f(_CONSTRAINT), f"state IN ({states})")


def upgrade() -> None:
    _replace_state_check(skipped=True)


def downgrade() -> None:
    op.execute(sa.text("UPDATE trigger_event SET state = 'completed' WHERE state = 'skipped'"))
    _replace_state_check(skipped=False)
