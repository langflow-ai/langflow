"""Unit tests for langflow.services.tracing.formatting.

Covers:
- safe_int_tokens: happy path, edge cases, adversarial inputs
- build_span_tree: ordering, hierarchy, empty input, orphan spans
- extract_trace_io_from_spans: Chat Input detection, root-span output selection
- extract_trace_io_from_rows: same heuristics via lightweight row tuples
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from langflow.services.database.models.traces.model import SpanStatus, SpanTable, SpanType
from langflow.services.tracing.formatting import (
    _CHAT_INPUT_SPAN_NAME,
    build_span_tree,
    extract_trace_io_from_rows,
    extract_trace_io_from_spans,
    safe_int_tokens,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TRACE_ID = uuid4()
_UTC = timezone.utc


def _dt(hour: int, minute: int = 0) -> datetime:
    """Return a UTC datetime for a fixed date at the given hour:minute."""
    return datetime(2024, 1, 1, hour, minute, tzinfo=_UTC)


def _span(
    *,
    name: str = "span",
    parent_span_id=None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    inputs: dict | None = None,
    outputs: dict | None = None,
    attributes: dict | None = None,
    span_type: SpanType = SpanType.CHAIN,
    status: SpanStatus = SpanStatus.OK,
) -> SpanTable:
    """Build a minimal SpanTable without a database session."""
    return SpanTable(
        id=uuid4(),
        trace_id=_TRACE_ID,
        name=name,
        parent_span_id=parent_span_id,
        start_time=start_time or _dt(0),
        end_time=end_time,
        inputs=inputs,
        outputs=outputs,
        attributes=attributes or {},
        span_type=span_type,
        status=status,
        latency_ms=0,
    )


def _row(
    *,
    name: str = "span",
    parent_span_id=None,
    end_time: datetime | None = None,
    inputs: dict | None = None,
    outputs: dict | None = None,
):
    """Build a lightweight row tuple matching the layout expected by extract_trace_io_from_rows.

    Layout: (trace_id, name, parent_span_id, end_time, inputs, outputs)
    """
    return (_TRACE_ID, name, parent_span_id, end_time, inputs, outputs)


# ---------------------------------------------------------------------------
# safe_int_tokens
# ---------------------------------------------------------------------------


class TestSafeIntTokens:
    # --- Happy path ---

    def test_should_return_int_unchanged_when_given_plain_int(self):
        assert safe_int_tokens(42) == 42

    def test_should_return_zero_when_given_zero_int(self):
        assert safe_int_tokens(0) == 0

    def test_should_truncate_float_to_int(self):
        assert safe_int_tokens(12.9) == 12

    def test_should_parse_decimal_string(self):
        assert safe_int_tokens("100") == 100

    def test_should_parse_float_string(self):
        assert safe_int_tokens("12.0") == 12

    def test_should_parse_scientific_notation_string(self):
        assert safe_int_tokens("1e3") == 1000

    # --- Edge cases ---

    def test_should_return_zero_for_none(self):
        assert safe_int_tokens(None) == 0

    def test_should_return_zero_for_empty_string(self):
        assert safe_int_tokens("") == 0

    def test_should_return_zero_for_nan_string(self):
        assert safe_int_tokens("NaN") == 0

    def test_should_return_zero_for_inf_string(self):
        # float("inf") is valid Python but not a meaningful token count.
        # int(float("inf")) raises OverflowError; we expect 0.
        assert safe_int_tokens("inf") == 0

    def test_should_return_zero_for_negative_inf_string(self):
        assert safe_int_tokens("-inf") == 0

    def test_should_return_zero_for_nan_float(self):
        assert safe_int_tokens(float("nan")) == 0

    def test_should_return_zero_for_arbitrary_string(self):
        assert safe_int_tokens("not-a-number") == 0

    def test_should_return_zero_for_list(self):
        assert safe_int_tokens([1, 2, 3]) == 0

    def test_should_return_zero_for_dict(self):
        assert safe_int_tokens({"tokens": 5}) == 0

    def test_should_return_zero_for_bool_true(self):
        value = True
        assert safe_int_tokens(value) == 0

    def test_should_return_zero_for_bool_false(self):
        value = False
        assert safe_int_tokens(value) == 0

    def test_should_handle_large_integer(self):
        assert safe_int_tokens(10**9) == 10**9

    def test_should_handle_negative_int(self):
        # Negative values are technically parseable; we return them as-is.
        assert safe_int_tokens(-5) == -5

    def test_should_parse_float_string_with_trailing_zeros(self):
        assert safe_int_tokens("100.00") == 100


# ---------------------------------------------------------------------------
# build_span_tree
# ---------------------------------------------------------------------------


class TestBuildSpanTree:
    # --- Happy path ---

    def test_should_return_empty_list_for_no_spans(self):
        assert build_span_tree([]) == []

    def test_should_return_single_root_span(self):
        span = _span(name="root")
        result = build_span_tree([span])
        assert len(result) == 1
        assert result[0].name == "root"
        assert result[0].children == []

    def test_should_nest_child_under_parent(self):
        parent = _span(name="parent", start_time=_dt(1))
        child = _span(name="child", parent_span_id=parent.id, start_time=_dt(2))
        result = build_span_tree([parent, child])
        assert len(result) == 1
        assert result[0].name == "parent"
        assert len(result[0].children) == 1
        assert result[0].children[0].name == "child"

    def test_should_build_three_level_hierarchy(self):
        root = _span(name="root", start_time=_dt(1))
        mid = _span(name="mid", parent_span_id=root.id, start_time=_dt(2))
        leaf = _span(name="leaf", parent_span_id=mid.id, start_time=_dt(3))
        result = build_span_tree([root, mid, leaf])
        assert result[0].children[0].children[0].name == "leaf"

    def test_should_return_multiple_root_spans(self):
        a = _span(name="a", start_time=_dt(1))
        b = _span(name="b", start_time=_dt(2))
        result = build_span_tree([a, b])
        assert len(result) == 2

    # --- Ordering ---

    def test_should_sort_roots_by_start_time_ascending(self):
        late = _span(name="late", start_time=_dt(10))
        early = _span(name="early", start_time=_dt(1))
        result = build_span_tree([late, early])
        assert result[0].name == "early"
        assert result[1].name == "late"

    def test_should_sort_children_by_start_time_ascending(self):
        parent = _span(name="parent", start_time=_dt(0))
        c2 = _span(name="c2", parent_span_id=parent.id, start_time=_dt(5))
        c1 = _span(name="c1", parent_span_id=parent.id, start_time=_dt(2))
        result = build_span_tree([parent, c2, c1])
        children = result[0].children
        assert children[0].name == "c1"
        assert children[1].name == "c2"

    def test_should_produce_same_tree_regardless_of_input_order(self):
        root = _span(name="root", start_time=_dt(1))
        child = _span(name="child", parent_span_id=root.id, start_time=_dt(2))

        result_forward = build_span_tree([root, child])
        result_reversed = build_span_tree([child, root])

        assert result_forward[0].name == result_reversed[0].name
        assert result_forward[0].children[0].name == result_reversed[0].children[0].name

    # --- Adversarial ---

    def test_should_treat_orphan_span_as_root(self):
        """A span whose parent_span_id references a non-existent span becomes a root."""
        orphan = _span(name="orphan", parent_span_id=uuid4())
        result = build_span_tree([orphan])
        assert len(result) == 1
        assert result[0].name == "orphan"

    def test_should_not_share_children_list_between_spans(self):
        """Each SpanReadResponse must have its own children list (default_factory)."""
        a = _span(name="a", start_time=_dt(1))
        b = _span(name="b", start_time=_dt(2))
        result = build_span_tree([a, b])
        result[0].children.append(result[1])
        # Mutating one span's children must not affect the other.
        assert result[1].children == []


# ---------------------------------------------------------------------------
# extract_trace_io_from_spans
# ---------------------------------------------------------------------------


class TestExtractTraceIoFromSpans:
    # --- Happy path ---

    def test_should_return_none_input_and_output_for_empty_spans(self):
        result = extract_trace_io_from_spans([])
        assert result == {"input": None, "output": None}

    def test_should_extract_input_from_chat_input_span(self):
        span = _span(
            name=_CHAT_INPUT_SPAN_NAME,
            inputs={"input_value": "hello"},
            end_time=_dt(1),
        )
        result = extract_trace_io_from_spans([span])
        assert result["input"] == {"input_value": "hello"}

    def test_should_extract_output_from_last_finished_root_span(self):
        early = _span(name="root_early", end_time=_dt(1), outputs={"result": "first"})
        late = _span(name="root_late", end_time=_dt(5), outputs={"result": "last"})
        result = extract_trace_io_from_spans([early, late])
        assert result["output"] == {"result": "last"}

    def test_should_ignore_unfinished_root_spans_for_output(self):
        finished = _span(name="done", end_time=_dt(3), outputs={"result": "ok"})
        unfinished = _span(name="pending", end_time=None, outputs={"result": "nope"})
        result = extract_trace_io_from_spans([finished, unfinished])
        assert result["output"] == {"result": "ok"}

    def test_should_ignore_child_spans_for_output(self):
        parent = _span(name="parent", end_time=_dt(2), outputs={"result": "parent_out"})
        child = _span(
            name="child",
            parent_span_id=parent.id,
            end_time=_dt(3),
            outputs={"result": "child_out"},
        )
        result = extract_trace_io_from_spans([parent, child])
        assert result["output"] == {"result": "parent_out"}

    # --- Edge cases ---

    def test_should_return_none_input_when_no_chat_input_span(self):
        span = _span(name="SomeOtherSpan", inputs={"input_value": "ignored"}, end_time=_dt(1))
        result = extract_trace_io_from_spans([span])
        assert result["input"] is None

    def test_should_return_none_input_when_chat_input_span_has_no_inputs(self):
        span = _span(name=_CHAT_INPUT_SPAN_NAME, inputs=None, end_time=_dt(1))
        result = extract_trace_io_from_spans([span])
        assert result["input"] is None

    def test_should_return_none_input_when_input_value_key_missing(self):
        span = _span(name=_CHAT_INPUT_SPAN_NAME, inputs={"other_key": "value"}, end_time=_dt(1))
        result = extract_trace_io_from_spans([span])
        assert result["input"] is None

    def test_should_return_none_output_when_root_span_has_no_outputs(self):
        span = _span(name="root", end_time=_dt(1), outputs=None)
        result = extract_trace_io_from_spans([span])
        assert result["output"] is None

    def test_should_return_none_output_when_no_finished_root_spans(self):
        span = _span(name="root", end_time=None, outputs={"result": "nope"})
        result = extract_trace_io_from_spans([span])
        assert result["output"] is None

    def test_should_match_chat_input_span_by_substring(self):
        """Span name only needs to *contain* the constant, not equal it."""
        span = _span(
            name=f"Langflow {_CHAT_INPUT_SPAN_NAME} Component",
            inputs={"input_value": "hi"},
            end_time=_dt(1),
        )
        result = extract_trace_io_from_spans([span])
        assert result["input"] == {"input_value": "hi"}


# ---------------------------------------------------------------------------
# extract_trace_io_from_rows
# ---------------------------------------------------------------------------


class TestExtractTraceIoFromRows:
    # --- Happy path ---

    def test_should_return_none_input_and_output_for_empty_rows(self):
        result = extract_trace_io_from_rows([])
        assert result == {"input": None, "output": None}

    def test_should_extract_input_from_chat_input_row(self):
        row = _row(name=_CHAT_INPUT_SPAN_NAME, inputs={"input_value": "hello"}, end_time=_dt(1))
        result = extract_trace_io_from_rows([row])
        assert result["input"] == {"input_value": "hello"}

    def test_should_extract_output_from_last_finished_root_row(self):
        early = _row(name="root_early", end_time=_dt(1), outputs={"result": "first"})
        late = _row(name="root_late", end_time=_dt(5), outputs={"result": "last"})
        result = extract_trace_io_from_rows([early, late])
        assert result["output"] == {"result": "last"}

    def test_should_ignore_unfinished_root_rows_for_output(self):
        finished = _row(name="done", end_time=_dt(3), outputs={"result": "ok"})
        unfinished = _row(name="pending", end_time=None, outputs={"result": "nope"})
        result = extract_trace_io_from_rows([finished, unfinished])
        assert result["output"] == {"result": "ok"}

    def test_should_ignore_child_rows_for_output(self):
        parent_id = uuid4()
        parent = _row(name="parent", end_time=_dt(2), outputs={"result": "parent_out"})
        child = _row(name="child", parent_span_id=parent_id, end_time=_dt(3), outputs={"result": "child_out"})
        result = extract_trace_io_from_rows([parent, child])
        assert result["output"] == {"result": "parent_out"}

    # --- Edge cases ---

    def test_should_return_none_input_when_no_chat_input_row(self):
        row = _row(name="SomeOtherSpan", inputs={"input_value": "ignored"}, end_time=_dt(1))
        result = extract_trace_io_from_rows([row])
        assert result["input"] is None

    def test_should_return_none_input_when_chat_input_row_has_no_inputs(self):
        row = _row(name=_CHAT_INPUT_SPAN_NAME, inputs=None, end_time=_dt(1))
        result = extract_trace_io_from_rows([row])
        assert result["input"] is None

    def test_should_return_none_input_when_input_value_key_missing(self):
        row = _row(name=_CHAT_INPUT_SPAN_NAME, inputs={"other_key": "value"}, end_time=_dt(1))
        result = extract_trace_io_from_rows([row])
        assert result["input"] is None

    def test_should_return_none_output_when_root_row_has_no_outputs(self):
        row = _row(name="root", end_time=_dt(1), outputs=None)
        result = extract_trace_io_from_rows([row])
        assert result["output"] is None

    def test_should_return_none_output_when_no_finished_root_rows(self):
        row = _row(name="root", end_time=None, outputs={"result": "nope"})
        result = extract_trace_io_from_rows([row])
        assert result["output"] is None

    def test_should_match_chat_input_row_by_substring(self):
        row = _row(
            name=f"Langflow {_CHAT_INPUT_SPAN_NAME} Component",
            inputs={"input_value": "hi"},
            end_time=_dt(1),
        )
        result = extract_trace_io_from_rows([row])
        assert result["input"] == {"input_value": "hi"}

    def test_should_produce_same_result_as_span_variant_for_equivalent_data(self):
        """extract_trace_io_from_rows and extract_trace_io_from_spans must agree."""
        span = _span(
            name=_CHAT_INPUT_SPAN_NAME,
            inputs={"input_value": "test"},
            end_time=_dt(2),
            outputs={"result": "out"},
        )
        row = _row(
            name=_CHAT_INPUT_SPAN_NAME,
            inputs={"input_value": "test"},
            end_time=_dt(2),
            outputs={"result": "out"},
        )
        span_result = extract_trace_io_from_spans([span])
        row_result = extract_trace_io_from_rows([row])
        assert span_result == row_result
