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
from uuid import UUID, uuid5

from lfx.log.logger import logger
from typing_extensions import override

from langflow.serialization.serialization import serialize
from langflow.services.database.models.traces.model import SpanStatus, SpanType
from langflow.services.tracing.base import BaseTracer
from langflow.services.tracing.span_sorting import (
    LANGFLOW_SPAN_NAMESPACE,
    resolve_span_uuids,
    topological_sort_spans,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langchain.callbacks.base import BaseCallbackHandler
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log

TYPE_MAP = {
    "chain": SpanType.CHAIN,
    "llm": SpanType.LLM,
    "tool": SpanType.TOOL,
    "retriever": SpanType.RETRIEVER,
    "embedding": SpanType.EMBEDDING,
    "parser": SpanType.PARSER,
    "agent": SpanType.AGENT,
}


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
        flow_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Initialize the native tracer.

        Args:
            trace_name: Name of the trace (usually flow name + trace ID)
            trace_type: Type of trace (e.g., "chain")
            project_name: Project name for organization
            trace_id: Unique ID for this trace run
            flow_id: Flow ID (if not provided, extracted from trace_name)
            user_id: Optional user ID
            session_id: Session ID for grouping traces (defaults to trace_id if not provided)
        """
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.user_id = user_id
        # Fallback to trace_id so session grouping always has a value in the DB.
        self.session_id = session_id or str(trace_id)
        # Prefer the explicit flow_id; fall back to parsing trace_name so callers
        # that don't pass flow_id separately still produce a usable value.
        self.flow_id = flow_id or (trace_name.split(" - ")[-1] if " - " in trace_name else trace_name)

        # OrderedDict preserves insertion order so spans flush in execution order.
        self.spans: dict[str, dict[str, Any]] = OrderedDict()

        # Collected at end_trace time; written to DB in a single batch on flush.
        self.completed_spans: list[dict[str, Any]] = []

        # Keyed by LangChain run_id so on_*_end can look up the matching on_*_start data.
        self.langchain_spans: dict[UUID, dict[str, Any]] = {}

        # Needed so get_langchain_callback() can set the correct parent span ID.
        self._current_component_id: str | None = None

        # Rolled up into the component span's attributes so the UI can show per-component token counts.
        self._component_tokens: dict[str, dict[str, int]] = {}

        self._start_time = datetime.now(tz=timezone.utc)

        # Awaited by TracingService.end_tracers() to guarantee the DB write completes before the response returns.
        self._flush_task: asyncio.Task | None = None

        self._ready = self._is_enabled()

    @staticmethod
    def _is_enabled() -> bool:
        """Opt-out rather than opt-in so new deployments get tracing without extra config."""
        return os.getenv("LANGFLOW_NATIVE_TRACING", "true").lower() not in ("false", "0", "no")

    @property
    def ready(self) -> bool:
        """Expose _ready so callers can skip tracing setup when the tracer is disabled."""
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

        # Strip the component ID suffix so the UI shows a clean display name.
        name = trace_name.removesuffix(f" ({trace_id})")
        self.spans[trace_id] = {
            "id": trace_id,
            "name": name,
            "trace_type": trace_type,
            "inputs": serialize(inputs),
            "metadata": metadata or {},
            "start_time": start_time,
        }

        # Stored so get_langchain_callback() can attach LangChain child spans to this component.
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

        # Merge outputs, error, and logs into one dict so the DB stores a single JSON blob per span.
        output_data: dict[str, Any] = {}
        if outputs:
            output_data.update(outputs)
        if error:
            output_data["error"] = str(error)
        if logs:
            output_data["logs"] = [log if isinstance(log, dict) else log.model_dump() for log in logs]

        # Pop so tokens aren't double-counted if end_trace is called more than once for the same component.
        tokens = self._component_tokens.pop(trace_id, {})

        # Use OTel GenAI conventions so observability tools can parse token usage uniformly across providers
        attributes: dict[str, Any] = {}
        if tokens.get("gen_ai.usage.input_tokens"):
            attributes["gen_ai.usage.input_tokens"] = tokens["gen_ai.usage.input_tokens"]
        if tokens.get("gen_ai.usage.output_tokens"):
            attributes["gen_ai.usage.output_tokens"] = tokens["gen_ai.usage.output_tokens"]

        self.completed_spans.append(
            self._build_completed_span(
                span_id=trace_id,
                name=span_info["name"],
                span_type=self._map_trace_type(span_info["trace_type"]),
                inputs=span_info["inputs"],
                outputs=serialize(output_data) if output_data else None,
                start_time=start_time,
                end_time=end_time,
                latency_ms=latency_ms,
                error=str(error) if error else None,
                attributes=attributes,
                span_source="component",
            )
        )

        # Reset so the next component's LangChain spans don't inherit this component as parent.
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

        # Store the task so TracingService.end_tracers() can await it before returning the response.
        try:
            loop = asyncio.get_running_loop()
            self._flush_task = loop.create_task(self._flush_to_database(error))
        except RuntimeError:
            # Called from a sync context (e.g. tests without an event loop) — data cannot be persisted.
            logger.error(
                "No running event loop for trace flush - trace data will be lost. Flow: %s, Spans: %d",
                self.flow_id,
                len(self.completed_spans),
            )

    async def wait_for_flush(self) -> None:
        """Wait for the flush task to complete.

        Called by TracingService after end() to ensure database write completes.
        """
        if self._flush_task is not None:
            try:
                await self._flush_task
            except Exception as e:  # noqa: BLE001
                logger.debug("Error waiting for flush: %s", e)

    async def _flush_to_database(self, error: Exception | None = None) -> None:
        """Persist the completed trace and all its spans in a single DB session to minimise round-trips."""
        try:
            from lfx.services.deps import session_scope

            from langflow.services.database.models.traces.model import SpanTable, TraceTable

            try:
                flow_uuid = UUID(self.flow_id)
            except (ValueError, TypeError):
                # Deterministic fallback so malformed flow_ids don't silently discard trace data.
                flow_uuid = uuid5(LANGFLOW_SPAN_NAMESPACE, f"invalid-flow-id:{self.flow_id}")
                logger.error(
                    "Invalid flow_id format — trace will be persisted with a sentinel flow_id. "
                    "flow_id=%r trace_id=%s sentinel_flow_id=%s",
                    self.flow_id,
                    self.trace_id,
                    flow_uuid,
                )

            end_time = datetime.now(tz=timezone.utc)
            total_latency_ms = int((end_time - self._start_time).total_seconds() * 1000)

            # Propagate any child span error to the trace so the UI can filter by status.
            has_span_errors = any(span.get("status") == SpanStatus.ERROR for span in self.completed_spans)
            trace_status = SpanStatus.ERROR if (error or has_span_errors) else SpanStatus.OK

            # Only sum LangChain spans because component spans already aggregate their children's
            # tokens — summing both levels would double-count every LLM call.
            # OTel spec requires deriving total from input+output (no standard total_tokens key)
            from langflow.services.tracing.formatting import safe_int_tokens

            total_tokens = sum(
                safe_int_tokens((span.get("attributes") or {}).get("gen_ai.usage.input_tokens"))
                + safe_int_tokens((span.get("attributes") or {}).get("gen_ai.usage.output_tokens"))
                for span in self.completed_spans
                if span.get("span_source") == "langchain"
            )

            async with session_scope() as session:
                trace = TraceTable(
                    id=self.trace_id,
                    name=self.trace_name,
                    flow_id=flow_uuid,
                    session_id=self.session_id,
                    status=trace_status,
                    start_time=self._start_time,
                    end_time=end_time,
                    total_latency_ms=total_latency_ms,
                    total_tokens=total_tokens,
                )
                await session.merge(trace)

                # Pre-compute UUIDs and topologically sort so parents are inserted
                # before children — required by PostgreSQL's immediate FK enforcement
                # on span.parent_span_id → span.id.
                resolved = resolve_span_uuids(self.completed_spans, self.trace_id)
                resolved = topological_sort_spans(resolved)

                for span_data, span_uuid, parent_uuid in resolved:
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
                        attributes=span_data.get("attributes") or {},
                    )
                    await session.merge(span)

                logger.debug("Flushed %d spans to database", len(self.completed_spans))

        except Exception:
            logger.exception("Error flushing trace data to database")
            raise

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Get a LangChain callback handler for deep tracing.

        Returns:
            NativeCallbackHandler instance or None if not ready.
        """
        if not self._ready:
            return None

        from langflow.services.tracing.native_callback import NativeCallbackHandler
        from langflow.services.tracing.service import component_context_var

        # Component context is set before add_trace() is called,
        # so it's available when components call get_langchain_callbacks() during flow execution.
        # We need to check component_context in case _current_component_id was still None when callbacks were created.
        parent_span_id = None
        component_context = component_context_var.get(None)
        if component_context:
            component_id = component_context.trace_id
            parent_span_id = uuid5(LANGFLOW_SPAN_NAMESPACE, f"{self.trace_id}-{component_id}")
        elif self._current_component_id:
            # Fallback for edge cases where component context might not be set
            parent_span_id = uuid5(LANGFLOW_SPAN_NAMESPACE, f"{self.trace_id}-{self._current_component_id}")

        return NativeCallbackHandler(self, parent_span_id=parent_span_id)

    def add_langchain_span(
        self,
        span_id: UUID,
        name: str,
        span_type: str,
        inputs: dict[str, Any],
        parent_span_id: UUID | None = None,
        model_name: str | None = None,
        provider: str | None = None,
    ) -> None:
        """Add a LangChain span (called from NativeCallbackHandler).

        Args:
            span_id: Unique span ID
            name: Span name
            span_type: Type of span (llm, tool, chain, retriever)
            inputs: Input data
            parent_span_id: Optional parent span ID
            model_name: Optional model name for LLM spans
            provider: Optional provider name for gen_ai.provider.name
        """
        if not self._ready:
            return

        start_time = datetime.now(tz=timezone.utc)

        # Keyed by span_id so end_langchain_span can look up the matching start data.
        self.langchain_spans[span_id] = {
            "id": str(span_id),
            "name": name,
            "span_type": span_type,
            "inputs": serialize(inputs),
            "start_time": start_time,
            "parent_span_id": parent_span_id,
            "model_name": model_name,
            "provider": provider,
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

        # Roll up into the component span so the UI shows per-component token totals.
        if total_tokens and self._current_component_id:
            tokens = self._component_tokens.setdefault(
                self._current_component_id,
                {
                    "gen_ai.usage.input_tokens": 0,
                    "gen_ai.usage.output_tokens": 0,
                },
            )
            tokens["gen_ai.usage.input_tokens"] += prompt_tokens or 0
            tokens["gen_ai.usage.output_tokens"] += completion_tokens or 0

        # Use OTel GenAI conventions so observability tools can parse LLM metrics uniformly
        lc_attributes: dict[str, Any] = {}
        if span_info.get("model_name"):
            # response.model captures the actual model used (vs request.model which may differ due to routing)
            lc_attributes["gen_ai.response.model"] = span_info["model_name"]
        if span_info.get("provider"):
            lc_attributes["gen_ai.provider.name"] = span_info["provider"]
        # Default to chat since most LLM usage in Langflow is conversational
        if span_info.get("span_type") == "llm":
            lc_attributes["gen_ai.operation.name"] = "chat"
        if prompt_tokens:
            lc_attributes["gen_ai.usage.input_tokens"] = prompt_tokens
        if completion_tokens:
            lc_attributes["gen_ai.usage.output_tokens"] = completion_tokens

        self.completed_spans.append(
            self._build_completed_span(
                span_id=span_info["id"],
                name=span_info["name"],
                span_type=self._map_trace_type(span_info["span_type"]),
                inputs=span_info["inputs"],
                outputs=serialize(outputs) if outputs else None,
                start_time=start_time,
                end_time=end_time,
                latency_ms=latency_ms or actual_latency,
                error=error,
                attributes=lc_attributes,
                span_source="langchain",
                parent_span_id=span_info.get("parent_span_id"),
            )
        )

    @staticmethod
    def _build_completed_span(
        *,
        span_id: str,
        name: str,
        span_type: SpanType,
        inputs: Any,
        outputs: Any = None,
        start_time: datetime,
        end_time: datetime,
        latency_ms: int,
        error: str | None = None,
        attributes: dict[str, Any] | None = None,
        span_source: str,
        parent_span_id: str | None = None,
    ) -> dict[str, Any]:
        """Build a completed span dict for storage.

        Args:
            span_id: Unique span identifier.
            name: Human-readable span name.
            span_type: Categorised span type enum value.
            inputs: Serialised input data.
            outputs: Serialised output data (or None).
            start_time: UTC datetime when the span started.
            end_time: UTC datetime when the span ended.
            latency_ms: Execution duration in milliseconds.
            error: Error message string, or None on success.
            attributes: OTel-style key/value attributes dict.
            span_source: Origin of the span ("component" or "langchain").
            parent_span_id: Optional parent span ID for nested spans.
        """
        span: dict[str, Any] = {
            "id": span_id,
            "name": name,
            "span_type": span_type,
            "inputs": inputs,
            "outputs": outputs,
            "start_time": start_time,
            "end_time": end_time,
            "latency_ms": latency_ms,
            "status": SpanStatus.ERROR if error else SpanStatus.OK,
            "error": error,
            "attributes": attributes or {},
            "span_source": span_source,
        }
        if parent_span_id is not None:
            span["parent_span_id"] = parent_span_id
        return span

    @staticmethod
    def _map_trace_type(trace_type: str) -> SpanType:
        """Normalise Langflow's string trace types to the SpanType enum, defaulting to CHAIN for unknown values."""
        return TYPE_MAP.get(trace_type.lower(), SpanType.CHAIN)
