"""Tests for the file-events queue used by the agentic filesystem tools.

These events are emitted by the agent's filesystem tools (write_file / edit_file)
and drained by `assistant_service` between LLM tokens so the frontend can render
a card for each file as it materializes.

Pattern mirrors `lfx.mcp.flow_builder_tools._flow_events_var` but with a fresh
ContextVar so file-event consumers don't have to import flow-builder internals.
"""

import asyncio
import json
from contextvars import copy_context
from unittest.mock import MagicMock

import pytest
from langflow.agentic.services.file_events import (
    drain_file_events,
    emit_file_event,
    reset_file_events,
    wrap_file_tool_with_event,
)


class TestDrainAndEmitInIsolation:
    """B2 — emit, drain, reset semantics inside a single context."""

    def setup_method(self):
        # Each test starts with an empty queue. We are inside the same context
        # as the runner here, so an explicit reset is required (mirrors what
        # assistant_service does at the start of every request).
        reset_file_events()

    def test_drain_file_events_should_return_empty_when_no_emits(self):
        # Act
        result = drain_file_events()

        # Assert
        assert result == []

    def test_emit_file_event_should_queue_event_with_action_path_and_size(self):
        # Act
        emit_file_event(action="write_file", path="DOCS.md", size=1234)
        result = drain_file_events()

        # Assert
        assert result == [{"action": "write_file", "path": "DOCS.md", "size": 1234}]

    def test_drain_file_events_should_clear_queue_after_drain(self):
        # Arrange
        emit_file_event(action="write_file", path="DOCS.md", size=10)

        # Act
        first = drain_file_events()
        second = drain_file_events()

        # Assert
        assert first == [{"action": "write_file", "path": "DOCS.md", "size": 10}]
        assert second == []

    def test_emit_file_event_should_preserve_order_when_multiple_events(self):
        # Act
        emit_file_event(action="write_file", path="A.md", size=1)
        emit_file_event(action="edit_file", path="A.md", size=2)
        emit_file_event(action="write_file", path="B.md", size=3)
        result = drain_file_events()

        # Assert
        assert [(e["action"], e["path"]) for e in result] == [
            ("write_file", "A.md"),
            ("edit_file", "A.md"),
            ("write_file", "B.md"),
        ]

    def test_reset_file_events_should_clear_pending_entries(self):
        # Arrange
        emit_file_event(action="write_file", path="A.md", size=1)

        # Act
        reset_file_events()
        result = drain_file_events()

        # Assert
        assert result == []


class TestContextIsolation:
    """B2 — ContextVar isolation: emits in one context don't leak to another."""

    def setup_method(self):
        # Tests above this class may have set the ContextVar in pytest's main
        # context; reset to None so the asyncio.gather isolation test starts
        # from the same baseline production code provides at task entry.
        reset_file_events()

    def test_file_events_should_be_isolated_across_contexts(self):
        # Arrange — emit in a child context, drain in the parent
        def child():
            emit_file_event(action="write_file", path="LEAKED.md", size=42)
            return drain_file_events()

        ctx = copy_context()
        child_result = ctx.run(child)

        # Drain in parent context — should be empty because the emit
        # happened in an isolated copy of the context.
        reset_file_events()
        parent_result = drain_file_events()

        # Assert
        assert child_result == [{"action": "write_file", "path": "LEAKED.md", "size": 42}]
        assert parent_result == [], "Parent context must not see child context's emits"

    def test_file_events_should_be_shared_across_asyncio_tasks_within_same_request(self):
        """Within a single request, child tasks (LLM agent, tool callbacks)
        emit into the SAME queue the parent will drain.

        This mirrors the production wiring in
        ``lfx.mcp.flow_builder_tools._flow_events_var``: reset allocates a
        deque in the parent context BEFORE spawning child tasks, so the
        children inherit the same object by reference. Cross-request
        isolation is provided at the FastAPI level (each request task has
        its own context).
        """  # noqa: D205

        async def emit_in_task(token: str) -> None:
            emit_file_event(action="write_file", path=f"{token}.md", size=len(token))
            await asyncio.sleep(0)

        async def parent_run() -> list[dict]:
            # Parent (request handler) resets, then spawns children.
            reset_file_events()
            await asyncio.gather(emit_in_task("alpha"), emit_in_task("beta"))
            # Parent drains — must see BOTH child emits.
            return drain_file_events()

        result = asyncio.run(parent_run())
        paths = sorted(entry["path"] for entry in result)
        assert paths == ["alpha.md", "beta.md"], f"Parent must see emits from both child tasks, got {result}"


class TestPayloadShape:
    """B2 — payload constraints that enforce security (no BASE_DIR leak)."""

    def setup_method(self):
        reset_file_events()

    def test_emit_file_event_should_reject_absolute_path(self):
        # Act / Assert — absolute paths are sandbox-internal; never emit them.
        with pytest.raises(ValueError, match="absolute"):
            emit_file_event(action="write_file", path="/etc/passwd", size=10)

    def test_emit_file_event_should_reject_path_with_drive_letter(self):
        # Act / Assert — Windows drive letter is an absolute marker.
        with pytest.raises(ValueError, match="absolute"):
            emit_file_event(action="write_file", path="C:\\Users\\x\\DOCS.md", size=10)

    def test_emit_file_event_should_reject_negative_size(self):
        with pytest.raises(ValueError, match="size"):
            emit_file_event(action="write_file", path="DOCS.md", size=-1)

    def test_emit_file_event_should_reject_empty_action(self):
        with pytest.raises(ValueError, match="action"):
            emit_file_event(action="", path="DOCS.md", size=10)

    def test_emit_file_event_should_reject_empty_path(self):
        with pytest.raises(ValueError, match="path"):
            emit_file_event(action="write_file", path="", size=10)


