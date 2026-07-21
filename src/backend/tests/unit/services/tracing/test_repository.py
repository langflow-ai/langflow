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
    """Build a mock AsyncSession where ``session.exec(stmt).all()`` returns ``rows``."""
    result_mock = MagicMock()
    result_mock.all.return_value = rows

    async def _exec(_stmt):
        return result_mock

    session = MagicMock()
    session.exec = _exec
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
    async def test_should_separate_summaries_by_trace_id(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_a = uuid4()
        trace_b = uuid4()
        rows = [
            (trace_a, "root_a", None, 1, None, {"result": "a"}),
            (trace_b, "root_b", None, 1, None, {"result": "b"}),
        ]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_a, trace_b])
        assert result[str(trace_a)].output == {"result": "a"}
        assert result[str(trace_b)].output == {"result": "b"}

    @pytest.mark.asyncio
    async def test_should_return_none_input_when_no_chat_input_span(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_id = uuid4()
        rows = [(trace_id, "SomeSpan", None, None, {"input_value": "ignored"}, None)]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_id])
        assert result[str(trace_id)].input is None

    @pytest.mark.asyncio
    async def test_should_extract_chat_input(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_id = uuid4()
        rows = [(trace_id, "Chat Input", uuid4(), None, {"input_value": "hello"}, None)]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_id])
        assert result[str(trace_id)].input == {"input_value": "hello"}

    @pytest.mark.asyncio
    async def test_should_return_none_output_when_no_finished_root_spans(self):
        from langflow.services.tracing.repository import fetch_trace_summary_data

        trace_id = uuid4()
        rows = [(trace_id, "root", None, None, None, {"result": "nope"})]
        result = await fetch_trace_summary_data(_make_session(rows), [trace_id])
        assert result[str(trace_id)].output is None
