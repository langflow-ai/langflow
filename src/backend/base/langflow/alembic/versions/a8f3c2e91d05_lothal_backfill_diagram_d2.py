"""lothal: backfill diagram_d2 from legacy diagram_json (D.13)

Revision ID: a8f3c2e91d05
Revises: 66bb47eb00f6
Create Date: 2026-06-18 00:00:00.000000

Phase: EXPAND

Epic D pivoted the diagram artifact from an xyflow graph (``diagram_json``) to D2
source (``diagram_d2``).  Migration 66bb47eb00f6 added the ``diagram_d2`` column.
Projects created before the D.2 landing have ``diagram_json`` populated but
``diagram_d2`` NULL — those projects cannot be rendered once the xyflow canvas is
removed in D.15.

This migration performs a one-time data backfill: for every ``lothal_project`` row
where ``diagram_d2 IS NULL AND diagram_json IS NOT NULL``, the stored xyflow graph
is converted to D2 source via ``xyflow_graph_to_d2`` and written into
``diagram_d2``.

Why convert rather than dual-read?
-----------------------------------
Keeping a dual-read path would require the frontend to keep the xyflow render
code alive indefinitely — but the xyflow canvas is being deleted in D.15, making
that impossible.  Converting the stored data once is the only path that keeps
every project renderable.  The original ``diagram_json`` column is intentionally
left in place (no data loss); dropping it is a later, separate migration.

Idempotency and safety
-----------------------
The migration is a no-op when:
- the ``lothal_project`` table does not yet exist;
- either column (``diagram_json`` or ``diagram_d2``) is absent;
- no rows satisfy the backfill condition (already converted, or no legacy data).

A row that fails conversion (invalid JSON, no nodes, …) is skipped with a warning
logged to stderr rather than aborting the whole migration — one corrupt legacy row
must not block the application from starting.

Downgrade
----------
The downgrade is intentionally a no-op.  Reverting the *structural* migration
(dropping ``diagram_d2``) is the job of the 66bb47eb00f6 downgrade.  Reversing a
data backfill would mean blanking ``diagram_d2`` for rows this migration wrote —
but we can't distinguish rows written here from rows written by the generation
engine, so any attempt to reverse would risk destroying real user data.  The safe
and honest choice is to leave the data in place on downgrade.
"""

import logging
import os
import shutil
import subprocess
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

logger = logging.getLogger("alembic.runtime.migration")


def _compiles(d2_source: str) -> bool | None:
    """Compile-check converted D2 with the `d2` binary: True/False, or None if unavailable.

    Mirrors how every other D2 writer (generation/refinement via d2_gate) gates
    its output, so the backfill can't silently persist a diagram that doesn't
    render. A missing binary is an environment fault, not a verdict on the data
    (returns None → the caller stores best-effort, same as the d2_gate policy);
    a non-zero exit means the converted D2 is broken and the row should be skipped.
    A timeout is treated as a definite failure (False, not None): a compile that
    hangs on this input is not a diagram we want to persist, and it would also
    stall the whole migration if retried — so skip the row.
    """
    d2_bin = shutil.which("d2")
    if not d2_bin:
        return None
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, input piped via stdin
            [d2_bin, "-", os.devnull],
            input=d2_source.encode(),
            capture_output=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # A hang is a failed validation, not an unavailable validator — return
        # False so the caller's `is False` check skips the row (returning None
        # here would store the unvalidated diagram).
        logger.warning("[D.13 migration] d2 compile-check timed out; treating as a compile failure.")
        return False
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("[D.13 migration] d2 compile-check unavailable (%s); storing without validation.", exc)
        return None
    return proc.returncode == 0

# revision identifiers, used by Alembic.
revision: str = "a8f3c2e91d05"
down_revision: str | None = "66bb47eb00f6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Guard: table may not exist in a fresh DB that bypassed these older migrations.
    if not migration.table_exists("lothal_project", conn):
        return

    # Guard: both columns must exist before we can read/write them.
    if not migration.column_exists("lothal_project", "diagram_json", conn):
        return
    if not migration.column_exists("lothal_project", "diagram_d2", conn):
        return

    # Import the converter here (inside the function) so that Alembic can import
    # this migration file without executing application code at module load time.
    # This matches Alembic's expected pattern and keeps the migration self-contained.
    from langflow.lothal.xyflow_to_d2 import xyflow_graph_to_d2

    # Reflect only the columns we need to avoid a full ORM round-trip.
    lothal_project = sa.table(
        "lothal_project",
        sa.column("id", sa.Text()),
        sa.column("diagram_json", sa.Text()),
        sa.column("diagram_d2", sa.Text()),
    )

    rows = conn.execute(
        sa.select(lothal_project.c.id, lothal_project.c.diagram_json).where(
            lothal_project.c.diagram_d2.is_(None),
            lothal_project.c.diagram_json.isnot(None),
        )
    ).fetchall()

    converted = 0
    skipped = 0
    for row in rows:
        project_id, diagram_json = row.id, row.diagram_json
        try:
            d2 = xyflow_graph_to_d2(diagram_json)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[D.13 migration] Skipping project %s: could not convert diagram_json — %s", project_id, exc)
            skipped += 1
            continue

        # Compile-check the conversion before persisting (the converter sanitises
        # ids/labels, but legacy data is unbounded). A definite failure → skip the
        # row, leaving diagram_d2 NULL so the project shows "no diagram yet" and
        # can be regenerated, rather than being stuck with a non-rendering diagram.
        # `None` (no d2 binary) means we can't judge → store best-effort.
        if _compiles(d2) is False:
            logger.warning("[D.13 migration] Skipping project %s: converted D2 did not compile.", project_id)
            skipped += 1
            continue

        conn.execute(
            sa.update(lothal_project).where(lothal_project.c.id == project_id).values(diagram_d2=d2)
        )
        converted += 1

    if converted or skipped:
        logger.info("[D.13 migration] Backfilled diagram_d2 for %s project(s); skipped %s row(s).", converted, skipped)


def downgrade() -> None:
    # Intentional no-op — see module docstring for the reasoning.
    pass
