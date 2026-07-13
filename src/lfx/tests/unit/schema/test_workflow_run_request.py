"""Tests for the v2 ``WorkflowRunRequest`` body schema."""

from __future__ import annotations

import pytest
from lfx.schema.workflow import WorkflowMode, WorkflowRunRequest
from pydantic import ValidationError

_VALID_UUID = "67ccd2be-17f0-8190-81ff-3bb2cf6508e6"


class TestDefaults:
    """A minimal body should auto-populate the awesome-DX defaults."""

    def test_minimal_body_defaults_to_sync_langflow(self):
        req = WorkflowRunRequest(flow_id=_VALID_UUID)
        assert req.flow_id == _VALID_UUID
        assert req.input_value == ""
        assert req.tweaks == {}
        assert req.session_id is None
        assert req.mode is WorkflowMode.SYNC
        assert req.stream_protocol == "langflow"
        assert req.data is None
        assert req.files is None
        assert req.start_component_id is None
        assert req.stop_component_id is None
        assert req.output_ids is None

    def test_output_ids_accepts_component_id_list(self):
        req = WorkflowRunRequest(flow_id=_VALID_UUID, output_ids=["ChatOutput-abc", "ChatOutput-def"])
        assert req.output_ids == ["ChatOutput-abc", "ChatOutput-def"]

    def test_mode_accepts_string_value(self):
        req = WorkflowRunRequest(flow_id=_VALID_UUID, mode="stream")
        assert req.mode is WorkflowMode.STREAM

    def test_mode_rejects_unknown_value(self):
        with pytest.raises(ValidationError) as exc:
            WorkflowRunRequest(flow_id=_VALID_UUID, mode="async")
        assert "mode" in str(exc.value)

    def test_stream_protocol_accepts_any_string_for_registry_lookup(self):
        """The schema doesn't constrain the protocol so adapters can register at runtime.

        Endpoint-level dispatch is responsible for the 422 with the available list.
        """
        req = WorkflowRunRequest(
            flow_id=_VALID_UUID,
            mode="stream",
            stream_protocol="something-not-registered-yet",
        )
        assert req.stream_protocol == "something-not-registered-yet"


class TestFlowIdValidation:
    """``flow_id`` must be a UUID-formatted string."""

    def test_missing_flow_id_raises(self):
        with pytest.raises(ValidationError) as exc:
            WorkflowRunRequest()
        assert "flow_id" in str(exc.value)

    def test_non_uuid_flow_id_raises(self):
        with pytest.raises(ValidationError) as exc:
            WorkflowRunRequest(flow_id="not-a-uuid")
        assert "flow_id" in str(exc.value).lower() or "uuid" in str(exc.value).lower()

    def test_uppercase_uuid_accepted(self):
        upper = _VALID_UUID.upper()
        req = WorkflowRunRequest(flow_id=upper)
        assert req.flow_id == upper


class TestExtraForbid:
    """Unknown body keys must be rejected so typos surface as 422 instead of silent drops."""

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError) as exc:
            WorkflowRunRequest(flow_id=_VALID_UUID, mod="sync")
        assert "mod" in str(exc.value)


class TestRoundTripsWithRichBody:
    """A fully populated body round-trips through ``model_dump`` / ``model_validate``."""

    def test_full_body_round_trip(self):
        body = {
            "flow_id": _VALID_UUID,
            "input_value": "Hello!",
            "tweaks": {"ChatInput-abc": {"some_param": "value"}},
            "session_id": "session-123",
            "mode": "stream",
            "stream_protocol": "agui",
            "data": {"nodes": [], "edges": []},
            "files": ["/tmp/a.txt", "/tmp/b.png"],
            "start_component_id": "ChatInput-abc",
            "stop_component_id": "ChatOutput-xyz",
            "output_ids": ["ChatOutput-xyz"],
            "globals": {"API_TOKEN": "secret-123"},
            "idempotency_key": "idem-123",
        }
        req = WorkflowRunRequest.model_validate(body)
        dumped = req.model_dump(mode="json")
        assert dumped == body
