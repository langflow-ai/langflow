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
                # Reject NaN (NaN != NaN) and ±infinity (not finite).
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
        token_usage = {
            "promptTokens": safe_int_tokens(span.attributes.get("prompt_tokens", 0)),
            "completionTokens": safe_int_tokens(span.attributes.get("completion_tokens", 0)),
            "totalTokens": safe_int_tokens(span.attributes.get("total_tokens", 0)),
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


def extract_trace_io_from_spans(spans: list[SpanTable]) -> TraceIO:
    """Extract a simplified input/output payload for a trace from SpanTable objects.

    Used when full SpanTable objects are already loaded (e.g. single-trace fetch).

    **Input heuristic** — searches for the first span whose name contains
    :data:`_CHAT_INPUT_SPAN_NAME` (``"Chat Input"``).  This is the span
    created by Langflow's ``ChatInput`` component.  The ``input_value`` key
    from that span's ``inputs`` dict is surfaced as the trace-level input.
    If no such span exists the input is ``None``.

    **Output heuristic** — collects all *root* spans (``parent_span_id`` is
    ``None``) that have already finished (``end_time`` is not ``None``), then
    picks the one with the latest ``end_time``.  Its full ``outputs`` dict is
    surfaced as the trace-level output.  Root spans represent top-level flow
    executions; the last one to finish is the most relevant result.

    To support different span naming conventions in the future, change
    :data:`_CHAT_INPUT_SPAN_NAME`.

    Args:
        spans: List of SpanTable objects for a single trace.

    Returns:
        Dict with ``"input"`` and ``"output"`` keys.  Each value is either a
        dict payload or ``None`` if the heuristic found no matching span.
    """
    chat_input_span = next((s for s in spans if _CHAT_INPUT_SPAN_NAME in (s.name or "")), None)
    input_value = None
    if chat_input_span and chat_input_span.inputs:
        input_value = chat_input_span.inputs.get("input_value")

    root_spans = [s for s in spans if s.parent_span_id is None and s.end_time]
    output_value = None
    if root_spans:
        root_spans_sorted = sorted(
            root_spans,
            key=lambda s: s.end_time or _UTC_MIN,
            reverse=True,
        )
        if root_spans_sorted[0].outputs:
            output_value = root_spans_sorted[0].outputs

    return {
        "input": {"input_value": input_value} if input_value else None,
        "output": output_value,
    }


def extract_trace_io_from_rows(rows: list[Any]) -> TraceIO:
    """Extract a simplified input/output payload for a trace from lightweight row tuples.

    Used when only selected columns are fetched (e.g. bulk list fetch) to avoid
    loading heavy JSON blobs for every span.

    Row tuple layout: ``(trace_id, name, parent_span_id, end_time, inputs, outputs)``

    **Input heuristic** — same as :func:`extract_trace_io_from_spans`: finds
    the first row whose ``name`` (index 1) contains :data:`_CHAT_INPUT_SPAN_NAME`
    and reads ``input_value`` from its ``inputs`` dict (index 4).

    **Output heuristic** — same as :func:`extract_trace_io_from_spans`: picks
    the root row (``parent_span_id`` at index 2 is ``None``) with the latest
    ``end_time`` (index 3) and returns its ``outputs`` dict (index 5).

    To support different span naming conventions in the future, change
    :data:`_CHAT_INPUT_SPAN_NAME`.

    Args:
        rows: List of lightweight row tuples for a single trace.

    Returns:
        Dict with ``"input"`` and ``"output"`` keys.  Each value is either a
        dict payload or ``None`` if the heuristic found no matching row.
    """
    chat_input_row = next((r for r in rows if _CHAT_INPUT_SPAN_NAME in (r[1] or "")), None)
    input_value = None
    if chat_input_row and chat_input_row[4]:
        input_value = chat_input_row[4].get("input_value")

    root_rows = [r for r in rows if r[2] is None and r[3] is not None]
    output_value = None
    if root_rows:
        root_rows_sorted = sorted(
            root_rows,
            key=lambda r: r[3] or _UTC_MIN,
            reverse=True,
        )
        if root_rows_sorted[0][5]:
            output_value = root_rows_sorted[0][5]

    return {
        "input": {"input_value": input_value} if input_value else None,
        "output": output_value,
    }
