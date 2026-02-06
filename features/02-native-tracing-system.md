# Feature 2: Native Tracing System (Backend)

## Summary

Implements a built-in tracing system that stores component-level and LangChain-level execution traces directly in Langflow's database. This enables a Trace View in the frontend without requiring external observability services like LangSmith or LangFuse. The system captures hierarchical spans (component executions, LLM calls, tool calls, retriever operations) organized into traces, with support for token usage tracking, latency measurement, and error recording.

## Dependencies

- SQLModel / SQLAlchemy (existing)
- Alembic migrations (existing)
- LangChain callbacks base (existing)
- `langflow.serialization` module (existing)
- Enabled by default; disable with `LANGFLOW_NATIVE_TRACING=false`

## Implementation Notes

- The `NativeTracer` class extends `BaseTracer` and is initialized alongside other tracers (LangSmith, LangFuse, etc.) in `TracingService`.
- Traces are flushed to the database asynchronously at the end of execution via `_flush_to_database()`, with `TracingService.end_all_tracers()` awaiting the flush.
- The `NativeCallbackHandler` captures LangChain-level events (LLM start/end, chain start/end, tool start/end, retriever start/end) and converts them to spans.
- The API endpoints (`/api/v1/traces`) provide CRUD operations for traces with timeout protection and graceful degradation if tables don't exist.
- The migration creates `trace` and `span` tables with proper foreign key relationships, indexes, and enum types.
- Tables are auto-created in development mode via `_ensure_tables_exist()` for convenience.

---

## File Diffs

### `src/backend/base/langflow/api/v1/traces.py` (new)

```diff
diff --git a/src/backend/base/langflow/api/v1/traces.py b/src/backend/base/langflow/api/v1/traces.py
new file mode 100644
index 0000000000..95e51eb632
--- /dev/null
+++ b/src/backend/base/langflow/api/v1/traces.py
@@ -0,0 +1,292 @@
+"""API endpoints for execution traces.
+
+This module provides endpoints for retrieving execution trace data
+from the native tracer, enabling the Trace View in the frontend.
+"""
+
+import asyncio
+import logging
+from typing import Annotated, Any
+from uuid import UUID
+
+from fastapi import APIRouter, Depends, HTTPException, Query
+from sqlalchemy.exc import OperationalError, ProgrammingError
+from sqlmodel import col, select
+
+from langflow.services.auth.utils import get_current_active_user
+from langflow.services.database.models.traces.model import (
+    SpanStatus,
+    SpanTable,
+    TraceTable,
+)
+from langflow.services.database.models.user.model import User
+from langflow.services.deps import session_scope
+
+logger = logging.getLogger(__name__)
+
+# Timeout for database operations (in seconds)
+DB_TIMEOUT = 5.0
+
+router = APIRouter(prefix="/traces", tags=["Traces"])
+
+
+async def _fetch_traces(
+    flow_id: UUID | None,
+    session_id: str | None,
+    status: SpanStatus | None,
+) -> dict[str, Any]:
+    """Internal function to fetch traces with proper session management."""
+    async with session_scope() as session:
+        # Simple query - just get traces for this flow
+        stmt = select(TraceTable)
+
+        if flow_id:
+            stmt = stmt.where(TraceTable.flow_id == flow_id)
+        if session_id:
+            stmt = stmt.where(TraceTable.session_id == session_id)
+        if status:
+            stmt = stmt.where(TraceTable.status == status)
+
+        # Order by most recent first
+        stmt = stmt.order_by(col(TraceTable.start_time).desc())
+        stmt = stmt.limit(10)
+
+        traces = (await session.exec(stmt)).all()
+
+        # Convert to response format
+        trace_list = []
+        for trace in traces:
+            trace_list.append(
+                {
+                    "id": str(trace.id),
+                    "name": trace.name,
+                    "status": trace.status.value if trace.status else "success",
+                    "startTime": trace.start_time.isoformat() if trace.start_time else "",
+                    "totalLatencyMs": trace.total_latency_ms,
+                    "totalTokens": trace.total_tokens,
+                    "totalCost": trace.total_cost,
+                    "flowId": str(trace.flow_id),
+                }
+            )
+
+        return {"traces": trace_list, "total": len(trace_list)}
+
+
+@router.get("", dependencies=[Depends(get_current_active_user)])
+async def get_traces(
+    current_user: Annotated[User, Depends(get_current_active_user)],
+    flow_id: Annotated[UUID | None, Query()] = None,
+    session_id: Annotated[str | None, Query()] = None,
+    status: Annotated[SpanStatus | None, Query()] = None,
+) -> dict[str, Any]:
+    """Get list of traces for a flow.
+
+    Args:
+        flow_id: Filter by flow ID
+        session_id: Filter by session ID
+        status: Filter by trace status
+
+    Returns:
+        List of traces
+    """
+    try:
+        # Use timeout to prevent hanging if database has issues
+        return await asyncio.wait_for(
+            _fetch_traces(flow_id, session_id, status),
+            timeout=DB_TIMEOUT,
+        )
+    except asyncio.TimeoutError:
+        logger.warning(f"Traces query timed out after {DB_TIMEOUT}s (table may not exist or DB is slow)")
+        return {"traces": [], "total": 0}
+    except (OperationalError, ProgrammingError) as e:
+        # Table doesn't exist or other SQL error
+        logger.debug(f"Database error getting traces (table may not exist): {e}")
+        return {"traces": [], "total": 0}
+    except Exception as e:
+        # Log error but return empty list
+        logger.debug(f"Error getting traces: {e}")
+        return {"traces": [], "total": 0}
+
+
+async def _fetch_single_trace(trace_id: UUID) -> dict[str, Any] | None:
+    """Internal function to fetch a single trace with its spans."""
+    async with session_scope() as session:
+        # Get trace (simple query without JOIN for now)
+        stmt = select(TraceTable).where(TraceTable.id == trace_id)
+        trace = (await session.exec(stmt)).first()
+
+        if not trace:
+            return None
+
+        # Get all spans for this trace
+        spans_stmt = select(SpanTable).where(SpanTable.trace_id == trace_id)
+        spans_stmt = spans_stmt.order_by(col(SpanTable.start_time).asc())
+        spans = (await session.exec(spans_stmt)).all()
+
+        # Build hierarchical span tree
+        span_tree = _build_span_tree(spans)
+
+        # Return trace with span tree in frontend-compatible format
+        return {
+            "id": str(trace.id),
+            "name": trace.name,
+            "status": trace.status.value if trace.status else "success",
+            "startTime": trace.start_time.isoformat() if trace.start_time else "",
+            "endTime": trace.end_time.isoformat() if trace.end_time else None,
+            "totalLatencyMs": trace.total_latency_ms,
+            "totalTokens": trace.total_tokens,
+            "totalCost": trace.total_cost,
+            "flowId": str(trace.flow_id),
+            "sessionId": trace.session_id,
+            "spans": span_tree,  # Return all root spans as flat list
+        }
+
+
+@router.get("/{trace_id}")
+async def get_trace(
+    trace_id: UUID,
+    current_user: Annotated[User, Depends(get_current_active_user)],
+) -> dict[str, Any]:
+    """Get a single trace with its hierarchical span tree.
+
+    Args:
+        trace_id: The trace ID to retrieve
+
+    Returns:
+        Trace with nested span tree structured for frontend consumption
+    """
+    try:
+        result = await asyncio.wait_for(
+            _fetch_single_trace(trace_id),
+            timeout=DB_TIMEOUT,
+        )
+        if result is None:
+            raise HTTPException(status_code=404, detail="Trace not found")
+        return result
+    except HTTPException:
+        raise
+    except asyncio.TimeoutError:
+        logger.warning(f"Single trace query timed out after {DB_TIMEOUT}s")
+        raise HTTPException(status_code=504, detail="Database query timed out") from None
+    except (OperationalError, ProgrammingError) as e:
+        logger.debug(f"Database error getting trace: {e}")
+        raise HTTPException(status_code=500, detail="Database error") from e
+    except Exception as e:
+        logger.debug(f"Error getting trace: {e}")
+        raise HTTPException(status_code=500, detail=str(e)) from e
+
+
+def _build_span_tree(spans: list[SpanTable]) -> list[dict[str, Any]]:
+    """Build a hierarchical span tree from flat span list.
+
+    Args:
+        spans: List of SpanTable records
+
+    Returns:
+        List of root spans with nested children
+    """
+    if not spans:
+        return []
+
+    # Create span dict lookup
+    span_dict: dict[UUID, dict[str, Any]] = {}
+    for span in spans:
+        span_data = _span_to_dict(span)
+        span_data["children"] = []
+        span_dict[span.id] = span_data
+
+    # Build tree by linking children to parents
+    root_spans = []
+    for span in spans:
+        span_data = span_dict[span.id]
+        if span.parent_span_id and span.parent_span_id in span_dict:
+            span_dict[span.parent_span_id]["children"].append(span_data)
+        else:
+            root_spans.append(span_data)
+
+    return root_spans
+
+
+def _span_to_dict(span: SpanTable) -> dict[str, Any]:
+    """Convert a SpanTable to a frontend-compatible dictionary.
+
+    Args:
+        span: SpanTable record
+
+    Returns:
+        Dictionary with frontend-compatible field names
+    """
+    token_usage = None
+    if span.total_tokens:
+        token_usage = {
+            "promptTokens": span.prompt_tokens or 0,
+            "completionTokens": span.completion_tokens or 0,
+            "totalTokens": span.total_tokens,
+            "cost": span.cost or 0,
+        }
+
+    return {
+        "id": str(span.id),
+        "name": span.name,
+        "type": span.span_type.value if span.span_type else "chain",
+        "status": span.status.value if span.status else "success",
+        "startTime": span.start_time.isoformat() if span.start_time else "",
+        "endTime": span.end_time.isoformat() if span.end_time else None,
+        "latencyMs": span.latency_ms,
+        "inputs": span.inputs or {},
+        "outputs": span.outputs or {},
+        "error": span.error,
+        "modelName": span.model_name,
+        "tokenUsage": token_usage,
+    }
+
+
+@router.delete("/{trace_id}", status_code=204, dependencies=[Depends(get_current_active_user)])
+async def delete_trace(
+    trace_id: UUID,
+    current_user: Annotated[User, Depends(get_current_active_user)],
+) -> None:
+    """Delete a trace and all its spans.
+
+    Args:
+        trace_id: The trace ID to delete
+    """
+    try:
+        async with session_scope() as session:
+            stmt = select(TraceTable).where(TraceTable.id == trace_id)
+            trace = (await session.exec(stmt)).first()
+
+            if not trace:
+                raise HTTPException(status_code=404, detail="Trace not found")
+
+            # Delete trace (cascade will delete spans)
+            await session.delete(trace)
+    except HTTPException:
+        raise
+    except Exception as e:
+        raise HTTPException(status_code=500, detail=str(e)) from e
+
+
+@router.delete("", status_code=204, dependencies=[Depends(get_current_active_user)])
+async def delete_traces_by_flow(
+    flow_id: Annotated[UUID, Query()],
+    current_user: Annotated[User, Depends(get_current_active_user)],
+) -> None:
+    """Delete all traces for a flow.
+
+    Args:
+        flow_id: The flow ID to delete traces for
+    """
+    try:
+        async with session_scope() as session:
+            # Get all traces for this flow
+            stmt = select(TraceTable).where(TraceTable.flow_id == flow_id)
+            traces = (await session.exec(stmt)).all()
+
+            # Delete all traces (cascade will delete spans)
+            for trace in traces:
+                await session.delete(trace)
+    except HTTPException:
+        raise
+    except Exception as e:
+        raise HTTPException(status_code=500, detail=str(e)) from e
```

