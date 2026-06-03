"""Tests for the v2 ``WorkflowExecutionResponse`` body schema.

These pin the additive, non-breaking contract for the two DX fields layered on
top of the existing ``outputs`` map: ``output_text`` and ``session_id``. Both
are optional and default to ``None`` so a response built without them still
validates and serializes (the ``outputs`` contract is unchanged).
"""

from __future__ import annotations

from lfx.schema.workflow import JobStatus, WorkflowExecutionResponse


class TestAdditiveDefaults:
    """Omitting ``output_text`` / ``session_id`` yields null, never an error."""

    def test_omitting_the_dx_fields_defaults_to_none(self):
        resp = WorkflowExecutionResponse(flow_id="flow-1", status=JobStatus.COMPLETED)
        assert resp.output_text is None
        assert resp.session_id is None

    def test_defaults_serialize_as_null(self):
        resp = WorkflowExecutionResponse(flow_id="flow-1", status=JobStatus.COMPLETED)
        dumped = resp.model_dump(mode="json")
        assert dumped["output_text"] is None
        assert dumped["session_id"] is None

    def test_populated_values_round_trip(self):
        resp = WorkflowExecutionResponse(
            flow_id="flow-1",
            status=JobStatus.COMPLETED,
            output_text="the answer",
            session_id="session-123",
        )
        dumped = resp.model_dump(mode="json")
        assert dumped["output_text"] == "the answer"
        assert dumped["session_id"] == "session-123"

        restored = WorkflowExecutionResponse.model_validate(dumped)
        assert restored.output_text == "the answer"
        assert restored.session_id == "session-123"
