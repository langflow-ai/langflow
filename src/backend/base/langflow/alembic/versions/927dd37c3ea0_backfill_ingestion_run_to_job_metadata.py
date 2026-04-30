"""Backfill ingestion_run rows into job.job_metadata

Revision ID: 927dd37c3ea0
Revises: da7f6b9b638a
Create Date: 2026-04-30 17:55:00.000000

Phase: MIGRATE
Safe to rollback: Partial — the upgrade is data-only and additive
    (writes ``job.job_metadata``, never deletes), so rolling back the
    table-drop migration that follows restores read paths. The
    backfilled metadata is left in place because (a) it doesn't
    conflict with anything and (b) re-running the upgrade is
    idempotent if needed.
Services compatible: All versions. New code reads from
    ``job.job_metadata``; old code reads from ``ingestion_run`` (still
    present at this point in the chain). The next migration drops the
    legacy table.

For each ``ingestion_run`` row:
* If a ``job`` row with the same ``ingestion_run.job_id`` exists,
  shallow-merge the run's data into ``job.job_metadata``.
* If no ``job`` row exists (orphan ingestion_run — should not occur
  in current code paths but defensively handled), synthesize a
  ``job`` row of type ``INGESTION`` with the run's lifecycle
  timestamps so the read path can find it.

Failures on individual rows are logged and skipped — the migration
must not block on stale data; the worst case is a single ingestion
run not appearing in the history UI.
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "927dd37c3ea0"  # pragma: allowlist secret
down_revision: str | None = "da7f6b9b638a"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Map IngestionRunStatus → JobStatus for synthetic job rows. The
# run-level outcome (PARTIAL/etc.) lives on ``job_metadata.status``;
# ``Job.status`` only carries the lifecycle (in_progress/completed/
# failed/cancelled), so collapse PARTIAL/SUCCEEDED → COMPLETED here.
_RUN_STATUS_TO_JOB_STATUS = {
    "pending": "queued",
    "running": "in_progress",
    "succeeded": "completed",
    "partial": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
}


def _build_metadata_from_run(row) -> dict:
    """Reproduce the same shape ``create_run`` + ``finalize_run`` write."""
    items = row.items
    if items is None:
        items = []
    elif isinstance(items, str):  # JSON column on SQLite occasionally surfaces strings
        import json

        try:
            items = json.loads(items)
        except (TypeError, ValueError):
            items = []
    source_config = row.source_config
    if isinstance(source_config, str):
        import json

        try:
            source_config = json.loads(source_config)
        except (TypeError, ValueError):
            source_config = {}
    elif source_config is None:
        source_config = {}

    return {
        "kind": "kb_ingestion",
        "ingestion_run_id": str(row.id),
        "kb_name": row.kb_name,
        "kb_id": str(row.kb_id) if row.kb_id else None,
        "source_type": row.source_type,
        "source_config": source_config,
        "status": row.status,
        "error_message": row.error_message,
        "total_items": int(row.total_items or 0),
        "succeeded": int(row.succeeded or 0),
        "failed": int(row.failed or 0),
        "skipped": int(row.skipped or 0),
        "total_bytes": int(row.total_bytes or 0),
        "chunks_created": int(row.chunks_created or 0),
        "items": items,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("ingestion_run", conn) or not migration.table_exists("job", conn):
        # Fresh installs that never carried the old table — nothing
        # to backfill.
        return

    # Avoid importing the ORM models — they may have moved or been
    # renamed by future code changes. Operate at the column level so
    # this migration stays compatible with arbitrary future model
    # restructuring.
    ingestion_run_cols = sa.text(
        """
        SELECT id, job_id, kb_name, kb_id, user_id, source_type, source_config,
               status, error_message, total_items, succeeded, failed, skipped,
               total_bytes, chunks_created, items, started_at, finished_at
        FROM ingestion_run
        """
    )
    rows = list(conn.execute(ingestion_run_cols).mappings())

    for row in rows:
        try:
            metadata = _build_metadata_from_run(row)
        except Exception:  # noqa: BLE001, S112 — never block the migration on a single bad row
            continue

        # Update existing job row when present.
        if row["job_id"] is not None:
            updated = conn.execute(
                sa.text("UPDATE job SET job_metadata = :md WHERE job_id = :jid"),
                {"md": _to_json(conn, metadata), "jid": str(row["job_id"])},
            )
            if (updated.rowcount or 0) > 0:
                continue
            # Fall through — job_id present but row missing: synthesize.

        # Synthesize a job row keyed by the IngestionRun.id so any
        # legacy URL referencing the old run_id still resolves.
        job_status = _RUN_STATUS_TO_JOB_STATUS.get(row["status"], "completed")
        created_ts = row["started_at"] or datetime.now(timezone.utc)
        finished_ts = row["finished_at"]
        try:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO job (
                        job_id, flow_id, status, type, user_id,
                        asset_id, asset_type,
                        created_timestamp, finished_timestamp, job_metadata
                    ) VALUES (
                        :job_id, :flow_id, :status, :type, :user_id,
                        :asset_id, :asset_type,
                        :created_timestamp, :finished_timestamp, :metadata
                    )
                    """
                ),
                {
                    "job_id": str(row["id"]),
                    "flow_id": str(row["id"]),
                    "status": job_status,
                    "type": "ingestion",
                    "user_id": str(row["user_id"]) if row["user_id"] else None,
                    "asset_id": str(row["kb_id"]) if row["kb_id"] else None,
                    "asset_type": "knowledge_base",
                    "created_timestamp": created_ts,
                    "finished_timestamp": finished_ts,
                    "metadata": _to_json(conn, metadata),
                },
            )
        except Exception:  # noqa: BLE001, S112 — keep going even if one synthesis trips a constraint
            continue


def downgrade() -> None:
    # Data migration — there is no clean way to reverse-distinguish
    # backfilled metadata from natively-written metadata once the next
    # migration drops ``ingestion_run``. Best-effort no-op: rolling
    # back the upgrade requires reverting the drop migration, at which
    # point both stores are again populated and the read path can pick
    # either.
    return


def _to_json(conn, value: dict) -> object:
    """Serialise ``value`` for the dialect-appropriate JSON binding.

    Postgres binds JSONB natively from a Python dict (psycopg adapts
    it). SQLite stores JSON as text, so we encode upfront.
    """
    if conn.dialect.name == "sqlite":
        import json

        return json.dumps(value)
    return value
