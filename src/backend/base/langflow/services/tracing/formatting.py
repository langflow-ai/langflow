"""Formatting helpers for trace/span data.

Handles transformation of raw database records into API response models,
keeping presentation logic out of the API and repository layers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from langflow.services.database.models.traces.model import (
    SpanReadResponse,
    SpanStatus,
    SpanTable,
    SpanType,
)

if TYPE_CHECKING:
    from uuid import UUID

# Spans without end_time should sort last, not first.
_UTC_MIN = datetime.min.replace(tzinfo=timezone.utc)

# Name substring used to identify the user-facing input span.
# Langflow's native tracer names this span "Chat Input" by convention.
# If the span naming convention changes, update this constant.
_CHAT_INPUT_SPAN_NAME = "Chat Input"

TraceIO = dict[str, dict[str, Any] | None]


@dataclass
class TraceSummaryData:
    """Aggregated per-trace data fetched in a single span query.

    Combines token totals and I/O summary so the repository can make one
    database round-trip instead of two when building the trace list.

    Attributes:
        total_tokens: Sum of tokens from leaf spans only (avoids double-counting).
        input: Simplified input payload derived from the "Chat Input" span.
        output: Simplified output payload derived from the last root span.
    """

    total_tokens: int = 0
    input: dict[str, Any] | None = field(default=None)
    output: dict[str, Any] | None = field(default=None)


def safe_int_tokens(value: Any) -> int:
    """Safely coerce a token count value to int, returning 0 on failure.

    Handles the full range of representations that LLM providers store in span
    attributes: plain ``int``, ``float`` (e.g. ``12.0``), decimal strings
    (``"12"``), float strings (``"12.0"``), and scientific notation (``"1e3"``).

    Returns 0 for ``None``, ``"NaN"``, ``"inf"``, empty strings, booleans
    stored as strings, and any other non-numeric value.

    Args:
        value: Raw token count from a span attribute.

    Returns:
        Non-negative integer token count, or 0 if the value cannot be parsed.
    """
    if isinstance(value, bool):
        # bool is a subclass of int; treat True/False as invalid token counts.
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) else 0
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            try:
                parsed = float(value)
                return int(parsed) if math.isfinite(parsed) else 0
            except (ValueError, TypeError, OverflowError):
                return 0
    return 0


def span_to_response(span: SpanTable) -> SpanReadResponse:
    """Convert a SpanTable record to a SpanReadResponse.

    Args:
        span: SpanTable record from the database.

    Returns:
        SpanReadResponse with frontend-compatible (camelCase) field names.
    """
    token_usage = None
    if span.attributes:
        # OTel GenAI conventions enable consistent parsing across different LLM providers
        input_tokens = span.attributes.get("gen_ai.usage.input_tokens", 0)
        output_tokens = span.attributes.get("gen_ai.usage.output_tokens", 0)
        # OTel spec requires deriving total from input+output (no standard total_tokens key)
        total_tokens = safe_int_tokens(input_tokens) + safe_int_tokens(output_tokens)

        token_usage = {
            "promptTokens": safe_int_tokens(input_tokens),
            "completionTokens": safe_int_tokens(output_tokens),
            "totalTokens": total_tokens,
        }
    inputs = span.inputs if isinstance(span.inputs, dict) or span.inputs is None else {"input": span.inputs}
    outputs = span.outputs if isinstance(span.outputs, dict) or span.outputs is None else {"output": span.outputs}

    return SpanReadResponse(
        id=span.id,
        name=span.name,
        type=span.span_type or SpanType.CHAIN,
        status=span.status or SpanStatus.UNSET,
        start_time=span.start_time,
        end_time=span.end_time,
        latency_ms=span.latency_ms,
        inputs=inputs,
        outputs=outputs,
        error=span.error,
        model_name=(span.attributes or {}).get("gen_ai.response.model"),
        token_usage=token_usage,
    )


def build_span_tree(spans: list[SpanTable]) -> list[SpanReadResponse]:
    """Build a hierarchical span tree from a flat list of SpanTable records.

    Spans are sorted by ``start_time`` ascending before tree construction so
    that children always appear in chronological order regardless of the order
    in which the caller provides them.  This makes the function safe to call
    even when the upstream query does not guarantee ordering.

    Each :class:`SpanReadResponse` is initialised with an empty ``children``
    list (via ``default_factory=list`` on the model field), so in-place
    ``append`` is safe and does not mutate shared state.

    Args:
        spans: Flat list of SpanTable records for a single trace.

    Returns:
        List of root :class:`SpanReadResponse` objects with nested children
        populated in chronological order.
    """
    if not spans:
        return []

    sorted_spans = sorted(spans, key=lambda s: s.start_time or _UTC_MIN)

    span_dict: dict[UUID, SpanReadResponse] = {}
    for span in sorted_spans:
        span_dict[span.id] = span_to_response(span)

    root_spans: list[SpanReadResponse] = []
    for span in sorted_spans:
        span_response = span_dict[span.id]
        if span.parent_span_id and span.parent_span_id in span_dict:
            span_dict[span.parent_span_id].children.append(span_response)
        else:
            root_spans.append(span_response)

    return root_spans


# ---------------------------------------------------------------------------
# Internal normalised span record used by the shared I/O heuristic.
# Both public extract_trace_io_* functions convert their inputs to this shape
# before delegating to _extract_trace_io, keeping the heuristic in one place.
# ---------------------------------------------------------------------------


@dataclass
class _SpanIORecord:
    """Minimal span fields required by the trace I/O heuristic."""

    name: str | None
    parent_span_id: Any  # None for root spans
    end_time: Any  # datetime | None
    inputs: dict[str, Any] | None
    outputs: dict[str, Any] | None


def _extract_trace_io(records: list[_SpanIORecord]) -> TraceIO:
    """Core I/O heuristic operating on normalised :class:`_SpanIORecord` objects.

    **Input heuristic** — searches for the first record whose name contains
    :data:`_CHAT_INPUT_SPAN_NAME` (``"Chat Input"``).  The ``input_value`` key
    from that record's ``inputs`` dict is surfaced as the trace-level input.

    **Output heuristic** — collects all *root* records (``parent_span_id`` is
    ``None``) that have already finished (``end_time`` is not ``None``), then
    picks the one with the latest ``end_time``.  Its full ``outputs`` dict is
    surfaced as the trace-level output.

    Args:
        records: Normalised span records for a single trace.

    Returns:
        Dict with ``"input"`` and ``"output"`` keys.
    """
    chat_input = next((r for r in records if _CHAT_INPUT_SPAN_NAME in (r.name or "")), None)
    input_value = None
    if chat_input and chat_input.inputs:
        input_value = chat_input.inputs.get("input_value")

    root_records = [r for r in records if r.parent_span_id is None and r.end_time]
    output_value = None
    if root_records:
        root_records_sorted = sorted(
            root_records,
            key=lambda r: r.end_time or _UTC_MIN,
            reverse=True,
        )
        if root_records_sorted[0].outputs:
            output_value = root_records_sorted[0].outputs

    return {
        "input": {"input_value": input_value} if input_value else None,
        "output": output_value,
    }


def extract_trace_io_from_spans(spans: list[SpanTable]) -> TraceIO:
    """Extract a simplified input/output payload for a trace from SpanTable objects.

    Used when full SpanTable objects are already loaded (e.g. single-trace fetch).
    Delegates to :func:`_extract_trace_io` after normalising the ORM objects.

    To support different span naming conventions in the future, change
    :data:`_CHAT_INPUT_SPAN_NAME`.

    Args:
        spans: List of SpanTable objects for a single trace.

    Returns:
        Dict with ``"input"`` and ``"output"`` keys.  Each value is either a
        dict payload or ``None`` if the heuristic found no matching span.
    """
    records = [
        _SpanIORecord(
            name=s.name,
            parent_span_id=s.parent_span_id,
            end_time=s.end_time,
            inputs=s.inputs,
            outputs=s.outputs,
        )
        for s in spans
    ]
    return _extract_trace_io(records)


def extract_trace_io_from_rows(rows: list[Any]) -> TraceIO:
    """Extract a simplified input/output payload for a trace from lightweight row tuples.

    Used when only selected columns are fetched (e.g. bulk list fetch) to avoid
    loading heavy JSON blobs for every span.  Delegates to :func:`_extract_trace_io`
    after normalising the row tuples.

    Row tuple layout: ``(trace_id, name, parent_span_id, end_time, inputs, outputs)``

    To support different span naming conventions in the future, change
    :data:`_CHAT_INPUT_SPAN_NAME`.

    Args:
        rows: List of lightweight row tuples for a single trace.

    Returns:
        Dict with ``"input"`` and ``"output"`` keys.  Each value is either a
        dict payload or ``None`` if the heuristic found no matching row.
    """
    records = [
        _SpanIORecord(
            name=r[1],
            parent_span_id=r[2],
            end_time=r[3],
            inputs=r[4],
            outputs=r[5],
        )
        for r in rows
    ]
    return _extract_trace_io(records)


def compute_leaf_token_total(
    span_ids: list[Any],
    parent_ids: set[Any],
    attributes_by_id: dict[Any, dict[str, Any]],
) -> int:
    """Sum token counts from leaf spans only, avoiding double-counting in nested hierarchies.

    A leaf span is one whose ID does not appear as a ``parent_span_id`` of any
    other span in the same trace.  Counting only leaves prevents tokens from
    being added at every level of a nested LLM call chain.

    Args:
        span_ids: Ordered list of span IDs to consider.
        parent_ids: Set of IDs that are referenced as a parent by at least one
            other span in the same trace.
        attributes_by_id: Mapping of span ID to its attributes dict.

    Returns:
        Total token count as a non-negative integer.
    """
    total = 0
    for span_id in span_ids:
        if span_id not in parent_ids:
            attrs = attributes_by_id.get(span_id) or {}
            # Prefer OTel GenAI keys for consistency with observability standards
            input_tokens = attrs.get("gen_ai.usage.input_tokens", 0)
            output_tokens = attrs.get("gen_ai.usage.output_tokens", 0)
            # Sum input+output when available, otherwise fall back for backward compatibility
            if input_tokens or output_tokens:
                token_val = safe_int_tokens(input_tokens) + safe_int_tokens(output_tokens)
            else:
                token_val = attrs.get("total_tokens", 0)
            total += safe_int_tokens(token_val)
    return total