### `src/backend/base/langflow/services/database/models/traces/__init__.py` (new)

```diff
diff --git a/src/backend/base/langflow/services/database/models/traces/__init__.py b/src/backend/base/langflow/services/database/models/traces/__init__.py
new file mode 100644
index 0000000000..362ef2ef93
--- /dev/null
+++ b/src/backend/base/langflow/services/database/models/traces/__init__.py
@@ -0,0 +1,3 @@
+from .model import SpanTable, TraceTable
+
+__all__ = ["SpanTable", "TraceTable"]
```

### `src/backend/base/langflow/services/database/models/traces/model.py` (new)

```diff
diff --git a/src/backend/base/langflow/services/database/models/traces/model.py b/src/backend/base/langflow/services/database/models/traces/model.py
new file mode 100644
index 0000000000..8910753d3a
--- /dev/null
+++ b/src/backend/base/langflow/services/database/models/traces/model.py
@@ -0,0 +1,184 @@
+from datetime import datetime, timezone
+from enum import Enum
+from typing import Any, Optional
+from uuid import UUID, uuid4
+
+from pydantic import field_serializer, field_validator
+from sqlmodel import JSON, Column, Field, Relationship, SQLModel, Text
+
+from langflow.serialization.serialization import serialize
+
+
+class SpanType(str, Enum):
+    """Types of spans that can be recorded."""
+
+    CHAIN = "chain"
+    LLM = "llm"
+    TOOL = "tool"
+    RETRIEVER = "retriever"
+    EMBEDDING = "embedding"
+    PARSER = "parser"
+    AGENT = "agent"
+
+
+class SpanStatus(str, Enum):
+    """Status of a span execution."""
+
+    SUCCESS = "success"
+    ERROR = "error"
+    RUNNING = "running"
+
+
+class TraceBase(SQLModel):
+    """Base model for traces."""
+
+    name: str = Field(nullable=False, description="Name of the trace (usually flow name)")
+    status: SpanStatus = Field(default=SpanStatus.RUNNING, description="Overall trace status")
+    start_time: datetime = Field(
+        default_factory=lambda: datetime.now(timezone.utc),
+        description="When the trace started",
+    )
+    end_time: datetime | None = Field(default=None, description="When the trace ended")
+    total_latency_ms: int = Field(default=0, description="Total execution time in milliseconds")
+    total_tokens: int = Field(default=0, description="Total tokens used across all LLM calls")
+    total_cost: float = Field(default=0.0, description="Estimated total cost")
+    flow_id: UUID = Field(index=True, description="ID of the flow this trace belongs to")
+    session_id: str | None = Field(default=None, index=True, description="Session ID for grouping traces")
+
+    class Config:
+        arbitrary_types_allowed = True
+
+    @field_validator("flow_id", mode="before")
+    @classmethod
+    def validate_flow_id(cls, value):
+        if value is None:
+            return value
+        if isinstance(value, str):
+            value = UUID(value)
+        return value
+
+
+class TraceTable(TraceBase, table=True):  # type: ignore[call-arg]
+    """Database table for storing execution traces."""
+
+    __tablename__ = "trace"
+
+    id: UUID = Field(default_factory=uuid4, primary_key=True)
+    spans: list["SpanTable"] = Relationship(
+        back_populates="trace",
+        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
+    )
+
+
+class TraceRead(TraceBase):
+    """Read model for traces with spans."""
+
+    id: UUID
+    spans: list["SpanRead"] = []
+
+
+class TraceCreate(SQLModel):
+    """Create model for traces."""
+
+    name: str
+    flow_id: UUID
+    session_id: str | None = None
+
+
+class SpanBase(SQLModel):
+    """Base model for spans (individual execution steps)."""
+
+    name: str = Field(nullable=False, description="Name of the span (component/operation name)")
+    span_type: SpanType = Field(default=SpanType.CHAIN, description="Type of operation")
+    status: SpanStatus = Field(default=SpanStatus.RUNNING, description="Execution status")
+    start_time: datetime = Field(
+        default_factory=lambda: datetime.now(timezone.utc),
+        description="When the span started",
+    )
+    end_time: datetime | None = Field(default=None, description="When the span ended")
+    latency_ms: int = Field(default=0, description="Execution time in milliseconds")
+    inputs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
+    outputs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
+    error: str | None = Field(default=None, sa_column=Column(Text), description="Error message if failed")
+    model_name: str | None = Field(default=None, description="Model name for LLM spans")
+    prompt_tokens: int | None = Field(default=None, description="Number of prompt tokens")
+    completion_tokens: int | None = Field(default=None, description="Number of completion tokens")
+    total_tokens: int | None = Field(default=None, description="Total tokens used")
+    cost: float | None = Field(default=None, description="Estimated cost for this span")
+
+    class Config:
+        arbitrary_types_allowed = True
+
+    @field_serializer("inputs")
+    def serialize_inputs(self, data) -> dict | None:
+        if data is None:
+            return None
+        return serialize(data)
+
+    @field_serializer("outputs")
+    def serialize_outputs(self, data) -> dict | None:
+        if data is None:
+            return None
+        return serialize(data)
+
+
+class SpanTable(SpanBase, table=True):  # type: ignore[call-arg]
+    """Database table for storing execution spans."""
+
+    __tablename__ = "span"
+
+    id: UUID = Field(default_factory=uuid4, primary_key=True)
+    trace_id: UUID = Field(foreign_key="trace.id", index=True, description="Parent trace ID")
+    parent_span_id: UUID | None = Field(
+        default=None,
+        foreign_key="span.id",
+        index=True,
+        description="Parent span ID for nested spans",
+    )
+
+    # Relationships
+    trace: TraceTable = Relationship(back_populates="spans")
+    parent: Optional["SpanTable"] = Relationship(
+        back_populates="children",
+        sa_relationship_kwargs={"remote_side": "SpanTable.id"},
+    )
+    children: list["SpanTable"] = Relationship(back_populates="parent")
+
+
+class SpanRead(SpanBase):
+    """Read model for spans with nested children."""
+
+    id: UUID
+    trace_id: UUID
+    parent_span_id: UUID | None = None
+    children: list["SpanRead"] = []
+
+
+class SpanCreate(SQLModel):
+    """Create model for spans."""
+
+    name: str
+    span_type: SpanType = SpanType.CHAIN
+    trace_id: UUID
+    parent_span_id: UUID | None = None
+    inputs: dict[str, Any] | None = None
+    model_name: str | None = None
+
+
+class SpanUpdate(SQLModel):
+    """Update model for completing spans."""
+
+    status: SpanStatus | None = None
+    end_time: datetime | None = None
+    latency_ms: int | None = None
+    outputs: dict[str, Any] | None = None
+    error: str | None = None
+    prompt_tokens: int | None = None
+    completion_tokens: int | None = None
+    total_tokens: int | None = None
+    cost: float | None = None
+
+
+# Update forward references
+TraceRead.model_rebuild()
+SpanRead.model_rebuild()
```

