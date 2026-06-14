"""Tests to verify langfuse v3 API compatibility.

These tests verify that the LangFuseTracer implementation is compatible
with the langfuse v3 SDK. The v3 SDK removed several methods that the
v2 API used, so we need to ensure our implementation uses the correct API.

See: https://langfuse.com/docs/observability/sdk/upgrade-path
"""

import os
import sys
import types
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


@pytest.fixture(autouse=True)
def reset_langfuse_shared_client():
    """Clear the cached Langfuse client between tests so mocks don't leak."""
    from langflow.services.tracing.langfuse import _reset_shared_client_for_tests

    _reset_shared_client_for_tests()
    yield
    _reset_shared_client_for_tests()


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


def _import_callback_handler_or_skip():
    try:
        from langfuse.langchain import CallbackHandler
    except Exception as exc:
        _clear_failed_langfuse_import()
        pytest.skip(f"langfuse LangChain callback handler is not importable: {exc}")
    return CallbackHandler


class TestLangfuseV3ApiExists:
    """Verify that the langfuse v3 API methods we need actually exist."""

    def test_langfuse_client_has_start_span(self):
        """Verify start_span method exists (v3 API)."""
        langfuse_class = _import_langfuse_or_skip()

        assert hasattr(langfuse_class, "start_span"), "Langfuse.start_span() should exist in v3"

    def test_langfuse_client_has_start_as_current_span(self):
        """Verify start_as_current_span method exists (v3 API)."""
        langfuse_class = _import_langfuse_or_skip()

        assert hasattr(langfuse_class, "start_as_current_span"), "Langfuse.start_as_current_span() should exist in v3"

    def test_langfuse_client_has_create_trace_id(self):
        """Verify create_trace_id method exists (v3 API)."""
        langfuse_class = _import_langfuse_or_skip()

        assert hasattr(langfuse_class, "create_trace_id"), "Langfuse.create_trace_id() should exist in v3"

    def test_langfuse_client_does_not_have_trace(self):
        """Verify trace() method was removed in v3."""
        langfuse_class = _import_langfuse_or_skip()

        # This test documents that trace() no longer exists
        # If this fails, langfuse may have restored backward compatibility
        assert not hasattr(langfuse_class, "trace"), "Langfuse.trace() should NOT exist in v3 (removed)"

    def test_callback_handler_import_path(self):
        """Verify the v3 callback handler import path works."""
        # v3 path
        callback_handler = _import_callback_handler_or_skip()

        assert callback_handler is not None


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

    def test_trace_user_id_uses_auth_user_when_no_tracing_override(self, mock_langfuse):
        """``trace.userId`` should be the authenticated Langflow user (pre-#9505 behavior)."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
            user_id="auth-user",
            session_id="session-1",
        )

        update_kwargs = mock_langfuse["root_span"].update_trace.call_args.kwargs
        assert update_kwargs["user_id"] == "auth-user"
        # No override → no metadata payload was supplied for the override.
        assert "metadata" not in update_kwargs

    def test_trace_user_id_stays_auth_user_and_override_goes_to_metadata(self, mock_langfuse):
        """``tracing_user_id`` must not redefine ``trace.userId``; it is stamped in metadata.

        Regression for GitHub issue #9505 / PR #13266 review: external Langfuse
        consumers depend on ``trace.userId`` continuing to mean the authenticated
        Langflow user. The caller-supplied override surfaces as
        ``metadata.langflow.tracing_user_id`` instead.
        """
        from langflow.services.tracing.langfuse import LangFuseTracer

        LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
            user_id="auth-user",
            session_id="session-1",
            tracing_user_id="end-user-456",
        )

        update_kwargs = mock_langfuse["root_span"].update_trace.call_args.kwargs
        assert update_kwargs["user_id"] == "auth-user"
        assert update_kwargs["metadata"] == {"langflow.tracing_user_id": "end-user-456"}

    def test_tracing_user_id_equal_to_auth_user_is_not_stamped(self, mock_langfuse):
        """When the override matches the auth user there is nothing extra to record."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        LangFuseTracer(
            trace_name="test-flow - flow-123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
            user_id="same-user",
            session_id="session-1",
            tracing_user_id="same-user",
        )

        update_kwargs = mock_langfuse["root_span"].update_trace.call_args.kwargs
        assert update_kwargs["user_id"] == "same-user"
        assert "metadata" not in update_kwargs

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


