"""Native tracer for storing execution traces in the database.

This module provides a tracer that stores component-level and LangChain-level
execution traces directly in Langflow's database, enabling the Trace View
without requiring external services like LangSmith or LangFuse.
"""

from __future__ import annotations

import asyncio
import os
from collections import OrderedDict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from typing_extensions import override

from langflow.serialization.serialization import serialize
from langflow.services.database.models.traces.model import SpanStatus, SpanType
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log


class NativeTracer(BaseTracer):
    """Tracer that stores execution traces in Langflow's database.

    This tracer captures:
    - Component-level traces (via add_trace/end_trace)
    - LangChain-level traces (via get_langchain_callback)

    Enabled by default. Disable with LANGFLOW_NATIVE_TRACING=false if needed.
    """

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Initialize the native tracer.

        Args:
            trace_name: Name of the trace (usually flow name + ID)
            trace_type: Type of trace (e.g., "chain")
            project_name: Project name for organization
            trace_id: Unique ID for this trace run
            user_id: Optional user ID
            session_id: Optional session ID for grouping traces
        """
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1] if " - " in trace_name else trace_name

        # Track active component spans (in-memory)
        self.spans: dict[str, dict[str, Any]] = OrderedDict()

        # Track completed spans for batch database write
        self.completed_spans: list[dict[str, Any]] = []

        # Track LangChain spans (from callback handler)
        self.langchain_spans: dict[UUID, dict[str, Any]] = {}

        # Track the currently active component span ID (for parent-child linking)
        self._current_component_id: str | None = None

        # Trace start time
        self._start_time = datetime.now(tz=timezone.utc)

        # Flush task (set by end() method, awaited by TracingService)
        self._flush_task: asyncio.Task | None = None

        # Check if native tracing is enabled
        self._ready = self._is_enabled()

    @staticmethod
    def _is_enabled() -> bool:
        """Check if native tracing is enabled (default: true)."""
        # Enabled by default, can be disabled with LANGFLOW_NATIVE_TRACING=false
        return os.getenv("LANGFLOW_NATIVE_TRACING", "true").lower() not in ("false", "0", "no")

    @property
    def ready(self) -> bool:
        """Return whether the tracer is ready to use."""
        return self._ready

    @override
    def add_trace(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ) -> None:
        """Add a component-level trace span.

        Args:
            trace_id: Component ID
            trace_name: Component name + ID
            trace_type: Type of component
            inputs: Input data
            metadata: Optional metadata
            vertex: Optional vertex reference
        """
        if not self._ready:
            return

        start_time = datetime.now(tz=timezone.utc)

        # Store span info for later completion
        name = trace_name.removesuffix(f" ({trace_id})")
        self.spans[trace_id] = {
            "id": trace_id,
            "name": name,
            "trace_type": trace_type,
            "inputs": serialize(inputs),
            "metadata": metadata or {},
            "start_time": start_time,
        }

        # Track current component for LangChain callback parent linking
        self._current_component_id = trace_id

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        """End a component-level trace span.

        Args:
            trace_id: Component ID
            trace_name: Component name
            outputs: Output data
            error: Optional error
            logs: Optional logs
        """
        if not self._ready:
            return

        end_time = datetime.now(tz=timezone.utc)

        span_info = self.spans.pop(trace_id, None)
        if not span_info:
            return

        start_time = span_info["start_time"]
        latency_ms = int((end_time - start_time).total_seconds() * 1000)

        # Prepare output with optional error and logs
        output_data: dict[str, Any] = {}
        if outputs:
            output_data.update(outputs)
        if error:
            output_data["error"] = str(error)
        if logs:
            output_data["logs"] = [log if isinstance(log, dict) else log.model_dump() for log in logs]

        # Store completed span for batch write
        self.completed_spans.append(
            {
                "id": trace_id,
                "name": span_info["name"],
                "span_type": self._map_trace_type(span_info["trace_type"]),
                "inputs": span_info["inputs"],
                "outputs": serialize(output_data) if output_data else None,
                "start_time": start_time,
                "end_time": end_time,
                "latency_ms": latency_ms,
                "status": SpanStatus.ERROR if error else SpanStatus.SUCCESS,
                "error": str(error) if error else None,
            }
        )

        # Clear current component ID
        self._current_component_id = None

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End the entire trace.

        Args:
            inputs: All accumulated inputs
            outputs: All accumulated outputs
            error: Optional error
            metadata: Optional metadata
        """
        if not self._ready:
            return

        # Schedule async database write - store task so TracingService can await it
        try:
            loop = asyncio.get_running_loop()
            self._flush_task = loop.create_task(self._flush_to_database(error))
        except RuntimeError:
            # No running event loop, try to run synchronously
            logger.warning("No running event loop, skipping database flush")

    async def wait_for_flush(self) -> None:
        """Wait for the flush task to complete.

        Called by TracingService after end() to ensure database write completes.
        """
        if self._flush_task is not None:
            try:
                await self._flush_task
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Error waiting for flush: {e}")

    async def _flush_to_database(self, error: Exception | None = None) -> None:
        """Flush all trace data to database."""
        try:
            from uuid import UUID as UUIDType

            from lfx.services.deps import session_scope

            from langflow.services.database.models.traces.model import SpanTable, TraceTable

            # Ensure tables exist (for development - in prod use migrations)
            await self._ensure_tables_exist()

            # Parse flow_id
            try:
                flow_uuid = UUIDType(self.flow_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid flow_id format: {self.flow_id}")
                return

            end_time = datetime.now(tz=timezone.utc)
            total_latency_ms = int((end_time - self._start_time).total_seconds() * 1000)

            async with session_scope() as session:
                # Create trace record
                trace = TraceTable(
                    id=self.trace_id,
                    name=self.trace_name,
                    flow_id=flow_uuid,
                    session_id=self.session_id,
                    status=SpanStatus.ERROR if error else SpanStatus.SUCCESS,
                    start_time=self._start_time,
                    end_time=end_time,
                    total_latency_ms=total_latency_ms,
                )
                session.add(trace)

                # Create span records
                from uuid import NAMESPACE_DNS, uuid5

                for span_data in self.completed_spans:
                    # Parse span_id to UUID (use uuid5 for deterministic conversion)
                    try:
                        span_uuid = UUIDType(span_data["id"])
                    except (ValueError, TypeError):
                        # Use uuid5 for deterministic UUID from string
                        span_uuid = uuid5(NAMESPACE_DNS, f"{self.trace_id}-{span_data['id']}")

                    # Handle parent_span_id conversion
                    parent_uuid = None
                    if span_data.get("parent_span_id"):
                        parent_id = span_data["parent_span_id"]
                        if isinstance(parent_id, UUIDType):
                            parent_uuid = parent_id
                        else:
                            try:
                                parent_uuid = UUIDType(str(parent_id))
                            except (ValueError, TypeError):
                                parent_uuid = uuid5(NAMESPACE_DNS, f"{self.trace_id}-{parent_id}")

                    span = SpanTable(
                        id=span_uuid,
                        trace_id=self.trace_id,
                        parent_span_id=parent_uuid,
                        name=span_data["name"],
                        span_type=span_data["span_type"],
                        status=span_data["status"],
                        start_time=span_data["start_time"],
                        end_time=span_data["end_time"],
                        latency_ms=span_data["latency_ms"],
                        inputs=span_data["inputs"],
                        outputs=span_data["outputs"],
                        error=span_data.get("error"),
                        model_name=span_data.get("model_name"),
                        prompt_tokens=span_data.get("prompt_tokens"),
                        completion_tokens=span_data.get("completion_tokens"),
                        total_tokens=span_data.get("total_tokens"),
                    )
                    session.add(span)

                await session.commit()
                logger.debug(f"Flushed {len(self.completed_spans)} spans to database")

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error flushing to database: {e}")

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Get a LangChain callback handler for deep tracing.

        Returns:
            NativeCallbackHandler instance or None if not ready.
        """
        if not self._ready:
            return None

        from uuid import NAMESPACE_DNS, uuid5

        from langflow.services.tracing.native_callback import NativeCallbackHandler

        # Convert current component ID to UUID for parent linking
        parent_span_id = None
        if self._current_component_id:
            parent_span_id = uuid5(NAMESPACE_DNS, f"{self.trace_id}-{self._current_component_id}")

        return NativeCallbackHandler(self, parent_span_id=parent_span_id)

    # Helper methods for LangChain callback integration
    def add_langchain_span(
        self,
        span_id: UUID,
        name: str,
        span_type: str,
        inputs: dict[str, Any],
        parent_span_id: UUID | None = None,
        model_name: str | None = None,
    ) -> None:
        """Add a LangChain span (called from NativeCallbackHandler).

        Args:
            span_id: Unique span ID
            name: Span name
            span_type: Type of span (llm, tool, chain, retriever)
            inputs: Input data
            parent_span_id: Optional parent span ID
            model_name: Optional model name for LLM spans
        """
        if not self._ready:
            return

        start_time = datetime.now(tz=timezone.utc)

        # Store span info
        self.langchain_spans[span_id] = {
            "id": str(span_id),
            "name": name,
            "span_type": span_type,
            "inputs": serialize(inputs),
            "start_time": start_time,
            "parent_span_id": parent_span_id,
            "model_name": model_name,
        }

    def end_langchain_span(
        self,
        span_id: UUID,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
        latency_ms: int = 0,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        """End a LangChain span (called from NativeCallbackHandler).

        Args:
            span_id: Span ID to end
            outputs: Output data
            error: Error message if failed
            latency_ms: Execution time in milliseconds
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            total_tokens: Total tokens used
        """
        if not self._ready:
            return

        span_info = self.langchain_spans.pop(span_id, None)
        if not span_info:
            return

        end_time = datetime.now(tz=timezone.utc)
        start_time = span_info["start_time"]
        actual_latency = int((end_time - start_time).total_seconds() * 1000)

        # Store completed span for batch write
        self.completed_spans.append(
            {
                "id": span_info["id"],
                "name": span_info["name"],
                "span_type": self._map_trace_type(span_info["span_type"]),
                "inputs": span_info["inputs"],
                "outputs": serialize(outputs) if outputs else None,
                "start_time": start_time,
                "end_time": end_time,
                "latency_ms": latency_ms or actual_latency,
                "status": SpanStatus.ERROR if error else SpanStatus.SUCCESS,
                "error": error,
                "model_name": span_info.get("model_name"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "parent_span_id": span_info.get("parent_span_id"),
            }
        )

    async def _ensure_tables_exist(self) -> None:
        """Ensure trace and span tables exist in the database."""
        try:
            from langflow.services.deps import get_db_service

            db_service = get_db_service()

            # Use run_sync to create tables if they don't exist
            from sqlmodel import SQLModel

            async with db_service.engine.begin() as conn:
                # Only create trace and span tables
                await conn.run_sync(
                    lambda c: SQLModel.metadata.create_all(
                        c,
                        tables=[
                            SQLModel.metadata.tables.get("trace"),
                            SQLModel.metadata.tables.get("span"),
                        ],
                        checkfirst=True,
                    )
                )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error ensuring tables exist: {e}")

    @staticmethod
    def _map_trace_type(trace_type: str) -> SpanType:
        """Map Langflow trace type to SpanType enum."""
        type_map = {
            "chain": SpanType.CHAIN,
            "llm": SpanType.LLM,
            "tool": SpanType.TOOL,
            "retriever": SpanType.RETRIEVER,
            "embedding": SpanType.EMBEDDING,
            "parser": SpanType.PARSER,
            "agent": SpanType.AGENT,
        }
        return type_map.get(trace_type.lower(), SpanType.CHAIN)
