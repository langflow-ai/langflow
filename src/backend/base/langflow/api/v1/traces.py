"""API endpoints for execution traces.

This module provides endpoints for retrieving execution trace data
from the native tracer, enabling the Trace View in the frontend.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import col, select

from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.traces.model import (
    SpanStatus,
    SpanTable,
    TraceTable,
)
from langflow.services.database.models.user.model import User

router = APIRouter(prefix="/traces", tags=["Traces"])


@router.get("", dependencies=[Depends(get_current_active_user)])
async def get_traces(
    current_user: Annotated[User, Depends(get_current_active_user)],
    flow_id: Annotated[UUID | None, Query()] = None,
    session_id: Annotated[str | None, Query()] = None,
    status: Annotated[SpanStatus | None, Query()] = None,
) -> dict[str, Any]:
    """Get list of traces for a flow.

    Args:
        flow_id: Filter by flow ID
        session_id: Filter by session ID
        status: Filter by trace status

    Returns:
        List of traces
    """
    from lfx.log.logger import logger
    from lfx.services.deps import session_scope

    try:
        async with session_scope() as session:
            # Simple query - just get traces for this flow
            stmt = select(TraceTable)

            if flow_id:
                stmt = stmt.where(TraceTable.flow_id == flow_id)
            if session_id:
                stmt = stmt.where(TraceTable.session_id == session_id)
            if status:
                stmt = stmt.where(TraceTable.status == status)

            # Order by most recent first
            stmt = stmt.order_by(col(TraceTable.start_time).desc())
            stmt = stmt.limit(10)

            traces = (await session.exec(stmt)).all()

            # Convert to response format
            trace_list = []
            for trace in traces:
                trace_list.append({
                    "id": str(trace.id),
                    "name": trace.name,
                    "status": trace.status.value if trace.status else "success",
                    "startTime": trace.start_time.isoformat() if trace.start_time else "",
                    "totalLatencyMs": trace.total_latency_ms,
                    "totalTokens": trace.total_tokens,
                    "totalCost": trace.total_cost,
                    "flowId": str(trace.flow_id),
                })

            return {"traces": trace_list, "total": len(trace_list)}
    except Exception as e:
        # Log error but return empty list (table might not exist yet)
        logger.debug(f"Error getting traces (table may not exist): {e}")
        return {"traces": [], "total": 0}


@router.get("/{trace_id}")
async def get_trace(
    trace_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict[str, Any]:
    """Get a single trace with its hierarchical span tree.

    Args:
        trace_id: The trace ID to retrieve

    Returns:
        Trace with nested span tree structured for frontend consumption
    """
    from lfx.log.logger import logger
    from lfx.services.deps import session_scope

    try:
        async with session_scope() as session:
            # Get trace (simple query without JOIN for now)
            stmt = select(TraceTable).where(TraceTable.id == trace_id)
            trace = (await session.exec(stmt)).first()

            if not trace:
                raise HTTPException(status_code=404, detail="Trace not found")

            # Get all spans for this trace
            spans_stmt = select(SpanTable).where(SpanTable.trace_id == trace_id)
            spans_stmt = spans_stmt.order_by(col(SpanTable.start_time).asc())
            spans = (await session.exec(spans_stmt)).all()

            # Build hierarchical span tree
            span_tree = _build_span_tree(spans)

            # Return trace with span tree in frontend-compatible format
            return {
                "id": str(trace.id),
                "name": trace.name,
                "status": trace.status.value if trace.status else "success",
                "startTime": trace.start_time.isoformat() if trace.start_time else "",
                "endTime": trace.end_time.isoformat() if trace.end_time else None,
                "totalLatencyMs": trace.total_latency_ms,
                "totalTokens": trace.total_tokens,
                "totalCost": trace.total_cost,
                "flowId": str(trace.flow_id),
                "sessionId": trace.session_id,
                "spans": span_tree,  # Return all root spans as flat list
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"Error getting trace: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        "status": span.status.value if span.status else "success",
        "startTime": span.start_time.isoformat() if span.start_time else "",
        "endTime": span.end_time.isoformat() if span.end_time else None,
        "latencyMs": span.latency_ms,
        "inputs": span.inputs or {},
        "outputs": span.outputs or {},
        "error": span.error,
        "modelName": span.model_name,
        "tokenUsage": token_usage,
    }


@router.delete("/{trace_id}", status_code=204, dependencies=[Depends(get_current_active_user)])
async def delete_trace(
    trace_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete a trace and all its spans.

    Args:
        trace_id: The trace ID to delete
    """
    from lfx.services.deps import session_scope

    try:
        async with session_scope() as session:
            stmt = select(TraceTable).where(TraceTable.id == trace_id)
            trace = (await session.exec(stmt)).first()

            if not trace:
                raise HTTPException(status_code=404, detail="Trace not found")

            # Delete trace (cascade will delete spans)
            await session.delete(trace)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("", status_code=204, dependencies=[Depends(get_current_active_user)])
async def delete_traces_by_flow(
    flow_id: Annotated[UUID, Query()],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete all traces for a flow.

    Args:
        flow_id: The flow ID to delete traces for
    """
    from lfx.services.deps import session_scope

    try:
        async with session_scope() as session:
            # Get all traces for this flow
            stmt = select(TraceTable).where(TraceTable.flow_id == flow_id)
            traces = (await session.exec(stmt)).all()

            # Delete all traces (cascade will delete spans)
            for trace in traces:
                await session.delete(trace)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