### `src/backend/base/langflow/alembic/versions/3671f35245e5_add_trace_and_span_tables.py` (new)

```diff
diff --git a/src/backend/base/langflow/alembic/versions/3671f35245e5_add_trace_and_span_tables.py b/src/backend/base/langflow/alembic/versions/3671f35245e5_add_trace_and_span_tables.py
new file mode 100644
index 0000000000..2f79507c94
--- /dev/null
+++ b/src/backend/base/langflow/alembic/versions/3671f35245e5_add_trace_and_span_tables.py
@@ -0,0 +1,107 @@
+"""Add trace and span tables for native tracing
+
+Revision ID: 3671f35245e5
+Revises: fd531f8868b1
+Create Date: 2026-01-28 04:10:00.000000
+
+"""
+
+from collections.abc import Sequence
+
+import sqlalchemy as sa
+import sqlmodel
+from alembic import op
+
+from langflow.utils import migration
+
+# revision identifiers, used by Alembic.
+revision: str = "3671f35245e5"
+down_revision: str | None = "182e5471b900"
+branch_labels: str | Sequence[str] | None = None
+depends_on: str | Sequence[str] | None = None
+
+
+def upgrade() -> None:
+    conn = op.get_bind()
+
+    # Create trace table
+    if not migration.table_exists("trace", conn):
+        op.create_table(
+            "trace",
+            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
+            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
+            sa.Column(
+                "status",
+                sa.Enum("SUCCESS", "ERROR", "RUNNING", name="spanstatus"),
+                nullable=False,
+                server_default="RUNNING",
+            ),
+            sa.Column("start_time", sa.DateTime(), nullable=False),
+            sa.Column("end_time", sa.DateTime(), nullable=True),
+            sa.Column("total_latency_ms", sa.Integer(), nullable=False, server_default="0"),
+            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
+            sa.Column("total_cost", sa.Float(), nullable=False, server_default="0.0"),
+            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
+            sa.Column("session_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
+            sa.PrimaryKeyConstraint("id"),
+        )
+        op.create_index("ix_trace_flow_id", "trace", ["flow_id"])
+        op.create_index("ix_trace_session_id", "trace", ["session_id"])
+
+    # Create span table
+    if not migration.table_exists("span", conn):
+        op.create_table(
+            "span",
+            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
+            sa.Column("trace_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
+            sa.Column("parent_span_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=True),
+            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
+            sa.Column(
+                "span_type",
+                sa.Enum("CHAIN", "LLM", "TOOL", "RETRIEVER", "EMBEDDING", "PARSER", "AGENT", name="spantype"),
+                nullable=False,
+                server_default="CHAIN",
+            ),
+            sa.Column(
+                "status",
+                sa.Enum("SUCCESS", "ERROR", "RUNNING", name="spanstatus"),
+                nullable=False,
+                server_default="RUNNING",
+            ),
+            sa.Column("start_time", sa.DateTime(), nullable=False),
+            sa.Column("end_time", sa.DateTime(), nullable=True),
+            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
+            sa.Column("inputs", sa.JSON(), nullable=True),
+            sa.Column("outputs", sa.JSON(), nullable=True),
+            sa.Column("error", sa.Text(), nullable=True),
+            sa.Column("model_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
+            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
+            sa.Column("completion_tokens", sa.Integer(), nullable=True),
+            sa.Column("total_tokens", sa.Integer(), nullable=True),
+            sa.Column("cost", sa.Float(), nullable=True),
+            sa.PrimaryKeyConstraint("id"),
+            sa.ForeignKeyConstraint(["trace_id"], ["trace.id"], name="fk_span_trace_id_trace"),
+            sa.ForeignKeyConstraint(["parent_span_id"], ["span.id"], name="fk_span_parent_span_id_span"),
+        )
+        op.create_index("ix_span_trace_id", "span", ["trace_id"])
+        op.create_index("ix_span_parent_span_id", "span", ["parent_span_id"])
+
+
+def downgrade() -> None:
+    conn = op.get_bind()
+
+    # Drop span table first (depends on trace)
+    if migration.table_exists("span", conn):
+        op.drop_index("ix_span_parent_span_id", table_name="span")
+        op.drop_index("ix_span_trace_id", table_name="span")
+        op.drop_table("span")
+
+    # Drop trace table
+    if migration.table_exists("trace", conn):
+        op.drop_index("ix_trace_session_id", table_name="trace")
+        op.drop_index("ix_trace_flow_id", table_name="trace")
+        op.drop_table("trace")
+
+    # Drop enums
+    op.execute("DROP TYPE IF EXISTS spantype")
+    op.execute("DROP TYPE IF EXISTS spanstatus")
```

