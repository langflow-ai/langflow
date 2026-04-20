"""Persistence helpers for ``ingestion_run`` rows.

Small, direct session-based CRUD — a full repository class would be
premature here since there's exactly one write path
(``KBIngestionHelper.perform_ingestion``) and Phase 2 reads will go
through dedicated query endpoints.

Each call opens its own ``session_scope``: an ingestion run can span
many minutes, and holding one session open across the whole operation
would block connection-pool slots for large background jobs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItemStatus,
    IngestionSummary,
)
from lfx.log.logger import logger

from langflow.services.database.models.ingestion_run import IngestionRun, IngestionRunStatus
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from lfx.base.knowledge_bases.ingestion_sources.base import KBIngestionSource


async def create_run(
    *,
    kb_name: str,
    source: KBIngestionSource,
    job_id: UUID | None,
    user_id: UUID | None,
) -> UUID:
    """Insert a PENDING ``ingestion_run`` row and return its id.

    ``source.describe()`` is responsible for redacting credential
    material from ``source_config`` before it lands in the DB.
    """
    run_id = uuid4()
    description = source.describe()
    # Persist only the config blob, not the whole describe() envelope —
    # display_name etc. are reconstructable from source_type at read time.
    source_config = description.get("config") or {}

    async with session_scope() as session:
        row = IngestionRun(
            id=run_id,
            job_id=job_id,
            kb_name=kb_name,
            user_id=user_id,
            source_type=source.source_type.value,
            source_config=source_config,
            status=IngestionRunStatus.PENDING.value,
            items=[],
        )
        session.add(row)
        await session.commit()
    return run_id


async def mark_running(run_id: UUID) -> None:
    await _update(run_id, status=IngestionRunStatus.RUNNING.value)


async def finalize_run(
    run_id: UUID,
    *,
    summary: IngestionSummary,
    status: IngestionRunStatus,
    error_message: str | None = None,
) -> None:
    """Write the final counters, items, and status for ``run_id``.

    Called from ``perform_ingestion`` in its ``finally`` block — must
    not raise on ``summary`` inconsistencies, otherwise the ingestion
    itself is fine but the UI shows a missing run. Errors are logged
    and swallowed here.
    """
    try:
        await _update(
            run_id,
            status=status.value,
            error_message=error_message,
            total_items=summary.total_items,
            succeeded=summary.succeeded,
            failed=summary.failed,
            skipped=summary.skipped,
            total_bytes=summary.total_bytes,
            chunks_created=summary.chunks_created,
            items=[_serialize_item(item) for item in summary.items],
            finished_at=datetime.now(timezone.utc),
        )
    except Exception as exc:  # noqa: BLE001
        await logger.aerror("Failed to finalize ingestion run %s: %s", run_id, exc)


async def _update(run_id: UUID, **fields) -> None:
    """Partial update of an ``ingestion_run`` row.

    Kept private — callers go through ``mark_running`` / ``finalize_run``
    so the status transitions stay controlled.
    """
    async with session_scope() as session:
        row = await session.get(IngestionRun, run_id)
        if row is None:
            await logger.awarning("ingestion_run %s missing on update; skipping", run_id)
            return
        for key, value in fields.items():
            if value is not None or key in {"error_message", "finished_at"}:
                setattr(row, key, value)
        session.add(row)
        await session.commit()


def _serialize_item(item) -> dict:
    """Convert an ``IngestionItemResult`` into a JSON-safe dict."""
    status = item.status.value if isinstance(item.status, IngestionItemStatus) else item.status
    return {
        "item_id": item.item_id,
        "display_name": item.display_name,
        "status": status,
        "chunks_created": item.chunks_created,
        "error_message": item.error_message,
    }
