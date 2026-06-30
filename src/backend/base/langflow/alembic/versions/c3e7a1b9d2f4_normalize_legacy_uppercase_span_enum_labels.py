"""Normalize legacy uppercase spanstatus/spantype enum labels to lowercase

Revision ID: c3e7a1b9d2f4
Revises: 4f0d2c9a8b7e
Create Date: 2026-06-30

Phase: MIGRATE

Repairs PostgreSQL databases whose ``spanstatus`` / ``spantype`` enum *types*
were materialized with UPPERCASE labels.

Background
----------
``SpanStatus`` / ``SpanType`` are ``str, Enum`` members whose *name* is uppercase
but whose *value* is lowercase (e.g. ``OK = "ok"``). Two paths can create the
backing PostgreSQL enum type, and historically they disagreed on the labels:

* Alembic migration ``3478f0bd6ccb`` creates the type from literal strings, so its
  labels are lowercase: ``spanstatus = {'unset', 'ok', 'error'}``.
* ``SQLModel.metadata.create_all`` on builds *before* #12820 used a bare
  ``sa.Enum(SpanStatus)`` (no ``values_callable``), so SQLAlchemy emitted the enum
  *names* and the labels came out UPPERCASE: ``{'UNSET', 'OK', 'ERROR'}``.

Since #12820 the application binds the lowercase *values*
(``values_callable=_enum_values``). On a database whose type carries uppercase
labels, every span/trace insert is therefore rejected by PostgreSQL at the type
level with ``invalid input value for enum spanstatus: "ok"``. The read-side
``_LegacyCaseEnum`` decorator (#13000 / #13346) only normalises legacy strings on
*read* — it cannot widen the type's label set, so writes still fail. This
migration closes that gap.

``ALTER TYPE ... RENAME VALUE`` is a metadata-only operation: it relabels the enum
in place (no table rewrite, no lock on the data, transaction-safe), and existing
rows follow automatically because PostgreSQL stores enum values by ``pg_enum`` oid
rather than by text. Each rename is guarded by a ``pg_enum`` lookup so the
migration is idempotent and a no-op on already-correct (lowercase) databases.

``spankind`` is intentionally excluded: its members have ``name == value`` (e.g.
``INTERNAL = "INTERNAL"``), so its labels are identical in both creation paths and
need no repair.

The downgrade is a deliberate no-op — see ``downgrade`` for the rationale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c3e7a1b9d2f4"  # pragma: allowlist secret
down_revision: str | None = "4f0d2c9a8b7e"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen snapshot of the legacy-uppercase -> canonical-lowercase label map for each
# affected enum type. Kept as literals (not imported from the live enum classes) so
# this migration remains a stable point-in-time record even if the enums evolve.
# Mirrors SpanStatus / SpanType in
# langflow.services.database.models.traces.model.
_ENUM_RELABELS: dict[str, dict[str, str]] = {
    "spanstatus": {
        "UNSET": "unset",
        "OK": "ok",
        "ERROR": "error",
    },
    "spantype": {
        "CHAIN": "chain",
        "LLM": "llm",
        "TOOL": "tool",
        "RETRIEVER": "retriever",
        "EMBEDDING": "embedding",
        "PARSER": "parser",
        "AGENT": "agent",
    },
}


def _existing_labels(conn, type_name: str) -> set[str]:
    """Return the current label set of a PostgreSQL enum type, or empty if it doesn't exist."""
    rows = conn.execute(
        sa.text("SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = :type_name"),
        {"type_name": type_name},
    )
    return {row[0] for row in rows}


def _rename_labels(conn, relabels: dict[str, dict[str, str]]) -> None:
    """Apply guarded ``ALTER TYPE ... RENAME VALUE`` for each ``{type: {old: new}}`` mapping.

    A rename runs only when the *old* label is present and the *new* label is absent,
    making the operation idempotent and safe to re-run.
    """
    for type_name, mapping in relabels.items():
        labels = _existing_labels(conn, type_name)
        if not labels:
            continue
        for old_label, new_label in mapping.items():
            if old_label in labels and new_label not in labels:
                # Identifiers/labels are hardcoded constants above (never user input),
                # and enum labels cannot be passed as bind parameters in DDL.
                stmt = f"ALTER TYPE {type_name} RENAME VALUE '{old_label}' TO '{new_label}'"
                conn.execute(sa.text(stmt))
                labels.discard(old_label)
                labels.add(new_label)


def upgrade() -> None:
    conn = op.get_bind()
    # Named enum types only exist on PostgreSQL; SQLite (and others) store these
    # columns as plain strings, so there is nothing to relabel.
    if conn.dialect.name != "postgresql":
        return
    _rename_labels(conn, _ENUM_RELABELS)


def downgrade() -> None:
    # Intentional no-op. This is a one-way convergence/repair: lowercase labels are
    # the only set the current application code (and migration 3478f0bd6ccb) accepts.
    # Re-introducing the legacy uppercase labels would deliberately recreate the
    # broken state this migration exists to fix and could corrupt databases that were
    # always correct, so the downgrade leaves the labels untouched.
    pass
