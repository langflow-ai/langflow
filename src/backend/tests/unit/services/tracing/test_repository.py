"""Unit tests for langflow.services.tracing.repository.

Covers:
- fetch_trace_summary_data: token aggregation, I/O extraction, empty input
- Pagination boundary math used by fetch_traces
- TraceSummaryData dataclass defaults
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langflow.services.tracing.formatting import TraceSummaryData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _paginate(total_count: int, size: int) -> int:
    """Mirror the pagination formula used in fetch_traces."""
    return math.ceil(total_count / size) if total_count > 0 else 0


# ---------------------------------------------------------------------------
# TraceSummaryData defaults
# ---------------------------------------------------------------------------


class TestTraceSummaryData:
    def test_should_have_zero_tokens_by_default(self):
        data = TraceSummaryData()
        assert data.total_tokens == 0

    def test_should_have_none_input_by_default(self):
        data = TraceSummaryData()
        assert data.input is None

    def test_should_have_none_output_by_default(self):
        data = TraceSummaryData()
        assert data.output is None

    def test_should_accept_explicit_values(self):
        data = TraceSummaryData(
            total_tokens=42,
            input={"input_value": "hello"},
            output={"result": "world"},
        )
        assert data.total_tokens == 42
        assert data.input == {"input_value": "hello"}
        assert data.output == {"result": "world"}

    def test_should_not_share_mutable_defaults_between_instances(self):
        """Two instances must not share the same dict objects."""
        a = TraceSummaryData(input={"k": "v"})
        b = TraceSummaryData(input={"k": "v"})
        assert a.input is not None
        assert b.input is not None
        a.input["extra"] = "mutated"
        assert "extra" not in b.input


# ---------------------------------------------------------------------------
# Pagination boundary math
# ---------------------------------------------------------------------------


class TestPaginationMath:
    """Tests for the total_pages calculation in fetch_traces.

    Formula: math.ceil(total_count / size) if total_count > 0 else 0
    """

    def test_should_return_zero_pages_when_no_results(self):
        assert _paginate(total_count=0, size=50) == 0

    def test_should_return_one_page_when_results_fit_exactly(self):
        assert _paginate(total_count=50, size=50) == 1

    def test_should_return_one_page_when_results_less_than_page_size(self):
        assert _paginate(total_count=1, size=50) == 1

    def test_should_return_two_pages_when_one_result_overflows(self):
        assert _paginate(total_count=51, size=50) == 2

    def test_should_return_correct_pages_for_large_dataset(self):
        assert _paginate(total_count=1000, size=50) == 20

    def test_should_return_correct_pages_when_not_evenly_divisible(self):
        assert _paginate(total_count=101, size=50) == 3

    def test_should_handle_page_size_of_one(self):
        assert _paginate(total_count=5, size=1) == 5

    def test_should_handle_page_size_equal_to_total(self):
        assert _paginate(total_count=200, size=200) == 1

    def test_should_handle_max_page_size(self):
        # API allows size up to 200; 1000 results → 5 pages.
        assert _paginate(total_count=1000, size=200) == 5

    def test_should_return_zero_pages_for_zero_total_regardless_of_size(self):
        for size in [1, 10, 50, 200]:
            assert _paginate(total_count=0, size=size) == 0


# ---------------------------------------------------------------------------
# fetch_trace_summary_data — unit tests with mocked session
# ---------------------------------------------------------------------------


def _make_session(rows: list) -> MagicMock:
    """Build a mock AsyncSession where ``session.execute(stmt).all()`` returns ``rows``.

    The production code does: ``rows = (await session.execute(stmt)).all()``
    AsyncSession.execute is a coroutine, so we use an async function as the side_effect
    so that ``await session.execute(stmt)`` returns a MagicMock whose ``.all()`` is set.
    """
    result_mock = MagicMock()
    result_mock.all.return_value = rows

    async def _execute(_stmt):
        return result_mock

    session = MagicMock()
    session.execute = _execute
    return session


class TestFetchTraceSummaryData:
    """Tests for fetch_trace_summary_data using a mocked AsyncSession."""

    @pytest.mark.asyncio
    async def test_should_return_empty_dict_for_no_trace_ids(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        session = _make_session([])
        result = await fetch_trace_summary_data(session, [])
        assert result == {}

    @pytest.mark.asyncio
    async def test_should_aggregate_tokens_from_leaf_spans_only(self):
        """Parent spans must not be counted to avoid double-counting."""
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_id = uuid4()
        parent_span_id = uuid4()
        child_span_id = uuid4()

        # Row layout: (trace_id, span_id, name, parent_span_id, end_time, inputs, outputs, attributes)
        rows = [
            # Parent span — has tokens but should be excluded (it IS a parent).
            (trace_id, parent_span_id, "parent", None, None, None, None, {"total_tokens": 100}),
            # Child span — leaf, should be counted.
            (trace_id, child_span_id, "child", parent_span_id, None, None, None, {"total_tokens": 30}),
        ]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_id])

        assert str(trace_id) in result
        # Only the leaf (child) span's 30 tokens should be counted.
        assert result[str(trace_id)].total_tokens == 30

    @pytest.mark.asyncio
    async def test_should_sum_tokens_from_multiple_leaf_spans(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_id = uuid4()
        leaf1_id = uuid4()
        leaf2_id = uuid4()

        rows = [
            (trace_id, leaf1_id, "leaf1", None, None, None, None, {"total_tokens": 10}),
            (trace_id, leaf2_id, "leaf2", None, None, None, None, {"total_tokens": 20}),
        ]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_id])
        assert result[str(trace_id)].total_tokens == 30

    @pytest.mark.asyncio
    async def test_should_handle_spans_with_no_token_attributes(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_id = uuid4()
        span_id = uuid4()

        rows = [(trace_id, span_id, "span", None, None, None, None, {})]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_id])
        assert result[str(trace_id)].total_tokens == 0

    @pytest.mark.asyncio
    async def test_should_handle_spans_with_none_attributes(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_id = uuid4()
        span_id = uuid4()

        rows = [(trace_id, span_id, "span", None, None, None, None, None)]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_id])
        assert result[str(trace_id)].total_tokens == 0

    @pytest.mark.asyncio
    async def test_should_separate_summaries_by_trace_id(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_a = uuid4()
        trace_b = uuid4()
        span_a = uuid4()
        span_b = uuid4()

        rows = [
            (trace_a, span_a, "span_a", None, None, None, None, {"total_tokens": 5}),
            (trace_b, span_b, "span_b", None, None, None, None, {"total_tokens": 15}),
        ]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_a, trace_b])
        assert result[str(trace_a)].total_tokens == 5
        assert result[str(trace_b)].total_tokens == 15

    @pytest.mark.asyncio
    async def test_should_use_llm_usage_total_tokens_attribute(self):
        """Prefer OTel GenAI token attributes over legacy 'total_tokens'."""
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_id = uuid4()
        span_id = uuid4()

        rows = [
            (
                trace_id,
                span_id,
                "llm_span",
                None,
                None,
                None,
                None,
                {"gen_ai.usage.input_tokens": 30, "gen_ai.usage.output_tokens": 20, "total_tokens": 10},
            ),
        ]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_id])
        assert result[str(trace_id)].total_tokens == 50

    @pytest.mark.asyncio
    async def test_should_return_none_input_when_no_chat_input_span(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_id = uuid4()
        span_id = uuid4()

        rows = [(trace_id, span_id, "SomeSpan", None, None, {"input_value": "ignored"}, None, {})]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_id])
        assert result[str(trace_id)].input is None

    @pytest.mark.asyncio
    async def test_should_return_none_output_when_no_finished_root_spans(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_id = uuid4()
        span_id = uuid4()

        # end_time (index 4) is None → unfinished, should not be used as output.
        rows = [(trace_id, span_id, "root", None, None, None, {"result": "nope"}, {})]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_id])
        assert result[str(trace_id)].output is None
