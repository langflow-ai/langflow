"""KB ingestion-run persistence on top of the unified ``job`` table.

Per the unification work in #12903 / #12940, async work is tracked
exclusively through the ``job`` table via ``execute_with_status``. KB
ingestion follows the same pattern: a single ``job`` row carries
status, lifecycle timestamps, and per-domain progress data on its
``job_metadata`` JSON column. The legacy ``ingestion_run`` table has
been dropped.

Function signatures here remain identifier-agnostic so callers don't
need to learn the new model — what was once the ``run_id`` is now the
``job_id`` returned by ``create_run``. Read endpoints continue to
return the same shape (``RunRow``) so the frontend doesn't change.

Each call opens its own ``session_scope``: an ingestion run can span
many minutes, and holding one session open across the whole operation
would block connection-pool slots for large background jobs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionSummary,
)
from lfx.log.logger import logger
from sqlalchemy import func
from sqlmodel import select

from langflow.services.database.models.jobs.model import Job, JobType
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from lfx.base.knowledge_bases.ingestion_sources.base import KBIngestionSource


@dataclass
class RunRow:
    """Read-side projection of a KB ingestion run.

    Built from a ``Job`` row plus its ``job_metadata`` blob. Mirrors
    the legacy ``IngestionRun`` attribute names so the existing
    serializer (``_run_row_to_info``) and the frontend response shape
    don't need to change.
    """

    id: UUID
    kb_name: str
    kb_id: UUID | None
    job_id: UUID
    user_id: UUID | None
    source_type: str
    source_config: dict[str, Any]
    status: str
    error_message: str | None
    total_items: int
    succeeded: int
    failed: int
    skipped: int
    total_bytes: int
    chunks_created: int
    items: list[dict[str, Any]]
    user_metadata: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None


async def create_run(
    *,
    kb_name: str,
    source: KBIngestionSource,
    job_id: UUID | None,
    user_id: UUID | None,  # noqa: ARG001 — kept for caller signature compatibility
    kb_id: UUID | None = None,
    user_metadata: dict | None = None,
) -> UUID | None:
    """Initialise a KB-ingestion run on the job-metadata side.

    The parent ``job`` row is created upstream by the API layer (see
    ``knowledge_bases.py::ingest_files`` and friends) before
    ``execute_with_status`` is invoked. This call seeds ``job_metadata``
    with the static config (kb_name, kb_id, source_type, source_config,
    user_metadata) and a PENDING status.

    ``user_metadata`` carries the run-level tags supplied at the API
    boundary (already validated by ``parse_user_metadata``). Persisted
    onto the same ``job_metadata`` blob as the rest of the run state
    so the run-history UI can render the tags without decoding the
    per-chunk ``source_metadata`` blobs.

    Returns the ``job_id`` so callers can use it as the legacy
    ``run_id`` handle. Returns ``None`` when ``job_id`` is missing —
    no current call site should hit this path, but defensively we
    no-op rather than crash so a misconfigured ingestion still records
    its data in-memory.
    """
    if job_id is None:
        await logger.awarning("create_run called without job_id; skipping job_metadata seed")
        return None

    description = source.describe()
    source_config = description.get("config") or {}

    await _patch_job_metadata(
        job_id,
        {
            "kind": "kb_ingestion",
            "kb_name": kb_name,
            "kb_id": str(kb_id) if kb_id is not None else None,
            "source_type": source.source_type.value,
            "source_config": source_config,
            "user_metadata": user_metadata or {},
            "status": IngestionRunStatus.PENDING.value,
            "started_at": datetime.now(timezone.utc).isoformat(),
            # Legacy alias preserved for any code path still referring
            # to ``ingestion_run_id``. Equal to ``job_id`` post-cutover.
            "ingestion_run_id": str(job_id),
        },
    )
    return job_id


async def mark_running(run_id: UUID) -> None:
    """Transition a run from PENDING to RUNNING.

    ``run_id`` is the parent ``job_id``. No-ops cleanly if the row is
    missing.
    """
    await _patch_job_metadata(run_id, {"status": IngestionRunStatus.RUNNING.value})


async def finalize_run(
    run_id: UUID,
    *,
    summary: IngestionSummary,
    status: IngestionRunStatus,
    error_message: str | None = None,
) -> None:
    """Persist the final counters, items, and outcome for ``run_id``.

    Called from ``perform_ingestion`` in its ``finally`` block — must
    not raise on summary inconsistencies, otherwise the ingestion
    itself is fine but the UI shows a missing run. Errors are logged
    and swallowed.
    """
    serialized_items = [_serialize_item(item) for item in summary.items]
    finished_at = datetime.now(timezone.utc)
    try:
        await _patch_job_metadata(
            run_id,
            {
                "status": status.value,
                "error_message": error_message,
                "total_items": summary.total_items,
                "succeeded": summary.succeeded,
                "failed": summary.failed,
                "skipped": summary.skipped,
                "total_bytes": summary.total_bytes,
                "chunks_created": summary.chunks_created,
                "items": serialized_items,
                "finished_at": finished_at.isoformat(),
            },
        )
    except Exception as exc:  # noqa: BLE001
        await logger.aerror("Failed to finalize ingestion run %s: %s", run_id, exc)


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
) -> tuple[list[RunRow], int]:
    """Return a page of KB ingestion runs for ``kb_name`` scoped to ``user_id``.

    Prefers the indexed ``Job.asset_id`` filter (resolved via
    ``KnowledgeBaseRecord.id``) over a JSON-extract on
    ``Job.job_metadata.kb_name``. The asset_id path is a btree index
    lookup, free of dialect-specific JSON gymnastics; the JSON-extract
    fallback only fires for legacy KBs that exist on disk but haven't
    been backfilled into the ``knowledge_base`` table yet.

    Ordered newest-first by ``Job.created_timestamp`` — the drill-down
    UI reads the most recent run the vast majority of the time.
    """
    # Lazy import: ``ingestion_run_service`` lives in the langflow API
    # surface but the KB record lookup is also there; avoid a circular
    # at module import time.
    from langflow.api.utils import knowledge_base_service

    offset = max(page - 1, 0) * limit
    kb_record = await knowledge_base_service.get_by_user_and_name(user_id, kb_name)

    async with session_scope() as session:
        if kb_record is not None:
            base_filter = (
                (Job.user_id == user_id)
                & (Job.type == JobType.INGESTION)
                & (Job.asset_type == "knowledge_base")
                & (Job.asset_id == kb_record.id)
            )
        else:
            # Legacy fallback for KBs not yet reconciled into the DB.
            kb_name_expr = Job.job_metadata["kb_name"].as_string()
            base_filter = (Job.user_id == user_id) & (Job.type == JobType.INGESTION) & (kb_name_expr == kb_name)

        count_stmt = select(func.count()).select_from(Job).where(base_filter)
        total = (await session.exec(count_stmt)).one()

        page_stmt = (
            select(Job)
            .where(base_filter)
            .order_by(Job.created_timestamp.desc())  # type: ignore[attr-defined]
            .offset(offset)
            .limit(limit)
        )
        rows = list((await session.exec(page_stmt)).all())

    return [_job_to_run_row(j) for j in rows], int(total)


async def get_run(run_id: UUID, *, user_id: UUID) -> RunRow | None:
    """Fetch a single run, scoped to ``user_id`` for authz.

    ``run_id`` is the parent ``job_id``. Returns ``None`` when the row
    is missing OR belongs to someone else — the caller maps both to
    404 so a user can't enumerate other users' run ids.

    Also returns ``None`` for jobs of the wrong type (e.g. a workflow
    job_id submitted to a KB runs endpoint), since the response shape
    is KB-specific.
    """
    async with session_scope() as session:
        job = await session.get(Job, run_id)
    if job is None or job.user_id != user_id or job.type != JobType.INGESTION:
        return None
    return _job_to_run_row(job)


def _job_to_run_row(job: Job) -> RunRow:
    """Project a ``Job`` row into the legacy ``RunRow`` shape.

    Counters / per-item outcomes live on ``job_metadata``; lifecycle
    timestamps come from the ``job`` row itself so they reflect the
    canonical ``execute_with_status`` lifecycle (not whatever the
    ingestion code happened to write).
    """
    metadata: dict[str, Any] = dict(job.job_metadata or {})
    kb_id_raw = metadata.get("kb_id")
    return RunRow(
        id=job.job_id,
        kb_name=metadata.get("kb_name", ""),
        kb_id=UUID(kb_id_raw) if isinstance(kb_id_raw, str) and kb_id_raw else None,
        job_id=job.job_id,
        user_id=job.user_id,
        source_type=metadata.get("source_type", ""),
        source_config=dict(metadata.get("source_config") or {}),
        status=metadata.get("status", IngestionRunStatus.PENDING.value),
        error_message=metadata.get("error_message"),
        total_items=int(metadata.get("total_items", 0) or 0),
        succeeded=int(metadata.get("succeeded", 0) or 0),
        failed=int(metadata.get("failed", 0) or 0),
        skipped=int(metadata.get("skipped", 0) or 0),
        total_bytes=int(metadata.get("total_bytes", 0) or 0),
        chunks_created=int(metadata.get("chunks_created", 0) or 0),
        items=list(metadata.get("items") or []),
        user_metadata=dict(metadata.get("user_metadata") or {}),
        started_at=job.created_timestamp,
        finished_at=job.finished_timestamp,
    )


async def _patch_job_metadata(job_id: UUID, patch: dict[str, Any]) -> None:
    """Shallow-merge ``patch`` into ``job.job_metadata`` (creating it if needed).

    Best-effort: a missing job row, a stale session, or an in-flight
    enum migration on ``status`` should never crash the ingestion. The
    parent caller in ``perform_ingestion`` already has its own
    ``finally`` cleanup; this layer just records the data.
    """
    try:
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            existing = job.job_metadata or {}
            job.job_metadata = {**existing, **patch}
            session.add(job)
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        await logger.awarning("Job metadata write failed for %s: %s", job_id, exc)
