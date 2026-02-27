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
    extract_trace_io_from_rows,
    extract_trace_io_from_spans,
    safe_int_tokens,
)

logger = logging.getLogger(__name__)


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
        total_tokens = 0
        for row in trace_rows:
            span_id = row[1]
            if span_id not in parent_ids:
                attrs = row[7] or {}
                token_val = attrs.get("llm.usage.total_tokens") or attrs.get("total_tokens") or 0
                total_tokens += safe_int_tokens(token_val)

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

            if flow_id:
                stmt = stmt.where(TraceTable.flow_id == flow_id)
                count_stmt = count_stmt.where(TraceTable.flow_id == flow_id)
            if session_id:
                stmt = stmt.where(TraceTable.session_id == session_id)
                count_stmt = count_stmt.where(TraceTable.session_id == session_id)
            if status:
                stmt = stmt.where(TraceTable.status == status)
                count_stmt = count_stmt.where(TraceTable.status == status)
            if query:
                search_value = f"%{query}%"
                search_filter = sa.or_(
                    sa.cast(TraceTable.name, sa.String).ilike(search_value),
                    sa.cast(TraceTable.id, sa.String).ilike(search_value),
                    sa.cast(TraceTable.session_id, sa.String).ilike(search_value),
                )
                stmt = stmt.where(search_filter)
                count_stmt = count_stmt.where(search_filter)
            if start_time:
                stmt = stmt.where(TraceTable.start_time >= start_time)
                count_stmt = count_stmt.where(TraceTable.start_time >= start_time)
            if end_time:
                stmt = stmt.where(TraceTable.start_time <= end_time)
                count_stmt = count_stmt.where(TraceTable.start_time <= end_time)

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
                tid = str(trace.id)
                summary = summary_map.get(tid)
                total_tokens = summary.total_tokens if summary else trace.total_tokens
                trace_summaries.append(
                    TraceSummaryRead(
                        id=trace.id,
                        name=trace.name,
                        status=trace.status or SpanStatus.UNSET,
                        start_time=trace.start_time,
                        total_latency_ms=trace.total_latency_ms,
                        total_tokens=total_tokens,
                        total_cost=trace.total_cost,
                        flow_id=trace.flow_id,
                        session_id=trace.session_id or tid,
                        input=summary.input if summary else None,
                        output=summary.output if summary else None,
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
        total_tokens = sum(
            safe_int_tokens(
                (s.attributes or {}).get("llm.usage.total_tokens") or (s.attributes or {}).get("total_tokens") or 0
            )
            for s in spans
            if s.id not in parent_ids
        )

        return TraceRead(
            id=trace.id,
            name=trace.name,
            status=trace.status or SpanStatus.UNSET,
            start_time=trace.start_time,
            end_time=trace.end_time,
            total_latency_ms=trace.total_latency_ms,
            total_tokens=total_tokens or trace.total_tokens,
            total_cost=trace.total_cost,
            flow_id=trace.flow_id,
            session_id=trace.session_id or str(trace.id),
            input=io_data.get("input"),
            output=io_data.get("output"),
            spans=span_tree,
        )
