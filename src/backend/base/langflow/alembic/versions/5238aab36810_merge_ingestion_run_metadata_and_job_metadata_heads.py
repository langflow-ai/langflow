"""Merge ingestion_run.user_metadata and job.job_metadata heads.

Revision ID: 5238aab36810
Revises: 16a290ab1332, da7f6b9b638a
Create Date: 2026-04-30 20:30:00.000000

Phase: EXPAND
Safe to rollback: YES — pure graph node, no DDL. The validator only
    recognises EXPAND / MIGRATE / CONTRACT, and a no-op merge fits the
    additive (EXPAND) bucket since it never drops or rewrites data.

After the kb_id-on-ingestion_run change (``e728126476a8``) was rebased
onto ``72df732be86b`` so the ``ingestion_run`` chain is linear, the
graph still had two independent tips:

* ``16a290ab1332`` — adds ``user_metadata`` JSON to ``ingestion_run``.
* ``da7f6b9b638a`` — adds ``job_metadata`` JSON to ``job``.

Neither references the other, so ``alembic upgrade head`` would
``CommandError: Multiple head revisions are present``. This empty
migration unifies them so future migrations can chain off a single
head without picking sides between the KB ingestion-run and the
job-metadata work.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "5238aab36810"  # pragma: allowlist secret
down_revision: tuple[str, ...] | str | None = (
    "16a290ab1332",  # pragma: allowlist secret
    "da7f6b9b638a",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op merge — combines two parallel migration heads."""


def downgrade() -> None:
    """No-op merge — combines two parallel migration heads."""
