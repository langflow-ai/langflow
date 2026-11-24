"""Tests for the v2 ``WorkflowExecutionResponse`` body schema.

These pin the contract for the DX fields layered on top of the ``outputs`` map:
``output`` (the resolved text answer plus its ``reason``), ``session_id``, and
the derived ``has_errors`` flag. A response built without them still validates
and serializes (the ``outputs`` contract is unchanged).
"""

from __future__ import annotations

from lfx.schema.workflow import (
    ErrorDetail,
    JobStatus,
    OutputReason,
    WorkflowExecutionResponse,
    WorkflowOutput,
)


class TestDefaults:
    """A response built without the DX fields still validates and serializes."""

    def test_omitting_output_defaults_to_reason_none(self):
        resp = WorkflowExecutionResponse(flow_id="flow-1", status=JobStatus.COMPLETED)
        assert resp.output.reason == OutputReason.NONE
        assert resp.output.text is None
        assert resp.output.source is None
        assert resp.session_id is None

    def test_defaults_serialize(self):
        resp = WorkflowExecutionResponse(flow_id="flow-1", status=JobStatus.COMPLETED)
        dumped = resp.model_dump(mode="json")
        assert dumped["output"] == {"reason": "none", "text": None, "source": None}
        assert dumped["session_id"] is None
        assert dumped["has_errors"] is False

    def test_populated_output_round_trips(self):
        resp = WorkflowExecutionResponse(
            flow_id="flow-1",
            status=JobStatus.COMPLETED,
            output=WorkflowOutput(reason=OutputReason.SINGLE, text="the answer", source="ChatOutput-abc"),
            session_id="session-123",
        )
        dumped = resp.model_dump(mode="json")
        assert dumped["output"] == {"reason": "single", "text": "the answer", "source": "ChatOutput-abc"}
        assert dumped["session_id"] == "session-123"

        restored = WorkflowExecutionResponse.model_validate(dumped)
        assert restored.output.reason == OutputReason.SINGLE
        assert restored.output.text == "the answer"
        assert restored.output.source == "ChatOutput-abc"
        assert restored.session_id == "session-123"


class TestHasErrors:
    """``has_errors`` is derived from ``errors`` so it can't drift."""

    def test_clean_response_has_no_errors(self):
        resp = WorkflowExecutionResponse(flow_id="flow-1", status=JobStatus.COMPLETED)
        assert resp.has_errors is False
        assert resp.model_dump(mode="json")["has_errors"] is False

    def test_response_with_errors_reports_true(self):
        resp = WorkflowExecutionResponse(
            flow_id="flow-1",
            status=JobStatus.FAILED,
            errors=[ErrorDetail(error="boom")],
        )
        assert resp.has_errors is True
        assert resp.model_dump(mode="json")["has_errors"] is True