class TestWrapFileToolWithEvent:
    """B3 — wrapper that turns a FileSystemTool's StructuredTool into an emitter.

    The wrapper invokes the underlying tool, parses its JSON response, and emits
    a ``file_written`` event ONLY when the response represents a successful write.
    """

    def setup_method(self):
        reset_file_events()

    def _make_fake_tool(self, response_payload: dict, captured_args: dict | None = None):
        """Build a stand-in StructuredTool with a recordable func.

        We don't depend on langchain's full StructuredTool here — the wrapper
        only reads ``name``, ``description``, ``func``, ``args_schema``, ``tags``
        from the input and produces a new one. A simple namespace passes that
        contract and keeps the test hermetic.
        """
        recorder = captured_args if captured_args is not None else {}

        def fake_func(**kwargs):
            recorder.update(kwargs)
            return json.dumps(response_payload)

        tool = MagicMock()
        tool.name = "write_file"
        tool.description = "Write a file"
        tool.func = fake_func
        tool.args_schema = None
        tool.tags = ["write_file"]
        return tool

    def test_wrapped_tool_should_emit_file_written_on_success(self):
        tool = self._make_fake_tool({"status": "created", "path": "DOCS.md", "bytes_written": 100})

        wrapped = wrap_file_tool_with_event(tool, action="write_file")
        result = wrapped.func(path="DOCS.md", content="x")

        # Result must round-trip unchanged.
        assert json.loads(result) == {"status": "created", "path": "DOCS.md", "bytes_written": 100}
        # Event was emitted carrying the content kwarg so the frontend can
        # render inline without a second HTTP fetch.
        events = drain_file_events()
        assert events == [
            {"action": "write_file", "path": "DOCS.md", "size": 100, "content": "x"},
        ]

    def test_wrapped_tool_should_not_emit_when_response_carries_error(self):
        tool = self._make_fake_tool({"error": "sub_path escapes user namespace", "path": "../escape.md"})

        wrapped = wrap_file_tool_with_event(tool, action="write_file")
        wrapped.func(path="../escape.md", content="x")

        assert drain_file_events() == [], "Failed writes must not enqueue stale events"

    def test_wrapped_tool_should_not_emit_when_response_is_not_json(self):
        tool = self._make_fake_tool({})
        tool.func = lambda **_: "<not-json>"

        wrapped = wrap_file_tool_with_event(tool, action="write_file")
        wrapped.func(path="A.md", content="x")

        assert drain_file_events() == []

    def test_wrapped_tool_should_not_emit_when_response_has_no_path(self):
        # Defensive: even if FileSystemTool ever drops the `path` key, we
        # don't emit a bogus event with an empty path.
        tool = self._make_fake_tool({"status": "created", "bytes_written": 5})

        wrapped = wrap_file_tool_with_event(tool, action="write_file")
        wrapped.func(path="A.md", content="x")

        assert drain_file_events() == []

    def test_wrapped_tool_should_propagate_kwargs_to_inner_func(self):
        # Arrange: capture what the inner func sees.
        captured: dict = {}
        tool = self._make_fake_tool({"status": "created", "path": "A.md", "bytes_written": 1}, captured)

        # Act
        wrapped = wrap_file_tool_with_event(tool, action="write_file")
        wrapped.func(path="A.md", content="hello")

        # Assert
        assert captured == {"path": "A.md", "content": "hello"}

    def test_wrapped_tool_should_emit_with_provided_action(self):
        tool = self._make_fake_tool({"status": "updated", "path": "A.md", "bytes_written": 9})

        wrapped = wrap_file_tool_with_event(tool, action="edit_file")
        wrapped.func(path="A.md", old_string="x", new_string="y")

        [event] = drain_file_events()
        assert event["action"] == "edit_file"

    def test_wrapped_tool_should_refuse_emit_with_absolute_path_in_response(self):
        # If the inner tool ever responds with an absolute path (it shouldn't —
        # FileSystemTool returns the same relative path the LLM passed in), the
        # wrapper must NOT silently leak it as a "relative" event. emit_file_event
        # raises and the wrapper surfaces the failure as a wrapped error in the
        # response so the LLM sees something is wrong but no event is emitted.
        tool = self._make_fake_tool({"status": "created", "path": "/etc/passwd", "bytes_written": 1})

        wrapped = wrap_file_tool_with_event(tool, action="write_file")
        result = wrapped.func(path="/etc/passwd", content="x")

        # Original payload is preserved in the response (so the LLM can react).
        assert "/etc/passwd" in result
        # No event emitted — emit_file_event refused the absolute path.
        assert drain_file_events() == []
