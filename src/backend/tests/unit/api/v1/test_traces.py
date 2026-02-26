"""Unit tests for trace helpers."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.api.v1.traces import (
    _build_span_tree,
    _fetch_trace_io_map,
    _fetch_trace_token_totals,
    _sanitize_query_string,
    _span_to_dict,
)
from langflow.services.database.models.traces.model import SpanStatus, SpanTable, SpanType, TraceTable


def test_span_to_dict_with_tokens():
    start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc)
    span = SpanTable(
        name="Test Span",
        span_type=SpanType.LLM,
        status=SpanStatus.ERROR,
        start_time=start_time,
        end_time=end_time,
        latency_ms=123,
        inputs={"input": "value"},
        outputs={"output": "value"},
        error="boom",
        model_name="test-model",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost=0.12,
        trace_id=uuid4(),
    )

    result = _span_to_dict(span)

    assert result["name"] == "Test Span"
    assert result["type"] == "llm"
    assert result["status"] == "error"
    assert result["startTime"] == start_time.isoformat()
    assert result["endTime"] == end_time.isoformat()
    assert result["latencyMs"] == 123
    assert result["inputs"] == {"input": "value"}
    assert result["outputs"] == {"output": "value"}
    assert result["error"] == "boom"
    assert result["modelName"] == "test-model"
    assert result["tokenUsage"] == {
        "promptTokens": 10,
        "completionTokens": 20,
        "totalTokens": 30,
        "cost": 0.12,
    }


def test_span_to_dict_without_token_usage():
    start_time = datetime(2024, 2, 1, tzinfo=timezone.utc)
    span = SpanTable(
        name="Basic Span",
        span_type=SpanType.CHAIN,
        status=SpanStatus.RUNNING,
        start_time=start_time,
        end_time=None,
        latency_ms=0,
        inputs=None,
        outputs=None,
        error=None,
        model_name=None,
        total_tokens=None,
        trace_id=uuid4(),
    )

    result = _span_to_dict(span)

    assert result["type"] == "chain"
    assert result["status"] == "running"
    assert result["startTime"] == start_time.isoformat()
    assert result["endTime"] is None
    assert result["inputs"] == {}
    assert result["outputs"] == {}
    assert result["tokenUsage"] is None


def test_sanitize_query_string_filters_and_truncates():
    assert _sanitize_query_string("  hello\nworld\t ") == "helloworld"
    assert _sanitize_query_string("a" * 60) == "a" * 50
    assert _sanitize_query_string("\n\t") is None


def test_build_span_tree_links_children():
    trace_id = uuid4()
    start_time = datetime(2024, 3, 1, tzinfo=timezone.utc)

    parent_id = uuid4()
    parent = SpanTable(
        id=parent_id,
        trace_id=trace_id,
        name="Parent",
        span_type=SpanType.CHAIN,
        status=SpanStatus.SUCCESS,
        start_time=start_time,
        latency_ms=10,
    )
    child = SpanTable(
        trace_id=trace_id,
        parent_span_id=parent_id,
        name="Child",
        span_type=SpanType.TOOL,
        status=SpanStatus.SUCCESS,
        start_time=start_time,
        latency_ms=5,
    )
    other_root = SpanTable(
        trace_id=trace_id,
        name="Other Root",
        span_type=SpanType.LLM,
        status=SpanStatus.RUNNING,
        start_time=start_time,
        latency_ms=15,
    )

    tree = _build_span_tree([child, parent, other_root])

    assert len(tree) == 2
    parent_nodes = [node for node in tree if node["name"] == "Parent"]
    assert parent_nodes
    assert parent_nodes[0]["children"][0]["name"] == "Child"


@pytest.mark.usefixtures("client")
async def test_fetch_trace_token_totals(async_session):
    trace_id = uuid4()
    other_trace_id = uuid4()
    trace = TraceTable(name="Trace", flow_id=uuid4(), session_id="s1", id=trace_id)
    other_trace = TraceTable(name="Other", flow_id=uuid4(), session_id="s2", id=other_trace_id)
    async_session.add_all([trace, other_trace])

    parent_id = uuid4()
    spans = [
        SpanTable(
            id=parent_id,
            trace_id=trace_id,
            name="Parent",
            span_type=SpanType.CHAIN,
            status=SpanStatus.SUCCESS,
            total_tokens=100,
        ),
        SpanTable(
            trace_id=trace_id,
            parent_span_id=parent_id,
            name="Child",
            span_type=SpanType.LLM,
            status=SpanStatus.SUCCESS,
            total_tokens=5,
        ),
        SpanTable(
            trace_id=trace_id,
            name="Leaf",
            span_type=SpanType.TOOL,
            status=SpanStatus.SUCCESS,
            total_tokens=7,
        ),
    ]
    async_session.add_all(spans)
    await async_session.commit()

    token_map = await _fetch_trace_token_totals(async_session, [trace_id, other_trace_id])

    assert token_map[str(trace_id)] == 12
    assert str(other_trace_id) not in token_map


@pytest.mark.usefixtures("client")
async def test_fetch_trace_io_map(async_session):
    trace_id = uuid4()
    trace = TraceTable(name="Trace", flow_id=uuid4(), session_id="s1", id=trace_id)
    async_session.add(trace)

    base_time = datetime(2024, 4, 1, tzinfo=timezone.utc)
    spans = [
        SpanTable(
            trace_id=trace_id,
            name="Chat Input",
            span_type=SpanType.CHAIN,
            status=SpanStatus.SUCCESS,
            inputs={"input_value": "hello"},
        ),
        SpanTable(
            trace_id=trace_id,
            name="Root A",
            span_type=SpanType.CHAIN,
            status=SpanStatus.SUCCESS,
            end_time=base_time,
            outputs={"output": "first"},
        ),
        SpanTable(
            trace_id=trace_id,
            name="Root B",
            span_type=SpanType.CHAIN,
            status=SpanStatus.SUCCESS,
            end_time=base_time.replace(minute=1),
            outputs={"output": "latest"},
        ),
    ]
    async_session.add_all(spans)
    await async_session.commit()

    io_map = await _fetch_trace_io_map(async_session, [trace_id])

    assert io_map[str(trace_id)]["input"] == {"input_value": "hello"}
    assert io_map[str(trace_id)]["output"] == {"output": "latest"}
