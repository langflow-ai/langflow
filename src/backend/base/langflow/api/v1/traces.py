"""API endpoints for execution traces.

This module provides HTTP handlers for retrieving and deleting execution trace
data from the native tracer, enabling the Trace View in the frontend.

Business logic (query/aggregation) lives in:
    langflow.services.tracing.repository

Data transformation logic lives in:
    langflow.services.tracing.formatting
"""

import asyncio
import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlmodel import col, select

from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.traces.model import (
    SpanStatus,
    TraceListResponse,
    TraceRead,
    TraceTable,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.tracing.repository import fetch_single_trace, fetch_traces
from langflow.services.tracing.validation import sanitize_query_string

logger = logging.getLogger(__name__)

# Keeps the API responsive when the trace table doesn't exist yet or the DB is slow at startup.
DB_TIMEOUT = 5.0

router = APIRouter(prefix="/monitor/traces", tags=["Traces"])


@router.get("", response_model_by_alias=True)
async def get_traces(
    current_user: Annotated[User, Depends(get_current_active_user)],
    flow_id: Annotated[UUID | None, Query()] = None,
    session_id: Annotated[str | None, Query()] = None,
    status: Annotated[SpanStatus | None, Query()] = None,
    query: Annotated[str | None, Query()] = None,
    start_time: Annotated[datetime | None, Query()] = None,
    end_time: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=0)] = 1,
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
        sanitized_query = sanitize_query_string(query)
        # Frontend uses 0-based pages; repository expects 1-based.
        effective_page = max(page, 1)
        return await asyncio.wait_for(
            fetch_traces(
                current_user.id,
                flow_id,
                session_id,
                status,
                sanitized_query,
                start_time,
                end_time,
                effective_page,
                size,
            ),
            timeout=DB_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("Traces query timed out after %ss (table may not exist or DB is slow)", DB_TIMEOUT)
        return TraceListResponse(traces=[], total=0, pages=0)
    except (OperationalError, ProgrammingError) as e:
        logger.debug("Database error getting traces (table may not exist): %s", e)
        return TraceListResponse(traces=[], total=0, pages=0)
    except Exception:
        logger.exception("Unexpected error getting traces")
        raise


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
            fetch_single_trace(current_user.id, trace_id),
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
            stmt = (
                select(TraceTable)
                .join(Flow, col(TraceTable.flow_id) == col(Flow.id))
                .where(col(TraceTable.id) == trace_id)
                .where(col(Flow.user_id) == current_user.id)
            )
            trace = (await session.exec(stmt)).first()

            if not trace:
                raise HTTPException(status_code=404, detail="Trace not found")

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
            flow_stmt = select(Flow).where(col(Flow.id) == flow_id).where(col(Flow.user_id) == current_user.id)
            flow = (await session.exec(flow_stmt)).first()

            if not flow:
                raise HTTPException(status_code=404, detail="Flow not found")

            # Single statement avoids N+1 deletes when a flow has many traces.
            delete_stmt = sa.delete(TraceTable).where(col(TraceTable.flow_id) == flow_id)
            await session.execute(delete_stmt)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting traces by flow")
        raise HTTPException(status_code=500, detail="Internal server error") from e
