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
    SpanStatus,
    SpanTable,
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


async def _fetch_trace_token_totals(session, trace_ids: list[UUID]) -> dict[str, int]:
    token_map: dict[str, int] = {}
    if not trace_ids:
        return token_map

    parent_ids_subq = (
        select(SpanTable.parent_span_id)
        .where(SpanTable.parent_span_id != None)  # noqa: E711
        .where(col(SpanTable.trace_id).in_(trace_ids))
    ).subquery()

    token_stmt = (
        select(
            SpanTable.trace_id,
            func.coalesce(func.sum(SpanTable.total_tokens), 0).label("sum_tokens"),
        )
        .where(col(SpanTable.trace_id).in_(trace_ids))
        .where(~col(SpanTable.id).in_(select(parent_ids_subq.c.parent_span_id)))
        .group_by(col(SpanTable.trace_id))
    )
    token_rows = (await session.exec(token_stmt)).all()
    for row in token_rows:
        token_map[str(row[0])] = int(row[1] or 0)

    return token_map


async def _fetch_trace_io_map(session, trace_ids: list[UUID]) -> dict[str, dict[str, Any]]:
    io_map: dict[str, dict[str, Any]] = {}
    if not trace_ids:
        return io_map

    all_spans_stmt = select(SpanTable).where(col(SpanTable.trace_id).in_(trace_ids))
    all_spans = (await session.exec(all_spans_stmt)).all()

    spans_by_trace: dict[str, list[SpanTable]] = {}
    for span in all_spans:
        trace_id_str = str(span.trace_id)
        spans_by_trace.setdefault(trace_id_str, []).append(span)

    for trace_id_str, spans in spans_by_trace.items():
        chat_input_span = next((s for s in spans if "Chat Input" in s.name), None)
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

        io_map[trace_id_str] = {
            "input": {"input_value": input_value} if input_value else None,
            "output": output_value,
        }

    return io_map


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
) -> dict[str, Any]:
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
            trace_list = []
            for trace in traces:
                tid = str(trace.id)
                total_tokens = token_map.get(tid, trace.total_tokens)
                io_data = io_map.get(tid, {})
                trace_list.append(
                    {
                        "id": tid,
                        "name": trace.name,
                        "status": trace.status.value if trace.status else SpanStatus.UNSET,
                        "startTime": trace.start_time.isoformat() if trace.start_time else SpanStatus.UNSET,
                        "totalLatencyMs": trace.total_latency_ms,
                        "totalTokens": total_tokens,
                        "totalCost": trace.total_cost,
                        "flowId": str(trace.flow_id),
                        "sessionId": trace.session_id or str(trace.id),
                        "input": io_data.get("input"),
                        "output": io_data.get("output"),
                    }
                )

            total_count = int(total)
            total_pages = max(1, math.ceil(total_count / size)) if size else 1
            result = {"traces": trace_list, "total": total_count, "pages": total_pages}
    except Exception:
        logger.exception("Error fetching traces")
        raise
    else:
        return result


@router.get("")
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
) -> dict[str, Any]:
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
        return {"traces": [], "total": 0}
    except (OperationalError, ProgrammingError) as e:
        # Table doesn't exist or other SQL error
        logger.debug("Database error getting traces (table may not exist): %s", e)
        return {"traces": [], "total": 0}
    except Exception:
        # Log unexpected errors at error level and re-raise
        logger.exception("Unexpected error getting traces")
        raise


async def _fetch_single_trace(user_id: UUID, trace_id: UUID) -> dict[str, Any] | None:
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

        # Build hierarchical span tree
        span_tree = _build_span_tree(list(spans))

        # Aggregate tokens from leaf spans only (parents already include children's tokens)
        parent_ids = {s.parent_span_id for s in spans if s.parent_span_id}
        total_tokens = sum(s.total_tokens or 0 for s in spans if s.id not in parent_ids)

        # Return trace with span tree in frontend-compatible format
        return {
            "id": str(trace.id),
            "name": trace.name,
            "status": trace.status.value if trace.status else SpanStatus.UNSET,
            "startTime": trace.start_time.isoformat() if trace.start_time else SpanStatus.UNSET,
            "endTime": trace.end_time.isoformat() if trace.end_time else None,
            "totalLatencyMs": trace.total_latency_ms,
            "totalTokens": total_tokens or trace.total_tokens,
            "totalCost": trace.total_cost,
            "flowId": str(trace.flow_id),
            "sessionId": trace.session_id or str(trace.id),
            "spans": span_tree,
        }


@router.get("/{trace_id}")
async def get_trace(
    trace_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict[str, Any]:
    """Get a single trace with its hierarchical span tree.

    Args:
        trace_id: The ID of the trace to retrieve.
        current_user: The authenticated user (required for authorization).

    Returns:
        Dictionary containing the trace and its hierarchical span tree
        structured for frontend consumption.
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


def _build_span_tree(spans: list[SpanTable]) -> list[dict[str, Any]]:
    """Build a hierarchical span tree from flat span list.

    Args:
        spans: List of SpanTable records

    Returns:
        List of root spans with nested children
    """
    if not spans:
        return []

    # Create span dict lookup
    span_dict: dict[UUID, dict[str, Any]] = {}
    for span in spans:
        span_data = _span_to_dict(span)
        span_data["children"] = []
        span_dict[span.id] = span_data

    # Build tree by linking children to parents
    root_spans = []
    for span in spans:
        span_data = span_dict[span.id]
        if span.parent_span_id and span.parent_span_id in span_dict:
            span_dict[span.parent_span_id]["children"].append(span_data)
        else:
            root_spans.append(span_data)

    return root_spans


def _span_to_dict(span: SpanTable) -> dict[str, Any]:
    """Convert a SpanTable to a frontend-compatible dictionary.

    Args:
        span: SpanTable record

    Returns:
        Dictionary with frontend-compatible field names
    """
    token_usage = None
    if span.total_tokens:
        token_usage = {
            "promptTokens": span.prompt_tokens or 0,
            "completionTokens": span.completion_tokens or 0,
            "totalTokens": span.total_tokens,
            "cost": span.cost or 0,
        }

    return {
        "id": str(span.id),
        "name": span.name,
        "type": span.span_type.value if span.span_type else "chain",
        "status": span.status.value if span.status else SpanStatus.UNSET,
        "startTime": span.start_time.isoformat() if span.start_time else "",
        "endTime": span.end_time.isoformat() if span.end_time else None,
        "latencyMs": span.latency_ms,
        "inputs": span.inputs or {},
        "outputs": span.outputs or {},
        "error": span.error,
        "modelName": span.model_name,
        "tokenUsage": token_usage,
    }


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

            # Get all traces for this flow
            stmt = select(TraceTable).where(TraceTable.flow_id == flow_id)
            traces = (await session.exec(stmt)).all()

            # Delete all traces (cascade will delete spans)
            for trace in traces:
                await session.delete(trace)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting traces by flow")
        raise HTTPException(status_code=500, detail="Internal server error") from e