### `src/backend/base/langflow/services/tracing/native.py` (new)

```diff
diff --git a/src/backend/base/langflow/services/tracing/native.py b/src/backend/base/langflow/services/tracing/native.py
new file mode 100644
index 0000000000..50e207a238
--- /dev/null
+++ b/src/backend/base/langflow/services/tracing/native.py
@@ -0,0 +1,469 @@
+"""Native tracer for storing execution traces in the database.
+
+This module provides a tracer that stores component-level and LangChain-level
+execution traces directly in Langflow's database, enabling the Trace View
+without requiring external services like LangSmith or LangFuse.
+"""
+
+from __future__ import annotations
+
+import asyncio
+import os
+from collections import OrderedDict
+from datetime import datetime, timezone
+from typing import TYPE_CHECKING, Any
+
+from lfx.log.logger import logger
+from typing_extensions import override
+
+from langflow.serialization.serialization import serialize
+from langflow.services.database.models.traces.model import SpanStatus, SpanType
+from langflow.services.tracing.base import BaseTracer
+
+if TYPE_CHECKING:
+    from collections.abc import Sequence
+    from uuid import UUID
+
+    from langchain.callbacks.base import BaseCallbackHandler
+    from lfx.graph.vertex.base import Vertex
+
+    from langflow.services.tracing.schema import Log
+
+
+class NativeTracer(BaseTracer):
+    """Tracer that stores execution traces in Langflow's database.
+
+    This tracer captures:
+    - Component-level traces (via add_trace/end_trace)
+    - LangChain-level traces (via get_langchain_callback)
+
+    Enabled by default. Disable with LANGFLOW_NATIVE_TRACING=false if needed.
+    """
+
+    def __init__(
+        self,
+        trace_name: str,
+        trace_type: str,
+        project_name: str,
+        trace_id: UUID,
+        user_id: str | None = None,
+        session_id: str | None = None,
+    ) -> None:
+        """Initialize the native tracer.
+
+        Args:
+            trace_name: Name of the trace (usually flow name + ID)
+            trace_type: Type of trace (e.g., "chain")
+            project_name: Project name for organization
+            trace_id: Unique ID for this trace run
+            user_id: Optional user ID
+            session_id: Optional session ID for grouping traces
+        """
+        self.trace_name = trace_name
+        self.trace_type = trace_type
+        self.project_name = project_name
+        self.trace_id = trace_id
+        self.user_id = user_id
+        self.session_id = session_id
+        self.flow_id = trace_name.split(" - ")[-1] if " - " in trace_name else trace_name
+
+        # Track active component spans (in-memory)
+        self.spans: dict[str, dict[str, Any]] = OrderedDict()
+
+        # Track completed spans for batch database write
+        self.completed_spans: list[dict[str, Any]] = []
+
+        # Track LangChain spans (from callback handler)
+        self.langchain_spans: dict[UUID, dict[str, Any]] = {}
+
+        # Track the currently active component span ID (for parent-child linking)
+        self._current_component_id: str | None = None
+
+        # Trace start time
+        self._start_time = datetime.now(tz=timezone.utc)
+
+        # Flush task (set by end() method, awaited by TracingService)
+        self._flush_task: asyncio.Task | None = None
+
+        # Check if native tracing is enabled
+        self._ready = self._is_enabled()
+
+    @staticmethod
+    def _is_enabled() -> bool:
+        """Check if native tracing is enabled (default: true)."""
+        # Enabled by default, can be disabled with LANGFLOW_NATIVE_TRACING=false
+        return os.getenv("LANGFLOW_NATIVE_TRACING", "true").lower() not in ("false", "0", "no")
+
+    @property
+    def ready(self) -> bool:
+        """Return whether the tracer is ready to use."""
+        return self._ready
+
+    @override
+    def add_trace(
+        self,
+        trace_id: str,
+        trace_name: str,
+        trace_type: str,
+        inputs: dict[str, Any],
+        metadata: dict[str, Any] | None = None,
+        vertex: Vertex | None = None,
+    ) -> None:
+        """Add a component-level trace span.
+
+        Args:
+            trace_id: Component ID
+            trace_name: Component name + ID
+            trace_type: Type of component
+            inputs: Input data
+            metadata: Optional metadata
+            vertex: Optional vertex reference
+        """
+        if not self._ready:
+            return
+
+        start_time = datetime.now(tz=timezone.utc)
+
+        # Store span info for later completion
+        name = trace_name.removesuffix(f" ({trace_id})")
+        self.spans[trace_id] = {
+            "id": trace_id,
+            "name": name,
+            "trace_type": trace_type,
+            "inputs": serialize(inputs),
+            "metadata": metadata or {},
+            "start_time": start_time,
+        }
+
+        # Track current component for LangChain callback parent linking
+        self._current_component_id = trace_id
+
+    @override
+    def end_trace(
+        self,
+        trace_id: str,
+        trace_name: str,
+        outputs: dict[str, Any] | None = None,
+        error: Exception | None = None,
+        logs: Sequence[Log | dict] = (),
+    ) -> None:
+        """End a component-level trace span.
+
+        Args:
+            trace_id: Component ID
+            trace_name: Component name
+            outputs: Output data
+            error: Optional error
+            logs: Optional logs
+        """
+        if not self._ready:
+            return
+
+        end_time = datetime.now(tz=timezone.utc)
+
+        span_info = self.spans.pop(trace_id, None)
+        if not span_info:
+            return
+
+        start_time = span_info["start_time"]
+        latency_ms = int((end_time - start_time).total_seconds() * 1000)
+
+        # Prepare output with optional error and logs
+        output_data: dict[str, Any] = {}
+        if outputs:
+            output_data.update(outputs)
+        if error:
+            output_data["error"] = str(error)
+        if logs:
+            output_data["logs"] = [log if isinstance(log, dict) else log.model_dump() for log in logs]
+
+        # Store completed span for batch write
+        self.completed_spans.append(
+            {
+                "id": trace_id,
+                "name": span_info["name"],
+                "span_type": self._map_trace_type(span_info["trace_type"]),
+                "inputs": span_info["inputs"],
+                "outputs": serialize(output_data) if output_data else None,
+                "start_time": start_time,
+                "end_time": end_time,
+                "latency_ms": latency_ms,
+                "status": SpanStatus.ERROR if error else SpanStatus.SUCCESS,
+                "error": str(error) if error else None,
+            }
+        )
+
+        # Clear current component ID
+        self._current_component_id = None
+
+    @override
+    def end(
+        self,
+        inputs: dict[str, Any],
+        outputs: dict[str, Any],
+        error: Exception | None = None,
+        metadata: dict[str, Any] | None = None,
+    ) -> None:
+        """End the entire trace.
+
+        Args:
+            inputs: All accumulated inputs
+            outputs: All accumulated outputs
+            error: Optional error
+            metadata: Optional metadata
+        """
+        if not self._ready:
+            return
+
+        # Schedule async database write - store task so TracingService can await it
+        try:
+            loop = asyncio.get_running_loop()
+            self._flush_task = loop.create_task(self._flush_to_database(error))
+        except RuntimeError:
+            # No running event loop, try to run synchronously
+            logger.warning("No running event loop, skipping database flush")
+
+    async def wait_for_flush(self) -> None:
+        """Wait for the flush task to complete.
+
+        Called by TracingService after end() to ensure database write completes.
+        """
+        if self._flush_task is not None:
+            try:
+                await self._flush_task
+            except Exception as e:  # noqa: BLE001
+                logger.debug(f"Error waiting for flush: {e}")
+
+    async def _flush_to_database(self, error: Exception | None = None) -> None:
+        """Flush all trace data to database."""
+        try:
+            from uuid import UUID as UUIDType
+
+            from lfx.services.deps import session_scope
+
+            from langflow.services.database.models.traces.model import SpanTable, TraceTable
+
+            # Ensure tables exist (for development - in prod use migrations)
+            await self._ensure_tables_exist()
+
+            # Parse flow_id
+            try:
+                flow_uuid = UUIDType(self.flow_id)
+            except (ValueError, TypeError):
+                logger.warning(f"Invalid flow_id format: {self.flow_id}")
+                return
+
+            end_time = datetime.now(tz=timezone.utc)
+            total_latency_ms = int((end_time - self._start_time).total_seconds() * 1000)
+
+            async with session_scope() as session:
+                # Create trace record
+                trace = TraceTable(
+                    id=self.trace_id,
+                    name=self.trace_name,
+                    flow_id=flow_uuid,
+                    session_id=self.session_id,
+                    status=SpanStatus.ERROR if error else SpanStatus.SUCCESS,
+                    start_time=self._start_time,
+                    end_time=end_time,
+                    total_latency_ms=total_latency_ms,
+                )
+                session.add(trace)
+
+                # Create span records
+                from uuid import NAMESPACE_DNS, uuid5
+
+                for span_data in self.completed_spans:
+                    # Parse span_id to UUID (use uuid5 for deterministic conversion)
+                    try:
+                        span_uuid = UUIDType(span_data["id"])
+                    except (ValueError, TypeError):
+                        # Use uuid5 for deterministic UUID from string
+                        span_uuid = uuid5(NAMESPACE_DNS, f"{self.trace_id}-{span_data['id']}")
+
+                    # Handle parent_span_id conversion
+                    parent_uuid = None
+                    if span_data.get("parent_span_id"):
+                        parent_id = span_data["parent_span_id"]
+                        if isinstance(parent_id, UUIDType):
+                            parent_uuid = parent_id
+                        else:
+                            try:
+                                parent_uuid = UUIDType(str(parent_id))
+                            except (ValueError, TypeError):
+                                parent_uuid = uuid5(NAMESPACE_DNS, f"{self.trace_id}-{parent_id}")
+
+                    span = SpanTable(
+                        id=span_uuid,
+                        trace_id=self.trace_id,
+                        parent_span_id=parent_uuid,
+                        name=span_data["name"],
+                        span_type=span_data["span_type"],
+                        status=span_data["status"],
+                        start_time=span_data["start_time"],
+                        end_time=span_data["end_time"],
+                        latency_ms=span_data["latency_ms"],
+                        inputs=span_data["inputs"],
+                        outputs=span_data["outputs"],
+                        error=span_data.get("error"),
+                        model_name=span_data.get("model_name"),
+                        prompt_tokens=span_data.get("prompt_tokens"),
+                        completion_tokens=span_data.get("completion_tokens"),
+                        total_tokens=span_data.get("total_tokens"),
+                    )
+                    session.add(span)
+
+                await session.commit()
+                logger.debug(f"Flushed {len(self.completed_spans)} spans to database")
+
+        except Exception as e:  # noqa: BLE001
+            logger.debug(f"Error flushing to database: {e}")
+
+    @override
+    def get_langchain_callback(self) -> BaseCallbackHandler | None:
+        """Get a LangChain callback handler for deep tracing.
+
+        Returns:
+            NativeCallbackHandler instance or None if not ready.
+        """
+        if not self._ready:
+            return None
+
+        from uuid import NAMESPACE_DNS, uuid5
+
+        from langflow.services.tracing.native_callback import NativeCallbackHandler
+
+        # Convert current component ID to UUID for parent linking
+        parent_span_id = None
+        if self._current_component_id:
+            parent_span_id = uuid5(NAMESPACE_DNS, f"{self.trace_id}-{self._current_component_id}")
+
+        return NativeCallbackHandler(self, parent_span_id=parent_span_id)
+
+    # Helper methods for LangChain callback integration
+    def add_langchain_span(
+        self,
+        span_id: UUID,
+        name: str,
+        span_type: str,
+        inputs: dict[str, Any],
+        parent_span_id: UUID | None = None,
+        model_name: str | None = None,
+    ) -> None:
+        """Add a LangChain span (called from NativeCallbackHandler).
+
+        Args:
+            span_id: Unique span ID
+            name: Span name
+            span_type: Type of span (llm, tool, chain, retriever)
+            inputs: Input data
+            parent_span_id: Optional parent span ID
+            model_name: Optional model name for LLM spans
+        """
+        if not self._ready:
+            return
+
+        start_time = datetime.now(tz=timezone.utc)
+
+        # Store span info
+        self.langchain_spans[span_id] = {
+            "id": str(span_id),
+            "name": name,
+            "span_type": span_type,
+            "inputs": serialize(inputs),
+            "start_time": start_time,
+            "parent_span_id": parent_span_id,
+            "model_name": model_name,
+        }
+
+    def end_langchain_span(
+        self,
+        span_id: UUID,
+        outputs: dict[str, Any] | None = None,
+        error: str | None = None,
+        latency_ms: int = 0,
+        prompt_tokens: int | None = None,
+        completion_tokens: int | None = None,
+        total_tokens: int | None = None,
+    ) -> None:
+        """End a LangChain span (called from NativeCallbackHandler).
+
+        Args:
+            span_id: Span ID to end
+            outputs: Output data
+            error: Error message if failed
+            latency_ms: Execution time in milliseconds
+            prompt_tokens: Number of prompt tokens
+            completion_tokens: Number of completion tokens
+            total_tokens: Total tokens used
+        """
+        if not self._ready:
+            return
+
+        span_info = self.langchain_spans.pop(span_id, None)
+        if not span_info:
+            return
+
+        end_time = datetime.now(tz=timezone.utc)
+        start_time = span_info["start_time"]
+        actual_latency = int((end_time - start_time).total_seconds() * 1000)
+
+        # Store completed span for batch write
+        self.completed_spans.append(
+            {
+                "id": span_info["id"],
+                "name": span_info["name"],
+                "span_type": self._map_trace_type(span_info["span_type"]),
+                "inputs": span_info["inputs"],
+                "outputs": serialize(outputs) if outputs else None,
+                "start_time": start_time,
+                "end_time": end_time,
+                "latency_ms": latency_ms or actual_latency,
+                "status": SpanStatus.ERROR if error else SpanStatus.SUCCESS,
+                "error": error,
+                "model_name": span_info.get("model_name"),
+                "prompt_tokens": prompt_tokens,
+                "completion_tokens": completion_tokens,
+                "total_tokens": total_tokens,
+                "parent_span_id": span_info.get("parent_span_id"),
+            }
+        )
+
+    async def _ensure_tables_exist(self) -> None:
+        """Ensure trace and span tables exist in the database."""
+        try:
+            from langflow.services.deps import get_db_service
+
+            db_service = get_db_service()
+
+            # Use run_sync to create tables if they don't exist
+            from sqlmodel import SQLModel
+
+            async with db_service.engine.begin() as conn:
+                # Only create trace and span tables
+                await conn.run_sync(
+                    lambda c: SQLModel.metadata.create_all(
+                        c,
+                        tables=[
+                            SQLModel.metadata.tables.get("trace"),
+                            SQLModel.metadata.tables.get("span"),
+                        ],
+                        checkfirst=True,
+                    )
+                )
+        except Exception as e:  # noqa: BLE001
+            logger.debug(f"Error ensuring tables exist: {e}")
+
+    @staticmethod
+    def _map_trace_type(trace_type: str) -> SpanType:
+        """Map Langflow trace type to SpanType enum."""
+        type_map = {
+            "chain": SpanType.CHAIN,
+            "llm": SpanType.LLM,
+            "tool": SpanType.TOOL,
+            "retriever": SpanType.RETRIEVER,
+            "embedding": SpanType.EMBEDDING,
+            "parser": SpanType.PARSER,
+            "agent": SpanType.AGENT,
+        }
+        return type_map.get(trace_type.lower(), SpanType.CHAIN)
```

