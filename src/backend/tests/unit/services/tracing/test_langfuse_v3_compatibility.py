"""Tests to verify langfuse v3 API compatibility.

These tests verify that the LangFuseTracer implementation is compatible
with the langfuse v3 SDK. The v3 SDK removed several methods that the
v2 API used, so we need to ensure our implementation uses the correct API.

See: https://langfuse.com/docs/observability/sdk/upgrade-path
"""

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def langfuse_env_vars():
    """Set fake langfuse credentials for testing."""
    with patch.dict(
        os.environ,
        {
            "LANGFUSE_SECRET_KEY": "sk-lf-test",  # pragma: allowlist secret
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_HOST": "http://localhost:3000",
        },
    ):
        yield


class TestLangfuseV3ApiExists:
    """Verify that the langfuse v3 API methods we need actually exist."""

    def test_langfuse_client_has_start_span(self):
        """Verify start_span method exists (v3 API)."""
        from langfuse import Langfuse

        assert hasattr(Langfuse, "start_span"), "Langfuse.start_span() should exist in v3"

    def test_langfuse_client_has_start_as_current_span(self):
        """Verify start_as_current_span method exists (v3 API)."""
        from langfuse import Langfuse

        assert hasattr(Langfuse, "start_as_current_span"), "Langfuse.start_as_current_span() should exist in v3"

    def test_langfuse_client_has_create_trace_id(self):
        """Verify create_trace_id method exists (v3 API)."""
        from langfuse import Langfuse

        assert hasattr(Langfuse, "create_trace_id"), "Langfuse.create_trace_id() should exist in v3"

    def test_langfuse_client_does_not_have_trace(self):
        """Verify trace() method was removed in v3."""
        from langfuse import Langfuse

        # This test documents that trace() no longer exists
        # If this fails, langfuse may have restored backward compatibility
        assert not hasattr(Langfuse, "trace"), "Langfuse.trace() should NOT exist in v3 (removed)"

    def test_callback_handler_import_path(self):
        """Verify the v3 callback handler import path works."""
        # v3 path
        from langfuse.langchain import CallbackHandler

        assert CallbackHandler is not None


class TestLangfuseTracerV3Compatibility:
    """Test that LangFuseTracer works with langfuse v3 API."""

    def test_tracer_initialization_does_not_crash(self):
        """Tracer should initialize without crashing (may not be ready without server)."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        # Should not raise an exception
        tracer = LangFuseTracer(
            trace_name="test-flow - test-id",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
            user_id="test-user",
            session_id="test-session",
        )
        # Tracer won't be ready without a server, but shouldn't crash
        assert isinstance(tracer.ready, bool)


class TestLangfuseTracerFunctionality:
    """Test LangFuseTracer functionality with mocked langfuse client."""

    @pytest.fixture
    def mock_langfuse(self):
        """Create a mock langfuse client that simulates v3 API."""
        with patch("langfuse.Langfuse") as mock_langfuse_class:
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            mock_langfuse_class.create_trace_id = MagicMock(return_value="a" * 32)

            # Mock health check (auth_check in v3)
            mock_client.auth_check.return_value = True

            # V3 API mocks
            mock_root_span = MagicMock()
            mock_root_span.id = "root-span-id"
            mock_client.start_span.return_value = mock_root_span

            mock_child_span = MagicMock()
            mock_child_span.id = "child-span-id"
            mock_root_span.start_span.return_value = mock_child_span

            yield {
                "client": mock_client,
                "root_span": mock_root_span,
                "child_span": mock_child_span,
            }

    def test_tracer_uses_v3_api_for_initialization(self, mock_langfuse):
        """Verify tracer uses start_span instead of removed trace() method."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracer = LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
            user_id="user-1",
            session_id="session-1",
        )

        assert tracer.ready
        # Should use v3 start_span, not v2 trace()
        mock_langfuse["client"].start_span.assert_called_once()
        # Should set trace metadata via update_trace
        mock_langfuse["root_span"].update_trace.assert_called()

    def test_add_trace_creates_child_span(self, mock_langfuse):
        """Test that add_trace creates a child span using v3 API."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracer = LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )

        tracer.add_trace(
            trace_id="component-1",
            trace_name="TestComponent (component-1)",
            trace_type="llm",
            inputs={"prompt": "test"},
            metadata={"key": "value"},
        )

        # Should create child span under root span
        mock_langfuse["root_span"].start_span.assert_called_once()
        call_kwargs = mock_langfuse["root_span"].start_span.call_args[1]
        assert call_kwargs["name"] == "TestComponent"

    def test_end_trace_updates_and_ends_span(self, mock_langfuse):
        """Test that end_trace updates span with output and ends it."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracer = LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )

        # Add then end a trace
        tracer.add_trace("comp-1", "Test (comp-1)", "llm", {"input": "test"})
        tracer.end_trace("comp-1", "Test", outputs={"output": "result"})

        # Should update and end the child span
        mock_langfuse["child_span"].update.assert_called()
        mock_langfuse["child_span"].end.assert_called()

    def test_end_updates_root_span_and_trace(self, mock_langfuse):
        """Test that end() updates both root span and trace, then ends."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracer = LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )

        tracer.end(
            inputs={"flow_input": "test"},
            outputs={"flow_output": "result"},
            metadata={"final": True},
        )

        # Should update root span
        mock_langfuse["root_span"].update.assert_called()
        # Should update trace metadata
        assert mock_langfuse["root_span"].update_trace.call_count >= 2  # init + end
        # Should end root span
        mock_langfuse["root_span"].end.assert_called()

    def test_get_langchain_callback_uses_trace_context(self, mock_langfuse):
        """Test that get_langchain_callback creates handler with trace context."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracer = LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )

        # Add a span first (uses mock_langfuse fixture)
        tracer.add_trace("comp-1", "Test", "llm", {})
        assert mock_langfuse["root_span"].start_span.called

        with patch("langfuse.langchain.CallbackHandler") as mock_handler:
            mock_handler.return_value = MagicMock()
            tracer.get_langchain_callback()

            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args[1]
            assert "trace_context" in call_kwargs
            assert "trace_id" in call_kwargs["trace_context"]

    def test_get_langchain_callback_includes_parent_span_id(self, mock_langfuse):
        """Test that callback handler gets parent span ID for proper nesting."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        tracer = LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )

        # Add a span to be used as parent (uses mock_langfuse fixture)
        tracer.add_trace("comp-1", "Test", "llm", {})
        assert mock_langfuse["child_span"].id == "child-span-id"

        with patch("langfuse.langchain.CallbackHandler") as mock_handler:
            mock_handler.return_value = MagicMock()
            tracer.get_langchain_callback()

            call_kwargs = mock_handler.call_args[1]
            trace_context = call_kwargs["trace_context"]
            assert "parent_span_id" in trace_context
            assert trace_context["parent_span_id"] == "child-span-id"
