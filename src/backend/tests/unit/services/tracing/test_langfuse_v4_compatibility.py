"""Tests to verify langfuse v4 API compatibility.

These tests verify that the LangFuseTracer implementation is compatible
with the langfuse v4 SDK. v4 is OpenTelemetry-based: `start_observation`
replaces v3's `start_span`; trace-level attributes propagate via
`propagate_attributes`; trace-level input/output go through `set_trace_io`.

See: https://langfuse.com/docs/observability/sdk/upgrade-path/python-v3-to-v4
"""

import os
import sys
import types
import uuid
from contextlib import contextmanager
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


def _clear_failed_langfuse_import() -> None:
    """Remove partially imported Langfuse modules after SDK import failures."""
    for module_name in list(sys.modules):
        if module_name == "langfuse" or module_name.startswith("langfuse."):
            sys.modules.pop(module_name, None)


def _import_langfuse_or_skip():
    try:
        from langfuse import Langfuse
    except Exception as exc:
        _clear_failed_langfuse_import()
        pytest.skip(f"langfuse SDK is not importable: {exc}")
    return Langfuse


def _import_propagate_attributes_or_skip():
    try:
        from langfuse import propagate_attributes
    except Exception as exc:
        _clear_failed_langfuse_import()
        pytest.skip(f"langfuse propagate_attributes is not importable: {exc}")
    return propagate_attributes


def _import_callback_handler_or_skip():
    try:
        from langfuse.langchain import CallbackHandler
    except Exception as exc:
        _clear_failed_langfuse_import()
        pytest.skip(f"langfuse LangChain callback handler is not importable: {exc}")
    return CallbackHandler


class TestLangfuseV4ApiExists:
    """Verify that the langfuse v4 API surface we depend on actually exists."""

    def test_langfuse_client_has_start_observation(self):
        """v4 replaces v3 `start_span` with `start_observation` on the client."""
        langfuse_class = _import_langfuse_or_skip()

        assert hasattr(langfuse_class, "start_observation"), "Langfuse.start_observation() should exist in v4"

    def test_langfuse_client_has_create_trace_id(self):
        """`create_trace_id` is still on the class in v4."""
        langfuse_class = _import_langfuse_or_skip()

        assert hasattr(langfuse_class, "create_trace_id"), "Langfuse.create_trace_id() should exist in v4"

    def test_langfuse_module_has_propagate_attributes(self):
        """v4 introduces `propagate_attributes` for trace-level attrs."""
        propagate_attributes = _import_propagate_attributes_or_skip()

        assert callable(propagate_attributes)

    def test_langfuse_client_does_not_have_v3_start_span(self):
        """`start_span` was removed from the client in v4 (replaced by start_observation)."""
        langfuse_class = _import_langfuse_or_skip()

        assert not hasattr(langfuse_class, "start_span"), "Langfuse.start_span() should NOT exist in v4 (removed)"

    def test_callback_handler_import_path(self):
        """The langchain integration import path still resolves in v4."""
        callback_handler = _import_callback_handler_or_skip()

        assert callback_handler is not None


class TestLangfuseTracerV4Compatibility:
    """Test that LangFuseTracer works with langfuse v4 API."""

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
        """Create a mock langfuse client that simulates the v4 API."""

        class TraceContext(dict):
            pass

        mock_langfuse_module = types.ModuleType("langfuse")
        mock_langfuse_types_module = types.ModuleType("langfuse.types")
        mock_langfuse_langchain_module = types.ModuleType("langfuse.langchain")

        mock_langfuse_class = MagicMock()
        mock_langfuse_types_module.TraceContext = TraceContext
        mock_langfuse_langchain_module.CallbackHandler = MagicMock()
        mock_langfuse_module.Langfuse = mock_langfuse_class
        mock_langfuse_module.types = mock_langfuse_types_module
        mock_langfuse_module.langchain = mock_langfuse_langchain_module

        # v4: propagate_attributes is a context manager exposed at top level.
        propagate_calls: list[dict] = []

        @contextmanager
        def _propagate_attributes(**attrs):
            propagate_calls.append(attrs)
            yield None

        mock_langfuse_module.propagate_attributes = MagicMock(side_effect=_propagate_attributes)

        with patch.dict(
            sys.modules,
            {
                "langfuse": mock_langfuse_module,
                "langfuse.types": mock_langfuse_types_module,
                "langfuse.langchain": mock_langfuse_langchain_module,
            },
        ):
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            mock_langfuse_class.create_trace_id = MagicMock(return_value="a" * 32)

            # Mock health check
            mock_client.auth_check.return_value = True

            # v4 API mocks
            mock_root_span = MagicMock()
            mock_root_span.id = "root-span-id"
            mock_client.start_observation.return_value = mock_root_span

            mock_child_span = MagicMock()
            mock_child_span.id = "child-span-id"
            mock_root_span.start_observation.return_value = mock_child_span

            yield {
                "client": mock_client,
                "root_span": mock_root_span,
                "child_span": mock_child_span,
                "propagate_calls": propagate_calls,
                "propagate_attributes": mock_langfuse_module.propagate_attributes,
            }

    def test_tracer_uses_v4_api_for_initialization(self, mock_langfuse):
        """Verify tracer uses start_observation + propagate_attributes."""
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
        # v4: client.start_observation creates the root, not start_span
        mock_langfuse["client"].start_observation.assert_called_once()
        # v4: trace-level attrs are propagated, not set via update_trace
        assert mock_langfuse["propagate_attributes"].called
        ctx_attrs = mock_langfuse["propagate_calls"][0]
        assert ctx_attrs["trace_name"] == "flow-123"
        assert ctx_attrs["user_id"] == "user-1"
        assert ctx_attrs["session_id"] == "session-1"

    def test_add_trace_creates_child_observation(self, mock_langfuse):
        """Test that add_trace creates a child observation under the root."""
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

        # v4: child created via root.start_observation, not start_span
        mock_langfuse["root_span"].start_observation.assert_called_once()
        call_kwargs = mock_langfuse["root_span"].start_observation.call_args[1]
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

    def test_end_updates_root_span_and_set_trace_io(self, mock_langfuse):
        """Test that end() updates the root span, calls set_trace_io, then ends."""
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
        # v4: trace-level input/output via set_trace_io (not update_trace)
        mock_langfuse["root_span"].set_trace_io.assert_called_once()
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
        assert mock_langfuse["root_span"].start_observation.called

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
