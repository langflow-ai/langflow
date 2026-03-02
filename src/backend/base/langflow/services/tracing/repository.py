"""Repository layer for trace/span database queries.

Handles all data-access operations for traces and spans, keeping
query/aggregation logic out of the API layer.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlmodel import col, func, select

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.traces.model import (
    SpanStatus,
    SpanTable,
    TraceListResponse,
    TraceRead,
    TraceSummaryRead,
    TraceTable,
)
from langflow.services.deps import session_scope
from langflow.services.tracing.formatting import (
    TraceSummaryData,
    build_span_tree,
    compute_leaf_token_total,
    extract_trace_io_from_rows,
    extract_trace_io_from_spans,
)

logger = logging.getLogger(__name__)


def _trace_to_base_fields(
    trace: TraceTable,
    total_tokens: int,
    summary: TraceSummaryData | None,
) -> dict:
    """Build the shared field mapping common to both TraceSummaryRead and TraceRead.

    Centralises the field extraction that was previously duplicated in
    ``fetch_traces`` and ``fetch_single_trace``, ensuring both response models
    are built from a single source of truth.

    Args:
        trace: The TraceTable ORM record.
        total_tokens: Pre-computed effective token count (leaf-span total or
            fallback to the stored ``trace.total_tokens``).
        summary: Optional TraceSummaryData carrying the I/O payload.  When
            ``None`` both ``input`` and ``output`` are set to ``None``.

    Returns:
        Dict of keyword arguments suitable for unpacking into either
        ``TraceSummaryRead(**...)`` or ``TraceRead(**...)``.
    """
    return {
        "id": trace.id,
        "name": trace.name,
        "status": trace.status or SpanStatus.UNSET,
        "start_time": trace.start_time,
        "total_latency_ms": trace.total_latency_ms,
        "total_tokens": total_tokens,
        "flow_id": trace.flow_id,
        "session_id": trace.session_id or str(trace.id),
        "input": summary.input if summary else None,
        "output": summary.output if summary else None,
    }


async def fetch_trace_summary_data(session: AsyncSession, trace_ids: list[UUID]) -> dict[str, TraceSummaryData]:
    """Fetch aggregated token totals and I/O summaries for a batch of traces.

    Makes a single database round-trip by selecting all columns needed for both
    token aggregation and I/O extraction, then processes them together per trace.

    Token counting uses only leaf spans (spans that are not parents of other spans)
    to avoid double-counting tokens in nested LLM call hierarchies.

    Args:
        session: Active async database session.
        trace_ids: List of trace IDs to aggregate.

    Returns:
        Mapping of trace ID string to :class:`TraceSummaryData`.
    """
    summary_map: dict[str, TraceSummaryData] = {}
    if not trace_ids:
        return summary_map

    all_spans_stmt = sa.select(
        col(SpanTable.trace_id),
        col(SpanTable.id),
        col(SpanTable.name),
        col(SpanTable.parent_span_id),
        col(SpanTable.end_time),
        col(SpanTable.inputs),
        col(SpanTable.outputs),
        col(SpanTable.attributes),
    ).where(col(SpanTable.trace_id).in_(trace_ids))
    rows = (await session.execute(all_spans_stmt)).all()

    parent_ids = {row[3] for row in rows if row[3] is not None}

    rows_by_trace: dict[str, list[Any]] = {}
    for row in rows:
        rows_by_trace.setdefault(str(row[0]), []).append(row)

    for trace_id_str, trace_rows in rows_by_trace.items():
        span_ids = [row[1] for row in trace_rows]
        attributes_by_id = {row[1]: (row[7] or {}) for row in trace_rows}
        total_tokens = compute_leaf_token_total(span_ids, parent_ids, attributes_by_id)

        io_rows = [(r[0], r[2], r[3], r[4], r[5], r[6]) for r in trace_rows]
        io_data = extract_trace_io_from_rows(io_rows)

        summary_map[trace_id_str] = TraceSummaryData(
            total_tokens=total_tokens,
            input=io_data.get("input"),
            output=io_data.get("output"),
        )

    return summary_map


async def fetch_traces(
    user_id: UUID,
    flow_id: UUID | None,
    session_id: str | None,
    status: SpanStatus | None,
    query: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
    page: int,
    size: int,
) -> TraceListResponse:
    """Fetch a paginated list of traces for a user, with optional filters."""
    try:
        async with session_scope() as session:
            stmt = (
                select(TraceTable)
                .join(Flow, col(TraceTable.flow_id) == col(Flow.id))
                .where(col(Flow.user_id) == user_id)
            )
            count_stmt = (
                select(func.count())
                .select_from(TraceTable)
                .join(Flow, col(TraceTable.flow_id) == col(Flow.id))
                .where(col(Flow.user_id) == user_id)
            )

            # Build filter expressions once and apply them to both statements,
            # avoiding the duplication of every condition across stmt + count_stmt.
            filters: list[Any] = []
            if flow_id:
                filters.append(TraceTable.flow_id == flow_id)
            if session_id:
                filters.append(TraceTable.session_id == session_id)
            if status:
                filters.append(TraceTable.status == status)
            if query:
                search_value = f"%{query}%"
                filters.append(
                    sa.or_(
                        sa.cast(TraceTable.name, sa.String).ilike(search_value),
                        sa.cast(TraceTable.id, sa.String).ilike(search_value),
                        sa.cast(TraceTable.session_id, sa.String).ilike(search_value),
                    )
                )
            if start_time:
                filters.append(TraceTable.start_time >= start_time)
            if end_time:
                filters.append(TraceTable.start_time <= end_time)

            for f in filters:
                stmt = stmt.where(f)
                count_stmt = count_stmt.where(f)

            stmt = stmt.order_by(col(TraceTable.start_time).desc())
            stmt = stmt.offset((page - 1) * size).limit(size)

            total = (await session.exec(count_stmt)).one()
            traces = (await session.exec(stmt)).all()

            trace_ids = [trace.id for trace in traces]
            summary_map = await fetch_trace_summary_data(session, trace_ids)

            total_count = int(total)
            total_pages = math.ceil(total_count / size) if total_count > 0 else 0
            trace_summaries = []
            for trace in traces:
                summary = summary_map.get(str(trace.id))
                effective_tokens = summary.total_tokens if summary else trace.total_tokens
                trace_summaries.append(
                    TraceSummaryRead(
                        **_trace_to_base_fields(trace, effective_tokens, summary),
                    )
                )

            return TraceListResponse(
                traces=trace_summaries,
                total=total_count,
                pages=total_pages,
            )
    except Exception:
        logger.exception("Error fetching traces")
        raise


async def fetch_single_trace(user_id: UUID, trace_id: UUID) -> TraceRead | None:
    """Fetch a single trace with its full hierarchical span tree."""
    async with session_scope() as session:
        stmt = (
            select(TraceTable)
            .join(Flow, col(TraceTable.flow_id) == col(Flow.id))
            .where(col(TraceTable.id) == trace_id)
            .where(col(Flow.user_id) == user_id)
        )
        trace = (await session.exec(stmt)).first()

        if not trace:
            return None

        spans_stmt = select(SpanTable).where(SpanTable.trace_id == trace_id)
        spans_stmt = spans_stmt.order_by(col(SpanTable.start_time).asc())
        spans = (await session.exec(spans_stmt)).all()

        io_data = extract_trace_io_from_spans(list(spans))
        span_tree = build_span_tree(list(spans))

        parent_ids = {s.parent_span_id for s in spans if s.parent_span_id}
        span_ids = [s.id for s in spans]
        attributes_by_id = {s.id: (s.attributes or {}) for s in spans}
        computed_tokens = compute_leaf_token_total(span_ids, parent_ids, attributes_by_id)

        effective_tokens = computed_tokens or trace.total_tokens

        # Build a lightweight summary so _trace_to_base_fields can supply io_data.
        io_summary = TraceSummaryData(
            total_tokens=effective_tokens,
            input=io_data.get("input"),
            output=io_data.get("output"),
        )

        return TraceRead(
            **_trace_to_base_fields(trace, effective_tokens, io_summary),
            end_time=trace.end_time,
            spans=span_tree,
        )