### `src/backend/base/langflow/services/tracing/native_callback.py` (new)

```diff
diff --git a/src/backend/base/langflow/services/tracing/native_callback.py b/src/backend/base/langflow/services/tracing/native_callback.py
new file mode 100644
index 0000000000..8886952ccd
--- /dev/null
+++ b/src/backend/base/langflow/services/tracing/native_callback.py
@@ -0,0 +1,413 @@
+"""Native callback handler for LangChain integration.
+
+This module provides a callback handler that captures LangChain execution events
+(LLM calls, tool calls, chain steps, etc.) and stores them as spans in the database.
+"""
+
+from __future__ import annotations
+
+from datetime import datetime, timezone
+from typing import TYPE_CHECKING, Any
+from uuid import UUID, uuid4
+
+from langchain.callbacks.base import BaseCallbackHandler
+
+if TYPE_CHECKING:
+    from langchain.schema import AgentAction, AgentFinish, LLMResult
+    from langchain_core.documents import Document
+    from langchain_core.messages import BaseMessage
+
+    from langflow.services.tracing.native import NativeTracer
+
+
+class NativeCallbackHandler(BaseCallbackHandler):
+    """Callback handler that captures LangChain events as spans.
+
+    This handler is returned by NativeTracer.get_langchain_callback() and
+    captures detailed execution information including:
+    - LLM calls with token usage
+    - Tool/function calls
+    - Chain executions
+    - Retriever operations
+    """
+
+    def __init__(self, tracer: NativeTracer, parent_span_id: UUID | None = None) -> None:
+        """Initialize the callback handler.
+
+        Args:
+            tracer: The NativeTracer instance to report spans to.
+            parent_span_id: Optional parent span ID for nested operations.
+        """
+        super().__init__()
+        self.tracer = tracer
+        self.parent_span_id = parent_span_id
+        # Track active spans by run_id
+        self._spans: dict[UUID, dict[str, Any]] = {}
+
+    def _get_span_id(self, run_id: UUID) -> UUID:
+        """Get or create a span ID for a run."""
+        if run_id not in self._spans:
+            self._spans[run_id] = {"span_id": uuid4(), "start_time": datetime.now(timezone.utc)}
+        return self._spans[run_id]["span_id"]
+
+    def _get_start_time(self, run_id: UUID) -> datetime:
+        """Get the start time for a run."""
+        if run_id in self._spans:
+            return self._spans[run_id]["start_time"]
+        return datetime.now(timezone.utc)
+
+    def _calculate_latency(self, run_id: UUID) -> int:
+        """Calculate latency in milliseconds for a run."""
+        start_time = self._get_start_time(run_id)
+        end_time = datetime.now(timezone.utc)
+        return int((end_time - start_time).total_seconds() * 1000)
+
+    def _cleanup_run(self, run_id: UUID) -> None:
+        """Clean up tracking data for a completed run."""
+        self._spans.pop(run_id, None)
+
+    # LLM callbacks
+    def on_llm_start(
+        self,
+        serialized: dict[str, Any],
+        prompts: list[str],
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        tags: list[str] | None = None,
+        metadata: dict[str, Any] | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when LLM starts running."""
+        span_id = self._get_span_id(run_id)
+        serialized = serialized or {}
+        name = serialized.get("name") or (serialized.get("id", ["LLM"])[-1] if serialized.get("id") else "LLM")
+        model_name = kwargs.get("invocation_params", {}).get("model_name") or kwargs.get("invocation_params", {}).get(
+            "model"
+        )
+
+        self.tracer.add_langchain_span(
+            span_id=span_id,
+            name=name,
+            span_type="llm",
+            inputs={"prompts": prompts},
+            parent_span_id=self.parent_span_id or (self._get_span_id(parent_run_id) if parent_run_id else None),
+            model_name=model_name,
+        )
+
+    def on_chat_model_start(
+        self,
+        serialized: dict[str, Any],
+        messages: list[list[BaseMessage]],
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        tags: list[str] | None = None,
+        metadata: dict[str, Any] | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when chat model starts running."""
+        span_id = self._get_span_id(run_id)
+        serialized = serialized or {}
+        name = serialized.get("name") or (
+            serialized.get("id", ["ChatModel"])[-1] if serialized.get("id") else "ChatModel"
+        )
+        model_name = kwargs.get("invocation_params", {}).get("model_name") or kwargs.get("invocation_params", {}).get(
+            "model"
+        )
+
+        # Convert messages to serializable format
+        formatted_messages = []
+        for message_list in messages:
+            formatted_messages.append([{"type": m.type, "content": m.content} for m in message_list])
+
+        self.tracer.add_langchain_span(
+            span_id=span_id,
+            name=name,
+            span_type="llm",
+            inputs={"messages": formatted_messages},
+            parent_span_id=self.parent_span_id or (self._get_span_id(parent_run_id) if parent_run_id else None),
+            model_name=model_name,
+        )
+
+    def on_llm_end(
+        self,
+        response: LLMResult,
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when LLM ends running."""
+        span_id = self._get_span_id(run_id)
+        latency_ms = self._calculate_latency(run_id)
+
+        # Extract token usage
+        llm_output = getattr(response, "llm_output", None) or {}
+        token_usage = llm_output.get("token_usage", {}) if isinstance(llm_output, dict) else {}
+        prompt_tokens = token_usage.get("prompt_tokens")
+        completion_tokens = token_usage.get("completion_tokens")
+        total_tokens = token_usage.get("total_tokens")
+
+        # Extract generations
+        generations = getattr(response, "generations", []) or []
+        outputs = {
+            "generations": [
+                [
+                    {"text": getattr(gen, "text", ""), "generation_info": getattr(gen, "generation_info", None)}
+                    for gen in gen_list
+                ]
+                for gen_list in generations
+            ]
+        }
+
+        self.tracer.end_langchain_span(
+            span_id=span_id,
+            outputs=outputs,
+            latency_ms=latency_ms,
+            prompt_tokens=prompt_tokens,
+            completion_tokens=completion_tokens,
+            total_tokens=total_tokens,
+        )
+        self._cleanup_run(run_id)
+
+    def on_llm_error(
+        self,
+        error: BaseException,
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when LLM errors."""
+        span_id = self._get_span_id(run_id)
+        latency_ms = self._calculate_latency(run_id)
+
+        self.tracer.end_langchain_span(
+            span_id=span_id,
+            error=str(error),
+            latency_ms=latency_ms,
+        )
+        self._cleanup_run(run_id)
+
+    # Chain callbacks
+    def on_chain_start(
+        self,
+        serialized: dict[str, Any],
+        inputs: dict[str, Any],
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        tags: list[str] | None = None,
+        metadata: dict[str, Any] | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when chain starts running."""
+        span_id = self._get_span_id(run_id)
+        serialized = serialized or {}
+        name = serialized.get("name") or (serialized.get("id", ["Chain"])[-1] if serialized.get("id") else "Chain")
+
+        self.tracer.add_langchain_span(
+            span_id=span_id,
+            name=name,
+            span_type="chain",
+            inputs=inputs or {},
+            parent_span_id=self.parent_span_id or (self._get_span_id(parent_run_id) if parent_run_id else None),
+        )
+
+    def on_chain_end(
+        self,
+        outputs: dict[str, Any],
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when chain ends running."""
+        span_id = self._get_span_id(run_id)
+        latency_ms = self._calculate_latency(run_id)
+
+        self.tracer.end_langchain_span(
+            span_id=span_id,
+            outputs=outputs or {},
+            latency_ms=latency_ms,
+        )
+        self._cleanup_run(run_id)
+
+    def on_chain_error(
+        self,
+        error: BaseException,
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when chain errors."""
+        span_id = self._get_span_id(run_id)
+        latency_ms = self._calculate_latency(run_id)
+
+        self.tracer.end_langchain_span(
+            span_id=span_id,
+            error=str(error),
+            latency_ms=latency_ms,
+        )
+        self._cleanup_run(run_id)
+
+    # Tool callbacks
+    def on_tool_start(
+        self,
+        serialized: dict[str, Any],
+        input_str: str,
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        tags: list[str] | None = None,
+        metadata: dict[str, Any] | None = None,
+        inputs: dict[str, Any] | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when tool starts running."""
+        span_id = self._get_span_id(run_id)
+        serialized = serialized or {}
+        name = serialized.get("name") or "Tool"
+
+        self.tracer.add_langchain_span(
+            span_id=span_id,
+            name=name,
+            span_type="tool",
+            inputs=inputs or {"input": input_str},
+            parent_span_id=self.parent_span_id or (self._get_span_id(parent_run_id) if parent_run_id else None),
+        )
+
+    def on_tool_end(
+        self,
+        output: Any,
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when tool ends running."""
+        span_id = self._get_span_id(run_id)
+        latency_ms = self._calculate_latency(run_id)
+
+        self.tracer.end_langchain_span(
+            span_id=span_id,
+            outputs={"output": str(output) if not isinstance(output, dict) else output},
+            latency_ms=latency_ms,
+        )
+        self._cleanup_run(run_id)
+
+    def on_tool_error(
+        self,
+        error: BaseException,
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when tool errors."""
+        span_id = self._get_span_id(run_id)
+        latency_ms = self._calculate_latency(run_id)
+
+        self.tracer.end_langchain_span(
+            span_id=span_id,
+            error=str(error),
+            latency_ms=latency_ms,
+        )
+        self._cleanup_run(run_id)
+
+    # Agent callbacks
+    def on_agent_action(
+        self,
+        action: AgentAction,
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when agent takes an action."""
+        # Agent actions are typically followed by tool calls, so we don't create separate spans
+
+    def on_agent_finish(
+        self,
+        finish: AgentFinish,
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when agent finishes."""
+        # Agent finish is handled by chain end
+
+    # Retriever callbacks
+    def on_retriever_start(
+        self,
+        serialized: dict[str, Any],
+        query: str,
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        tags: list[str] | None = None,
+        metadata: dict[str, Any] | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when retriever starts running."""
+        span_id = self._get_span_id(run_id)
+        serialized = serialized or {}
+        name = serialized.get("name") or (
+            serialized.get("id", ["Retriever"])[-1] if serialized.get("id") else "Retriever"
+        )
+
+        self.tracer.add_langchain_span(
+            span_id=span_id,
+            name=name,
+            span_type="retriever",
+            inputs={"query": query},
+            parent_span_id=self.parent_span_id or (self._get_span_id(parent_run_id) if parent_run_id else None),
+        )
+
+    def on_retriever_end(
+        self,
+        documents: list[Document],
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when retriever ends running."""
+        span_id = self._get_span_id(run_id)
+        latency_ms = self._calculate_latency(run_id)
+
+        # Serialize documents
+        documents = documents or []
+        docs_output = [
+            {"page_content": getattr(doc, "page_content", ""), "metadata": getattr(doc, "metadata", {})}
+            for doc in documents
+        ]
+
+        self.tracer.end_langchain_span(
+            span_id=span_id,
+            outputs={"documents": docs_output},
+            latency_ms=latency_ms,
+        )
+        self._cleanup_run(run_id)
+
+    def on_retriever_error(
+        self,
+        error: BaseException,
+        *,
+        run_id: UUID,
+        parent_run_id: UUID | None = None,
+        **kwargs: Any,
+    ) -> None:
+        """Called when retriever errors."""
+        span_id = self._get_span_id(run_id)
+        latency_ms = self._calculate_latency(run_id)
+
+        self.tracer.end_langchain_span(
+            span_id=span_id,
+            error=str(error),
+            latency_ms=latency_ms,
+        )
+        self._cleanup_run(run_id)
```

