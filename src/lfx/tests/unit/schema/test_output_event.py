"""Tests for ``OutputEvent`` — the per-component output shape carried on the stream.

``OutputEvent`` is the ``langflow``-protocol stream counterpart of a sync
``outputs[id]`` entry: the same ``ComponentOutput`` fields plus the
``component_id`` (which, in sync, is the dict key). One parser handles both.
"""

from __future__ import annotations

from lfx.schema.workflow import ComponentOutput, JobStatus, OutputEvent


class TestOutputEvent:
    def test_is_a_component_output_with_component_id(self):
        event = OutputEvent(
            component_id="ChatOutput-abc",
            type="message",
            status=JobStatus.COMPLETED,
            display_name="Chat Output",
            content="Hi there!",
            metadata={"component_type": "ChatOutput"},
        )
        # Same payload a parser reads off a sync ``outputs[id]`` entry...
        assert event.type == "message"
        assert event.status == JobStatus.COMPLETED
        assert event.display_name == "Chat Output"
        assert event.content == "Hi there!"
        assert event.metadata == {"component_type": "ChatOutput"}
        # ...plus the id that sync carries as the dict key.
        assert event.component_id == "ChatOutput-abc"
        # IS-A ComponentOutput, so a handler typed for the sync shape accepts it.
        assert isinstance(event, ComponentOutput)

    def test_component_id_is_required(self):
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc:
            OutputEvent(type="message", status=JobStatus.COMPLETED)
        assert "component_id" in str(exc.value)
