"""API endpoints for execution traces.

This module provides endpoints for retrieving execution trace data
from the native tracer, enabling the Trace View in the frontend.
"""

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlmodel import col, select

from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.traces.model import (
    SpanReadResponse,
    SpanStatus,
    SpanTable,
    SpanType,
    TraceListResponse,
    TraceRead,
    TraceSummaryRead,
    TraceTable,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope

logger = logging.getLogger(__name__)

# Timeout for database operations (in seconds)
DB_TIMEOUT = 5.0

router = APIRouter(prefix="/monitor/traces", tags=["Traces"])


def _sanitize_query_string(value: str | None, max_len: int = 50) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in value if " " <= ch <= "~")
    return cleaned.strip()[:max_len] if cleaned else None


def _safe_int_tokens(value: Any) -> int:
    """Safely coerce a token count value to int, returning 0 on failure.

    Handles int, float, and string representations (including "12.0").
    """
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            try:
                return int(float(value))
            except (ValueError, TypeError):
                logger.debug("Could not coerce token value to int: %r", value)
                return 0
    logger.debug("Unexpected token value type %s: %r", type(value).__name__, value)
    return 0


async def _fetch_trace_token_totals(session, trace_ids: list[UUID]) -> dict[str, int]:
    token_map: dict[str, int] = {}
    if not trace_ids:
        return token_map

    # Fetch all spans for the given traces and sum total_tokens from attributes JSON
    all_spans_stmt = select(SpanTable.trace_id, SpanTable.id, SpanTable.parent_span_id, SpanTable.attributes).where(
        col(SpanTable.trace_id).in_(trace_ids)
    )
    rows = (await session.exec(all_spans_stmt)).all()

    # Determine parent IDs (to count only leaf spans and avoid double-counting)
    parent_ids = {row[2] for row in rows if row[2] is not None}

    for row in rows:
        trace_id_val, span_id, _parent_span_id, attributes = row
        # Skip parent spans to avoid double-counting
        if span_id in parent_ids:
            continue
        attrs = attributes or {}
        total_tokens = attrs.get("llm.usage.total_tokens") or attrs.get("total_tokens") or 0
        tid = str(trace_id_val)
        token_map[tid] = token_map.get(tid, 0) + _safe_int_tokens(total_tokens)

    return token_map


async def _fetch_trace_io_map(session, trace_ids: list[UUID]) -> dict[str, dict[str, Any]]:
    io_map: dict[str, dict[str, Any]] = {}
    if not trace_ids:
        return io_map

    # Select only the columns needed for I/O extraction to avoid loading heavy JSON blobs
    all_spans_stmt = sa.select(
        col(SpanTable.trace_id),
        col(SpanTable.name),
        col(SpanTable.parent_span_id),
        col(SpanTable.end_time),
        col(SpanTable.inputs),
        col(SpanTable.outputs),
    ).where(col(SpanTable.trace_id).in_(trace_ids))
    rows = (await session.execute(all_spans_stmt)).all()

    # Group lightweight row tuples by trace_id for I/O extraction
    rows_by_trace: dict[str, list[Any]] = {}
    for row in rows:
        rows_by_trace.setdefault(str(row[0]), []).append(row)

    for trace_id_str, trace_rows in rows_by_trace.items():
        io_map[trace_id_str] = _extract_trace_io_from_rows(trace_rows)

    return io_map


