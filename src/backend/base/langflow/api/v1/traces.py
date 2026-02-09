"""API endpoints for execution traces.

This module provides endpoints for retrieving execution trace data
from the native tracer, enabling the Trace View in the frontend.
"""

import asyncio
import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlmodel import col, select

from langflow.services.auth.utils import get_current_active_user
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


async def _fetch_traces(
    flow_id: UUID | None,
    session_id: str | None,
    status: SpanStatus | None,
) -> dict[str, Any]:
    """Internal function to fetch traces with proper session management."""
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
        trace_list = [
            {
                "id": str(trace.id),
                "name": trace.name,
                "status": trace.status.value if trace.status else "success",
                "startTime": trace.start_time.isoformat() if trace.start_time else "",
                "totalLatencyMs": trace.total_latency_ms,
                "totalTokens": trace.total_tokens,
                "totalCost": trace.total_cost,
                "flowId": str(trace.flow_id),
            }
            for trace in traces
        ]

        return {"traces": trace_list, "total": len(trace_list)}


@router.get("", dependencies=[Depends(get_current_active_user)])
async def get_traces(
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: ARG001
    flow_id: Annotated[UUID | None, Query()] = None,
    session_id: Annotated[str | None, Query()] = None,
    status: Annotated[SpanStatus | None, Query()] = None,
) -> dict[str, Any]:
    """Get list of traces for a flow.

    Args:
        current_user: Authenticated user (required for authorization)
        flow_id: Filter by flow ID
        session_id: Filter by session ID
        status: Filter by trace status

    Returns:
        List of traces
    """
    try:
        # Use timeout to prevent hanging if database has issues
        return await asyncio.wait_for(
            _fetch_traces(flow_id, session_id, status),
            timeout=DB_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("Traces query timed out after %ss (table may not exist or DB is slow)", DB_TIMEOUT)
        return {"traces": [], "total": 0}
    except (OperationalError, ProgrammingError) as e:
        # Table doesn't exist or other SQL error
        logger.debug("Database error getting traces (table may not exist): %s", e)
        return {"traces": [], "total": 0}
    except Exception as e:  # noqa: BLE001
        # Log error but return empty list - broad catch needed for graceful degradation
        logger.debug("Error getting traces: %s", e)
        return {"traces": [], "total": 0}


async def _fetch_single_trace(trace_id: UUID) -> dict[str, Any] | None:
    """Internal function to fetch a single trace with its spans."""
    async with session_scope() as session:
        # Get trace (simple query without JOIN for now)
        stmt = select(TraceTable).where(TraceTable.id == trace_id)
        trace = (await session.exec(stmt)).first()

        if not trace:
            return None

        # Get all spans for this trace
        spans_stmt = select(SpanTable).where(SpanTable.trace_id == trace_id)
        spans_stmt = spans_stmt.order_by(col(SpanTable.start_time).asc())
        spans = (await session.exec(spans_stmt)).all()

        # Build hierarchical span tree
        span_tree = _build_span_tree(list(spans))

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


@router.get("/{trace_id}")
async def get_trace(
    trace_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: ARG001
) -> dict[str, Any]:
    """Get a single trace with its hierarchical span tree.

    Args:
        trace_id: The ID of the trace to retrieve.
        current_user: The authenticated user (required for authorization).

    Returns:
        Dictionary containing the trace and its hierarchical span tree.

    Args:
        trace_id: The trace ID to retrieve

    Returns:
        Trace with nested span tree structured for frontend consumption
    """
    try:
        result = await asyncio.wait_for(
            _fetch_single_trace(trace_id),
            timeout=DB_TIMEOUT,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Trace not found")
        return result  # noqa: TRY300
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.warning("Single trace query timed out after %ss", DB_TIMEOUT)
        raise HTTPException(status_code=504, detail="Database query timed out") from None
    except (OperationalError, ProgrammingError) as e:
        logger.debug("Database error getting trace: %s", e)
        raise HTTPException(status_code=500, detail="Database error") from e
    except Exception as e:
        logger.debug("Error getting trace: %s", e)
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
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: ARG001
) -> None:
    """Delete a trace and all its spans.

    Args:
        trace_id: The ID of the trace to delete.
        current_user: The authenticated user (required for authorization).

    Args:
        trace_id: The trace ID to delete
    """
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
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: ARG001
) -> None:
    """Delete all traces for a flow.

    Args:
        flow_id: The ID of the flow whose traces should be deleted.
        current_user: The authenticated user (required for authorization).

    Args:
        flow_id: The flow ID to delete traces for
    """
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