### `src/backend/base/langflow/services/tracing/service.py` (modified)

```diff
diff --git a/src/backend/base/langflow/services/tracing/service.py b/src/backend/base/langflow/services/tracing/service.py
index 3e4632d21b..c2ce7cbdaa 100644
--- a/src/backend/base/langflow/services/tracing/service.py
+++ b/src/backend/base/langflow/services/tracing/service.py
@@ -59,6 +59,12 @@ def _get_traceloop_tracer():
     return TraceloopTracer


+def _get_native_tracer():
+    from langflow.services.tracing.native import NativeTracer
+
+    return NativeTracer
+
+
 trace_context_var: ContextVar[TraceContext | None] = ContextVar("trace_context", default=None)
 component_context_var: ContextVar[ComponentTraceContext | None] = ContextVar("component_trace_context", default=None)

@@ -220,6 +226,19 @@ class TracingService(Service):
             session_id=trace_context.session_id,
         )

+    def _initialize_native_tracer(self, trace_context: TraceContext) -> None:
+        if self.deactivated:
+            return
+        native_tracer = _get_native_tracer()
+        trace_context.tracers["native"] = native_tracer(
+            trace_name=trace_context.run_name,
+            trace_type="chain",
+            project_name=trace_context.project_name,
+            trace_id=trace_context.run_id,
+            user_id=trace_context.user_id,
+            session_id=trace_context.session_id,
+        )
+
     async def start_tracers(
         self,
         run_id: UUID,
@@ -247,6 +266,7 @@ class TracingService(Service):
             self._initialize_arize_phoenix_tracer(trace_context)
             self._initialize_opik_tracer(trace_context)
             self._initialize_traceloop_tracer(trace_context)
+            self._initialize_native_tracer(trace_context)
         except Exception as e:  # noqa: BLE001
             await logger.adebug(f"Error initializing tracers: {e}")

@@ -282,6 +302,7 @@ class TracingService(Service):

         - stop worker for current trace_context
         - call end for all the tracers
+        - wait for native tracer to flush to database
         """
         if self.deactivated:
             return
@@ -291,6 +312,11 @@ class TracingService(Service):
         await self._stop(trace_context)
         self._end_all_tracers(trace_context, outputs, error)

+        # Wait for native tracer to flush to database
+        native_tracer = trace_context.tracers.get("native")
+        if native_tracer and hasattr(native_tracer, "wait_for_flush"):
+            await native_tracer.wait_for_flush()
+
     @staticmethod
     def _cleanup_inputs(inputs: dict[str, Any]):
         inputs = inputs.copy()
```