def _extract_trace_io_from_rows(rows: list[Any]) -> dict[str, Any]:
    """Extract a simplified input/output payload for a trace from lightweight row tuples.

    Row tuple layout: (trace_id, name, parent_span_id, end_time, inputs, outputs)

    - Input: derived from the first row with a name containing "Chat Input" (if present)
    - Output: derived from the most recently finished root span (if present)
    """
    chat_input_row = next((r for r in rows if "Chat Input" in (r[1] or "")), None)
    input_value = None
    if chat_input_row and chat_input_row[4]:
        input_value = chat_input_row[4].get("input_value")

    root_rows = [r for r in rows if r[2] is None and r[3] is not None]
    output_value = None
    if root_rows:
        root_rows_sorted = sorted(
            root_rows,
            key=lambda r: r[3] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        if root_rows_sorted and root_rows_sorted[0][5]:
            output_value = root_rows_sorted[0][5]

    return {
        "input": {"input_value": input_value} if input_value else None,
        "output": output_value,
    }


def _extract_trace_io_from_spans(spans: list[SpanTable]) -> dict[str, Any]:
    """Extract a simplified input/output payload for a trace from SpanTable objects.

    Used by _fetch_single_trace which already loads full span objects.

    - Input: derived from the first span with a name containing "Chat Input" (if present)
    - Output: derived from the most recently finished root span (if present)
    """
    chat_input_span = next((s for s in spans if "Chat Input" in (s.name or "")), None)
    input_value = None
    if chat_input_span and chat_input_span.inputs:
        input_value = chat_input_span.inputs.get("input_value")

    root_spans = [s for s in spans if s.parent_span_id is None and s.end_time]
    output_value = None
    if root_spans:
        root_spans_sorted = sorted(
            root_spans,
            key=lambda s: s.end_time or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        if root_spans_sorted and root_spans_sorted[0].outputs:
            output_value = root_spans_sorted[0].outputs

    return {
        "input": {"input_value": input_value} if input_value else None,
        "output": output_value,
    }


async def _fetch_traces(
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
    """Internal function to fetch traces with proper session management."""
    try:
        async with session_scope() as session:
            # Join with Flow table to filter by user_id for authorization
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

            # Order by most recent first
            stmt = stmt.order_by(col(TraceTable.start_time).desc())
            stmt = stmt.offset((page - 1) * size).limit(size)

            total = (await session.exec(count_stmt)).one()

            traces = (await session.exec(stmt)).all()

            # Get aggregated token counts per trace (leaf spans only to avoid double-counting)
            trace_ids = [trace.id for trace in traces]
            token_map = await _fetch_trace_token_totals(session, trace_ids)

            # Fetch Chat Input span input_value and final output for each trace
            io_map = await _fetch_trace_io_map(session, trace_ids)

            # Convert to response format
            total_count = int(total)
            total_pages = math.ceil(total_count / size) if total_count > 0 else 0
            trace_summaries = []
            for trace in traces:
                tid = str(trace.id)
                total_tokens = token_map.get(tid, trace.total_tokens)
                io_data = io_map.get(tid, {})
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
                        input=io_data.get("input"),
                        output=io_data.get("output"),
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


@router.get("", response_model_by_alias=True)
async def get_traces(
    current_user: Annotated[User, Depends(get_current_active_user)],
    flow_id: Annotated[UUID | None, Query()] = None,
    session_id: Annotated[str | None, Query()] = None,
    status: Annotated[SpanStatus | None, Query()] = None,
    query: Annotated[str | None, Query()] = None,
    start_time: Annotated[datetime | None, Query()] = None,
    end_time: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> TraceListResponse:
    """Get list of traces for a flow.

    Args:
        current_user: Authenticated user (required for authorization)
        flow_id: Filter by flow ID
        session_id: Filter by session ID
        status: Filter by trace status
        query: Search query for trace name/id/session id
        start_time: Filter traces starting on/after this time (ISO)
        end_time: Filter traces starting on/before this time (ISO)
        page: Page number (1-based)
        size: Page size

    Returns:
        List of traces
    """
    try:
        query = _sanitize_query_string(query)
        # Use timeout to prevent hanging if database has issues
        return await asyncio.wait_for(
            _fetch_traces(current_user.id, flow_id, session_id, status, query, start_time, end_time, page, size),
            timeout=DB_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("Traces query timed out after %ss (table may not exist or DB is slow)", DB_TIMEOUT)
        return TraceListResponse(traces=[], total=0, pages=0)
    except (OperationalError, ProgrammingError) as e:
        # Table doesn't exist or other SQL error
        logger.debug("Database error getting traces (table may not exist): %s", e)
        return TraceListResponse(traces=[], total=0, pages=0)
    except Exception:
        # Log unexpected errors at error level and re-raise
        logger.exception("Unexpected error getting traces")
        raise


async def _fetch_single_trace(user_id: UUID, trace_id: UUID) -> TraceRead | None:
    """Internal function to fetch a single trace with its spans."""
    async with session_scope() as session:
        # Get trace with authorization check
        stmt = (
            select(TraceTable)
            .join(Flow, col(TraceTable.flow_id) == col(Flow.id))
            .where(col(TraceTable.id) == trace_id)
            .where(col(Flow.user_id) == user_id)
        )
        trace = (await session.exec(stmt)).first()

        if not trace:
            return None

        # Get all spans for this trace
        spans_stmt = select(SpanTable).where(SpanTable.trace_id == trace_id)
        spans_stmt = spans_stmt.order_by(col(SpanTable.start_time).asc())
        spans = (await session.exec(spans_stmt)).all()

        io_data = _extract_trace_io_from_spans(list(spans))

        # Build hierarchical span tree
        span_tree = _build_span_tree(list(spans))

        # Aggregate tokens from leaf spans only (parents already include children's tokens)
        parent_ids = {s.parent_span_id for s in spans if s.parent_span_id}
        total_tokens = sum(
            _safe_int_tokens(
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


@router.get("/{trace_id}", response_model_by_alias=True)
async def get_trace(
    trace_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TraceRead:
    """Get a single trace with its hierarchical span tree.

    Args:
        trace_id: The ID of the trace to retrieve.
        current_user: The authenticated user (required for authorization).

    Returns:
        TraceRead containing the trace and its hierarchical span tree.
    """
    try:
        result = await asyncio.wait_for(
            _fetch_single_trace(current_user.id, trace_id),
            timeout=DB_TIMEOUT,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Trace not found")
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.warning("Single trace query timed out after %ss", DB_TIMEOUT)
        raise HTTPException(status_code=504, detail="Database query timed out") from None
    except (OperationalError, ProgrammingError) as e:
        logger.debug("Database error getting trace: %s", e)
        raise HTTPException(status_code=500, detail="Database error") from e
    except Exception as e:
        logger.exception("Error getting trace")
        raise HTTPException(status_code=500, detail="Internal server error") from e
    else:
        return result


def _build_span_tree(spans: list[SpanTable]) -> list[SpanReadResponse]:
    """Build a hierarchical span tree from flat span list.

    Args:
        spans: List of SpanTable records

    Returns:
        List of root spans with nested children
    """
    if not spans:
        return []

    # Create span lookup keyed by ID
    span_dict: dict[UUID, SpanReadResponse] = {}
    for span in spans:
        span_dict[span.id] = _span_to_response(span)

    # Build tree by linking children to parents
    root_spans: list[SpanReadResponse] = []
    for span in spans:
        span_response = span_dict[span.id]
        if span.parent_span_id and span.parent_span_id in span_dict:
            span_dict[span.parent_span_id].children.append(span_response)
        else:
            root_spans.append(span_response)

    return root_spans


def _span_to_response(span: SpanTable) -> SpanReadResponse:
    """Convert a SpanTable to a SpanReadResponse.

    Args:
        span: SpanTable record

    Returns:
        SpanReadResponse with frontend-compatible field names
    """
    token_usage = None
    if span.attributes:
        token_usage = {
            "promptTokens": span.attributes.get("prompt_tokens", 0),
            "completionTokens": span.attributes.get("completion_tokens", 0),
            "totalTokens": span.attributes.get("total_tokens", 0),
            "cost": span.attributes.get("cost", 0.0),
        }

    return SpanReadResponse(
        id=span.id,
        name=span.name,
        type=span.span_type or SpanType.CHAIN,
        status=span.status or SpanStatus.UNSET,
        start_time=span.start_time,
        end_time=span.end_time,
        latency_ms=span.latency_ms,
        inputs=span.inputs,
        outputs=span.outputs,
        error=span.error,
        model_name=(span.attributes or {}).get("model_name"),
        token_usage=token_usage,
    )


@router.delete("/{trace_id}", status_code=204)
async def delete_trace(
    trace_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete a trace and all its spans.

    Args:
        trace_id: The ID of the trace to delete.
        current_user: The authenticated user (required for authorization).
    """
    try:
        async with session_scope() as session:
            # Verify user owns the flow before deleting
            stmt = (
                select(TraceTable)
                .join(Flow, col(TraceTable.flow_id) == col(Flow.id))
                .where(col(TraceTable.id) == trace_id)
                .where(col(Flow.user_id) == current_user.id)
            )
            trace = (await session.exec(stmt)).first()

            if not trace:
                raise HTTPException(status_code=404, detail="Trace not found")

            # Delete trace (cascade will delete spans)
            await session.delete(trace)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting trace")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.delete("", status_code=204)
async def delete_traces_by_flow(
    flow_id: Annotated[UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete all traces for a flow.

    Args:
        flow_id: The ID of the flow whose traces should be deleted.
        current_user: The authenticated user (required for authorization).
    """
    try:
        async with session_scope() as session:
            # Verify user owns the flow before deleting traces
            flow_stmt = select(Flow).where(col(Flow.id) == flow_id).where(col(Flow.user_id) == current_user.id)
            flow = (await session.exec(flow_stmt)).first()

            if not flow:
                raise HTTPException(status_code=404, detail="Flow not found")

            # Bulk-delete all traces for this flow.
            # The DB-level CASCADE on SpanTable.trace_id handles span deletion.
            delete_stmt = sa.delete(TraceTable).where(col(TraceTable.flow_id) == flow_id)
            await session.execute(delete_stmt)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting traces by flow")
        raise HTTPException(status_code=500, detail="Internal server error") from e
