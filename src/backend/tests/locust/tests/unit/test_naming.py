"""Unit tests for metric_name high-cardinality rejection."""

from __future__ import annotations

import pytest

from tests.locust.langflow_runtime.config.naming import metric_name


def test_metric_name_accepts_static_segments() -> None:
    assert metric_name("mcp", "tools_call", "protocol_calibration", "passthrough") == (
        "mcp:tools_call:protocol_calibration:passthrough"
    )


def test_metric_name_rejects_uuids() -> None:
    with pytest.raises(ValueError, match="high-cardinality"):
        metric_name(
            "mcp",
            "tools_call",
            "protocol_calibration",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )


def test_metric_name_rejects_job_id_tokens() -> None:
    with pytest.raises(ValueError, match="high-cardinality"):
        metric_name("workflows", "get_status", "queue", "job_id_abc")


def test_metric_name_rejects_env_tagged_kb_names() -> None:
    with pytest.raises(ValueError, match="high-cardinality"):
        metric_name("workflows", "run_sync", "kb_retrieve", "perf_kb_perf_local")


def test_metric_name_rejects_session_tokens() -> None:
    with pytest.raises(ValueError, match="high-cardinality"):
        metric_name("workflows", "run_sync", "chat_db", "session_id_abc")