### `src/backend/base/langflow/api/v1/__init__.py` (modified - traces_router part)

Note: This diff also includes `datasets_router` and `evaluations_router` which belong to other features.

```diff
diff --git a/src/backend/base/langflow/api/v1/__init__.py b/src/backend/base/langflow/api/v1/__init__.py
index 45d609694c..0e0c6339b3 100644
--- a/src/backend/base/langflow/api/v1/__init__.py
+++ b/src/backend/base/langflow/api/v1/__init__.py
@@ -1,6 +1,8 @@
 from langflow.api.v1.api_key import router as api_key_router
 from langflow.api.v1.chat import router as chat_router
+from langflow.api.v1.datasets import router as datasets_router
 from langflow.api.v1.endpoints import router as endpoints_router
+from langflow.api.v1.evaluations import router as evaluations_router
 from langflow.api.v1.files import router as files_router
 from langflow.api.v1.flows import router as flows_router
 from langflow.api.v1.folders import router as folders_router
@@ -15,6 +17,7 @@ from langflow.api.v1.openai_responses import router as openai_responses_router
 from langflow.api.v1.projects import router as projects_router
 from langflow.api.v1.starter_projects import router as starter_projects_router
 from langflow.api.v1.store import router as store_router
+from langflow.api.v1.traces import router as traces_router
 from langflow.api.v1.users import router as users_router
 from langflow.api.v1.validate import router as validate_router
 from langflow.api.v1.variable import router as variables_router
@@ -23,7 +26,9 @@ from langflow.api.v1.voice_mode import router as voice_mode_router
 __all__ = [
     "api_key_router",
     "chat_router",
+    "datasets_router",
     "endpoints_router",
+    "evaluations_router",
     "files_router",
     "flows_router",
     "folders_router",
@@ -38,6 +43,7 @@ __all__ = [
     "projects_router",
     "starter_projects_router",
     "store_router",
+    "traces_router",
     "users_router",
     "validate_router",
     "variables_router",
```

