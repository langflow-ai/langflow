"""Tests for the manage_files routing and SSE pipeline in assistant_service.

These tests focus on three behaviors that B4 introduces:
1. The TranslationFlow's ``manage_files`` intent routes to the same flow as
   ``build_flow`` (flow_builder_assistant) since the toolkit was merged in B3.
2. The first progress event for a ``manage_files`` request uses the
   ``generating_document`` step (label "Generating document...").
3. ``drain_file_events`` is called inside the streaming loop and each emitted
   entry is yielded as an SSE ``file_written`` event.
"""

from __future__ import annotations

import json

import pytest
from langflow.agentic.helpers.sse import (
    format_file_written_event,
)


class TestFormatFileWrittenEvent:
    """B4 — SSE formatter for file_written entries."""

    def test_format_file_written_event_should_carry_action_path_and_size(self):
        payload = format_file_written_event(
            action="write_file",
            path="DOCS.md",
            size=1234,
        )

        # Strip "data: " prefix and trailing newlines, then parse the JSON body.
        assert payload.startswith("data: ")
        assert payload.endswith("\n\n")
        body = json.loads(payload[len("data: ") : -2])
        assert body == {
            "event": "file_written",
            "action": "write_file",
            "path": "DOCS.md",
            "size": 1234,
        }

    def test_format_file_written_event_should_refuse_absolute_path(self):
        # Defense in depth — the formatter is the last hop before the wire.
        with pytest.raises(ValueError, match="absolute"):
            format_file_written_event(action="write_file", path="/etc/passwd", size=1)


class TestStepTypeIncludesGeneratingDocument:
    """B4 — StepType Literal includes the new step values."""

    def test_step_type_should_include_generating_document(self):
        # Literal types are introspectable via typing.get_args.
        from typing import get_args

        from langflow.agentic.api.schemas import StepType

        members = set(get_args(StepType))
        assert "generating_document" in members, members
        assert "document_ready" in members, members


class TestStreamingEmitsFileWrittenEvents:
    """B4 — SSE pipeline yields file_written events drained between tokens."""

    @pytest.mark.asyncio
    async def test_stream_should_yield_file_written_when_file_events_pending(self, monkeypatch):
        """End-to-end-ish: with a stubbed flow generator emitting a 'token' event,
        a pending file_event in the queue must surface as a file_written SSE line
        before the token line in the output.

        We exercise the streaming function with a fake flow_generator and assert
        on the textual SSE output. This pinpoints the drain insertion point
        without requiring a real LLM call.
        """  # noqa: D205
        from langflow.agentic.services import assistant_service
        from langflow.agentic.services.file_events import emit_file_event, reset_file_events

        # Arrange — stub classify_intent to return manage_files (routes to same flow).
        async def fake_classify_intent(*args, **kwargs):  # noqa: ARG001
            from langflow.agentic.services.flow_types import IntentResult

            return IntentResult(translation="hi", intent="manage_files")

        monkeypatch.setattr(assistant_service, "classify_intent", fake_classify_intent)

        # Stub the flow generator: emit one token, then end with a benign result.
        async def fake_flow_streaming(*args, **kwargs):  # noqa: ARG001
            # Push a file event from inside the same task so it lands in this context.
            emit_file_event(action="write_file", path="DOCS.md", size=10)
            yield ("token", "ok")
            yield ("end", {"result": "wrote docs"})

        monkeypatch.setattr(
            assistant_service,
            "execute_flow_file_streaming",
            fake_flow_streaming,
        )

        # Stub _get_current_flow_summary so we don't touch the DB.
        async def fake_summary(_flow_id, **_kwargs):  # accepts user_id kwarg from production (I2)
            return None

        monkeypatch.setattr(
            assistant_service,
            "_get_current_flow_summary",
            fake_summary,
        )

        reset_file_events()

        # Act — collect every SSE line.
        sse_lines: list[str] = [
            line
            async for line in assistant_service.execute_flow_with_validation_streaming(
                flow_filename="LangflowAssistant.json",  # default; overridden internally by intent
                input_value="crie um doc",
                global_variables={"FLOW_ID": None},
                max_retries=0,
                user_id="u1",
                session_id="agentic_session_1",
                provider="OpenAI",
                model_name="gpt-4o-mini",
                api_key_var=None,
                is_disconnected=None,
            )
        ]

        # Assert — at least one SSE line is a file_written event with the right path.
        file_written = [line for line in sse_lines if '"event": "file_written"' in line]
        assert file_written, f"Expected a file_written SSE event, got: {sse_lines}"
        body = json.loads(file_written[0][len("data: ") : -2])
        assert body["path"] == "DOCS.md"
        assert body["action"] == "write_file"
        assert body["size"] == 10

    @pytest.mark.asyncio
    async def test_stream_should_emit_generating_document_step_for_manage_files(self, monkeypatch):
        """The first progress event for manage_files intent must use the
        generating_document step (so the frontend label says
        "Generating document..." instead of "Generating flow...").
        """  # noqa: D205
        from langflow.agentic.services import assistant_service
        from langflow.agentic.services.file_events import reset_file_events

        async def fake_classify_intent(*args, **kwargs):  # noqa: ARG001
            from langflow.agentic.services.flow_types import IntentResult

            return IntentResult(translation="hi", intent="manage_files")

        monkeypatch.setattr(assistant_service, "classify_intent", fake_classify_intent)

        async def fake_flow_streaming(*args, **kwargs):  # noqa: ARG001
            yield ("end", {"result": "ok"})

        monkeypatch.setattr(
            assistant_service,
            "execute_flow_file_streaming",
            fake_flow_streaming,
        )

        async def fake_summary(_flow_id, **_kwargs):  # accepts user_id kwarg from production (I2)
            return None

        monkeypatch.setattr(
            assistant_service,
            "_get_current_flow_summary",
            fake_summary,
        )

        reset_file_events()

        sse_lines: list[str] = [
            line
            async for line in assistant_service.execute_flow_with_validation_streaming(
                flow_filename="LangflowAssistant.json",  # default; overridden internally by intent
                input_value="crie um doc",
                global_variables={"FLOW_ID": None},
                max_retries=0,
                user_id="u1",
                session_id="agentic_session_1",
                provider="OpenAI",
                model_name="gpt-4o-mini",
                api_key_var=None,
                is_disconnected=None,
            )
        ]

        # First progress event should be generating_document.
        first_progress = next(line for line in sse_lines if '"event": "progress"' in line)
        body = json.loads(first_progress[len("data: ") : -2])
        assert body["step"] == "generating_document", body
        # And the user-facing message should say so.
        assert "document" in (body.get("message") or "").lower(), body
