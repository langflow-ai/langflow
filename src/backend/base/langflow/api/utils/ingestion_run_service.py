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
from sqlalchemy import func
from sqlmodel import select

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
    kb_id: UUID | None = None,
) -> UUID:
    """Insert a PENDING ``ingestion_run`` row and return its id.

    ``source.describe()`` is responsible for redacting credential
    material from ``source_config`` before it lands in the DB.

    ``kb_id`` is optional: the Phase 1.5 expand-contract pattern keeps
    ``kb_name`` as the legacy pointer, so a run still records a row
    even if the KB doesn't yet have a ``knowledge_base`` DB entry
    (backfill will link them on the next list).
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
            kb_id=kb_id,
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


async def list_runs_for_kb(
    *,
    kb_name: str,
    user_id: UUID,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[IngestionRun], int]:
    """Return a page of runs for ``kb_name`` scoped to ``user_id``.

    Runs are scoped to the user so one account can't observe another's
    ingestion history. Ordered newest first — the drill-down UI reads
    the most recent run the vast majority of the time.

    Returns the page of rows plus the total count (needed so the UI
    can render pagination without a second round-trip).
    """
    offset = max(page - 1, 0) * limit
    async with session_scope() as session:
        base_filter = (IngestionRun.kb_name == kb_name) & (IngestionRun.user_id == user_id)

        count_stmt = select(func.count()).select_from(IngestionRun).where(base_filter)
        total = (await session.exec(count_stmt)).one()

        page_stmt = (
            select(IngestionRun)
            .where(base_filter)
            .order_by(IngestionRun.started_at.desc())  # type: ignore[attr-defined]
            .offset(offset)
            .limit(limit)
        )
        rows = list((await session.exec(page_stmt)).all())

    return rows, int(total)


async def get_run(run_id: UUID, *, user_id: UUID) -> IngestionRun | None:
    """Fetch a single run, scoped to ``user_id`` for authz.

    Returns ``None`` when the run is missing *or* belongs to someone
    else — the caller maps both to 404 so a user can't enumerate
    other users' run ids.
    """
    async with session_scope() as session:
        row = await session.get(IngestionRun, run_id)
    if row is None or row.user_id != user_id:
        return None
    return row