class TestLangfuseClientSingleton:
    """Verify the Langfuse client is constructed once and reused across flow runs.

    Regression test for https://github.com/langflow-ai/langflow/issues/9066.
    """

    def test_single_client_for_multiple_flow_runs(self):
        """A single Langfuse() client must be reused across all flow runs.

        Background threads (task_manager, prompt_cache, OTel exporters) are
        spawned per client and never joined, so a per-run client leaks threads.
        """
        from langflow.services.tracing.langfuse import LangFuseTracer

        n_runs = 5

        with patch("langfuse.Langfuse") as mock_langfuse_class:
            mock_langfuse_class.create_trace_id = MagicMock(return_value="a" * 32)
            mock_client = MagicMock()
            mock_client.auth_check.return_value = True
            mock_langfuse_class.return_value = mock_client

            for _ in range(n_runs):
                LangFuseTracer(
                    trace_name="test-flow - flow-id",
                    trace_type="chain",
                    project_name="test-project",
                    trace_id=uuid.uuid4(),
                )

            # After fix: Langfuse() must be instantiated exactly once,
            # regardless of how many flows run.
            assert mock_langfuse_class.call_count == 1

    def test_end_calls_client_flush(self):
        """end() must flush buffered events so they're sent before the trace finishes."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        with patch("langfuse.Langfuse") as mock_langfuse_class:
            mock_langfuse_class.create_trace_id = MagicMock(return_value="a" * 32)
            mock_client = MagicMock()
            mock_client.auth_check.return_value = True
            mock_root_span = MagicMock()
            mock_client.start_span.return_value = mock_root_span
            mock_langfuse_class.return_value = mock_client

            tracer = LangFuseTracer(
                trace_name="test-flow - flow-id",
                trace_type="chain",
                project_name="test-project",
                trace_id=uuid.uuid4(),
            )
            tracer.end(inputs={"a": 1}, outputs={"b": 2})

            mock_client.flush.assert_called_once()

    def test_end_swallows_flush_errors(self):
        """A failing flush() must not break flow end."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        with patch("langfuse.Langfuse") as mock_langfuse_class:
            mock_langfuse_class.create_trace_id = MagicMock(return_value="a" * 32)
            mock_client = MagicMock()
            mock_client.auth_check.return_value = True
            mock_client.flush.side_effect = RuntimeError("upstream down")
            mock_root_span = MagicMock()
            mock_client.start_span.return_value = mock_root_span
            mock_langfuse_class.return_value = mock_client

            tracer = LangFuseTracer(
                trace_name="test-flow - flow-id",
                trace_type="chain",
                project_name="test-project",
                trace_id=uuid.uuid4(),
            )
            # Should not raise even though flush() blew up.
            tracer.end(inputs={"a": 1}, outputs={"b": 2})

            mock_client.flush.assert_called_once()

    def test_feedback_helper_reuses_shared_client(self):
        """`_get_langfuse_client()` (used by feedback scoring) must reuse the singleton."""
        from langflow.services.tracing.langfuse import _get_langfuse_client

        with patch("langfuse.Langfuse") as mock_langfuse_class:
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client

            client_a = _get_langfuse_client()
            client_b = _get_langfuse_client()

            assert client_a is client_b
            assert mock_langfuse_class.call_count == 1

    def test_credential_change_creates_new_client(self):
        """Rotating credentials should produce a fresh client, not reuse the stale one."""
        from langflow.services.tracing.langfuse import _get_langfuse_client

        with patch("langfuse.Langfuse") as mock_langfuse_class:
            mock_langfuse_class.return_value = MagicMock()

            _get_langfuse_client()
            assert mock_langfuse_class.call_count == 1

            # Rotate credentials and call again.
            with patch.dict(
                os.environ,
                {
                    "LANGFUSE_SECRET_KEY": "sk-lf-rotated",  # pragma: allowlist secret
                    "LANGFUSE_PUBLIC_KEY": "pk-lf-rotated",
                    "LANGFUSE_HOST": "http://localhost:3000",
                },
            ):
                _get_langfuse_client()

            assert mock_langfuse_class.call_count == 2


class TestLangfuseIsolatedTracerProvider:
    """Verify Langfuse is initialized with an isolated OTel ``TracerProvider``.

    Regression test for https://github.com/langflow-ai/langflow/issues/13319.

    Without an explicit ``tracer_provider``, the Langfuse v3 SDK registers
    itself as the global OTel tracer provider. Because ``langflow.main`` calls
    ``FastAPIInstrumentor.instrument_app(app)`` (which uses the global
    provider), every FastAPI HTTP request span would then be exported to
    Langfuse — flooding traces with health checks, flow list calls, and other
    unrelated routes. Passing an isolated provider keeps Langfuse spans
    private to the langfuse client.
    """

    def test_shared_client_uses_isolated_tracer_provider(self):
        """``Langfuse(...)`` must receive an explicit, non-global ``TracerProvider``."""
        from langflow.services.tracing.langfuse import _get_langfuse_client
        from opentelemetry.sdk.trace import TracerProvider

        with patch("langfuse.Langfuse") as mock_langfuse_class:
            mock_langfuse_class.return_value = MagicMock()

            _get_langfuse_client()

            mock_langfuse_class.assert_called_once()
            call_kwargs = mock_langfuse_class.call_args.kwargs
            assert "tracer_provider" in call_kwargs, (
                "Langfuse() must be called with an explicit tracer_provider so it does not"
                " register itself as the global OTel tracer provider (issue #13319)."
            )
            assert isinstance(call_kwargs["tracer_provider"], TracerProvider)

    def test_global_tracer_provider_is_not_replaced_by_langfuse_init(self):
        """Initializing the Langfuse client must not swap out the global TracerProvider.

        If Langfuse becomes the global provider, ``FastAPIInstrumentor`` will
        emit HTTP request spans into Langfuse, which is the symptom reported
        in #13319.
        """
        from langflow.services.tracing.langfuse import _get_langfuse_client
        from opentelemetry import trace as otel_trace_api

        before = otel_trace_api.get_tracer_provider()

        with patch("langfuse.Langfuse") as mock_langfuse_class:
            mock_langfuse_class.return_value = MagicMock()
            _get_langfuse_client()

        after = otel_trace_api.get_tracer_provider()
        assert after is before, (
            "Global OTel TracerProvider must not change when the Langfuse client is initialized (issue #13319)."
        )