### `src/backend/base/langflow/api/router.py` (modified - traces_router part)

Note: This diff also includes `datasets_router` and `evaluations_router` which belong to other features.

```diff
diff --git a/src/backend/base/langflow/api/router.py b/src/backend/base/langflow/api/router.py
index d15a4dc062..71ac55e326 100644
--- a/src/backend/base/langflow/api/router.py
+++ b/src/backend/base/langflow/api/router.py
@@ -4,7 +4,9 @@ from fastapi import APIRouter
 from langflow.api.v1 import (
     api_key_router,
     chat_router,
+    datasets_router,
     endpoints_router,
+    evaluations_router,
     files_router,
     flows_router,
     folders_router,
@@ -19,6 +21,7 @@ from langflow.api.v1 import (
     projects_router,
     starter_projects_router,
     store_router,
+    traces_router,
     users_router,
     validate_router,
     variables_router,
@@ -48,10 +51,13 @@ router_v1.include_router(login_router)
 router_v1.include_router(variables_router)
 router_v1.include_router(files_router)
 router_v1.include_router(monitor_router)
+router_v1.include_router(traces_router)
 router_v1.include_router(folders_router)
 router_v1.include_router(projects_router)
 router_v1.include_router(starter_projects_router)
 router_v1.include_router(knowledge_bases_router)
+router_v1.include_router(datasets_router)
+router_v1.include_router(evaluations_router)
 router_v1.include_router(mcp_router)
 router_v1.include_router(voice_mode_router)
 router_v1.include_router(mcp_projects_router)
```

### `src/backend/base/langflow/services/database/models/__init__.py` (modified - traces part)

Note: This diff also includes `Dataset`, `DatasetItem`, `Evaluation`, and `EvaluationResult` which belong to other features.

```diff
diff --git a/src/backend/base/langflow/services/database/models/__init__.py b/src/backend/base/langflow/services/database/models/__init__.py
index 4bc498757c..48e016e3cc 100644
--- a/src/backend/base/langflow/services/database/models/__init__.py
+++ b/src/backend/base/langflow/services/database/models/__init__.py
@@ -1,20 +1,29 @@
 from .api_key import ApiKey
+from .dataset import Dataset, DatasetItem
+from .evaluation import Evaluation, EvaluationResult
 from .file import File
 from .flow import Flow
 from .folder import Folder
 from .jobs import Job
 from .message import MessageTable
+from .traces import SpanTable, TraceTable
 from .transactions import TransactionTable
 from .user import User
 from .variable import Variable

 __all__ = [
     "ApiKey",
+    "Dataset",
+    "DatasetItem",
+    "Evaluation",
+    "EvaluationResult",
     "File",
     "Flow",
     "Folder",
     "Job",
     "MessageTable",
+    "SpanTable",
+    "TraceTable",
     "TransactionTable",
     "User",
     "Variable",
```