class TestLangfuseSetupFailureVisibility:
    """Regression for https://github.com/langflow-ai/langflow/issues/13317.

    On Docker v1.9.3 (Python 3.14 + pydantic<2.13) langfuse fails to import
    with ``pydantic.v1.errors.ConfigError`` and the tracer was silently
    initializing with ``_ready = False`` because the broad except branch in
    ``_setup_langfuse`` only logged at ``debug`` level. Users saw no traces
    in Langfuse and no diagnostic message in logs. Setup failures must now
    surface at ``WARNING``/``ERROR`` level (via loguru) so the cause is
    visible. The module logger is loguru's ``lfx.log.logger.logger`` so we
    patch its methods directly rather than relying on stdlib ``caplog``.
    """

    def test_auth_check_failure_logs_warning(self):
        """A failed auth_check must log a WARNING so users see the problem."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        with (
            patch("langfuse.Langfuse") as mock_langfuse_class,
            patch("langflow.services.tracing.langfuse.logger") as mock_logger,
        ):
            mock_langfuse_class.create_trace_id = MagicMock(return_value="a" * 32)
            mock_client = MagicMock()
            mock_client.auth_check.return_value = False
            mock_langfuse_class.return_value = mock_client

            tracer = LangFuseTracer(
                trace_name="test - flow-1",
                trace_type="chain",
                project_name="proj",
                trace_id=uuid.uuid4(),
            )

            assert tracer.ready is False
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args.args[0].lower()
            assert "authentication failed" in warning_msg

    def test_auth_check_exception_logs_warning(self):
        """A connection error during auth_check must log a WARNING, not debug."""
        from langflow.services.tracing.langfuse import LangFuseTracer

        with (
            patch("langfuse.Langfuse") as mock_langfuse_class,
            patch("langflow.services.tracing.langfuse.logger") as mock_logger,
        ):
            mock_langfuse_class.create_trace_id = MagicMock(return_value="a" * 32)
            mock_client = MagicMock()
            mock_client.auth_check.side_effect = ConnectionError("upstream unreachable")
            mock_langfuse_class.return_value = mock_client

            tracer = LangFuseTracer(
                trace_name="test - flow-1",
                trace_type="chain",
                project_name="proj",
                trace_id=uuid.uuid4(),
            )

            assert tracer.ready is False
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args.args[0].lower()
            assert "cannot connect to langfuse" in warning_msg

    def test_setup_exception_logs_with_traceback(self):
        """Unexpected setup errors must call logger.exception so users see the cause.

        Simulates the production failure mode: langfuse import succeeds (mocked)
        but ``start_span`` raises something other than ``ImportError`` — exactly
        the shape ``pydantic.v1.errors.ConfigError`` takes on Python 3.14 with
        pydantic<2.13, just raised later in the path. The previous ``debug``
        log meant users got no signal at all.
        """
        from langflow.services.tracing.langfuse import LangFuseTracer

        with (
            patch("langfuse.Langfuse") as mock_langfuse_class,
            patch("langflow.services.tracing.langfuse.logger") as mock_logger,
        ):
            mock_langfuse_class.create_trace_id = MagicMock(return_value="a" * 32)
            mock_client = MagicMock()
            mock_client.auth_check.return_value = True
            mock_client.start_span.side_effect = RuntimeError("simulated pydantic v1 config error")
            mock_langfuse_class.return_value = mock_client

            tracer = LangFuseTracer(
                trace_name="test - flow-1",
                trace_type="chain",
                project_name="proj",
                trace_id=uuid.uuid4(),
            )

            assert tracer.ready is False
            mock_logger.exception.assert_called_once()
            err_msg = mock_logger.exception.call_args.args[0].lower()
            assert "error setting up langfuse tracer" in err_msg
