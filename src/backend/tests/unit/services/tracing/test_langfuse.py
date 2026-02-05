"""Tests for Langfuse v3 API integration.

This module tests the LangFuseTracer class which uses the Langfuse v3 API
for distributed tracing of Langflow components.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4


class TestLangfuseTracer:
    """Tests for LangFuseTracer v3 API integration.

    Verifies trace_id format, start_span usage, and update_trace calls.
    """

    def test_trace_id_hex_format(self):
        """Test trace_id is converted to 32-char hex format.

        Langfuse v3 requires W3C Trace Context format (32 hex chars).
        UUID dashes must be removed.
        """
        trace_id = uuid4()
        trace_id_hex = str(trace_id).replace("-", "")

        assert len(trace_id_hex) == 32
        assert "-" not in trace_id_hex
        # Verify it's valid hex
        int(trace_id_hex, 16)

    @patch.dict(
        "os.environ",
        {
            "LANGFUSE_SECRET_KEY": "test-secret",  # pragma: allowlist secret
            "LANGFUSE_PUBLIC_KEY": "test-public",
            "LANGFUSE_HOST": "https://test.langfuse.com",
        },
    )
    @patch("langfuse.Langfuse")
    def test_start_span_called_instead_of_span(self, mock_langfuse_class):
        """Test v3 uses start_span() method instead of span().

        Verifies that the tracer uses the v3 API which requires
        start_span() for creating spans.
        """
        from langflow.services.tracing.langfuse import LangFuseTracer

        # Setup mock
        mock_client = MagicMock()
        mock_client.auth_check.return_value = True
        mock_span = MagicMock()
        mock_span.trace_id = "test-trace-id"
        mock_client.start_span.return_value = mock_span
        mock_langfuse_class.return_value = mock_client

        trace_id = uuid4()
        LangFuseTracer(
            trace_name="Test - flow123",
            trace_type="flow",
            project_name="test-project",
            trace_id=trace_id,
            user_id="test-user",
            session_id="test-session",
        )

        # Verify start_span was called (v3 API)
        mock_client.start_span.assert_called_once()

        # Verify update_trace was called for trace-level attributes
        mock_span.update_trace.assert_called_once_with(
            name="flow123",
            user_id="test-user",
            session_id="test-session",
        )

    @patch.dict(
        "os.environ",
        {
            "LANGFUSE_SECRET_KEY": "test-secret",  # pragma: allowlist secret
            "LANGFUSE_PUBLIC_KEY": "test-public",
            "LANGFUSE_HOST": "https://test.langfuse.com",
        },
    )
    @patch("langfuse.Langfuse")
    def test_update_trace_sets_attributes(self, mock_langfuse_class):
        """Test trace-level attributes are set via update_trace().

        Verifies that user_id, session_id, and name are set at the
        trace level using the v3 update_trace method.
        """
        from langflow.services.tracing.langfuse import LangFuseTracer

        mock_client = MagicMock()
        mock_client.auth_check.return_value = True
        mock_span = MagicMock()
        mock_span.trace_id = "test-trace-id"
        mock_client.start_span.return_value = mock_span
        mock_langfuse_class.return_value = mock_client

        trace_id = uuid4()
        LangFuseTracer(
            trace_name="Test - flow456",
            trace_type="flow",
            project_name="test-project",
            trace_id=trace_id,
            user_id="user123",
            session_id="session456",
        )

        # Check update_trace was called with correct parameters
        call_kwargs = mock_span.update_trace.call_args[1]
        assert call_kwargs["name"] == "flow456"
        assert call_kwargs["user_id"] == "user123"
        assert call_kwargs["session_id"] == "session456"

    @patch.dict(
        "os.environ",
        {
            "LANGFUSE_SECRET_KEY": "test-secret",  # pragma: allowlist secret
            "LANGFUSE_PUBLIC_KEY": "test-public",
            "LANGFUSE_HOST": "https://test.langfuse.com",
        },
    )
    @patch("langfuse.Langfuse")
    def test_add_trace_uses_start_span(self, mock_langfuse_class):
        """Test add_trace creates child spans with start_span().

        Verifies that component traces are created as child spans
        using the v3 start_span method.
        """
        from langflow.services.tracing.langfuse import LangFuseTracer

        mock_client = MagicMock()
        mock_root_span = MagicMock()
        mock_root_span.trace_id = "root-trace-id"
        mock_child_span = MagicMock()
        mock_root_span.start_span.return_value = mock_child_span
        mock_client.start_span.return_value = mock_root_span
        mock_langfuse_class.return_value = mock_client

        trace_id = uuid4()
        tracer = LangFuseTracer(
            trace_name="Test - flow789",
            trace_type="flow",
            project_name="test-project",
            trace_id=trace_id,
        )

        # Add a component trace
        tracer.add_trace(
            trace_id="component123",
            trace_name="MyComponent (component123)",
            trace_type="component",
            inputs={"value": "test"},
        )

        # Verify start_span was called on root span for child
        mock_root_span.start_span.assert_called_once()
        call_kwargs = mock_root_span.start_span.call_args[1]
        assert call_kwargs["name"] == "MyComponent"
        assert call_kwargs["input"] == {"value": "test"}

    @patch.dict(
        "os.environ",
        {
            "LANGFUSE_SECRET_KEY": "test-secret",  # pragma: allowlist secret
            "LANGFUSE_PUBLIC_KEY": "test-public",
            "LANGFUSE_HOST": "https://test.langfuse.com",
        },
    )
    @patch("langfuse.Langfuse")
    def test_end_trace_calls_end(self, mock_langfuse_class):
        """Test end_trace explicitly ends the span.

        In v3, spans must be explicitly ended with end() method.
        """
        from langflow.services.tracing.langfuse import LangFuseTracer

        mock_client = MagicMock()
        mock_root_span = MagicMock()
        mock_root_span.trace_id = "root-trace-id"
        mock_child_span = MagicMock()
        mock_root_span.start_span.return_value = mock_child_span
        mock_client.start_span.return_value = mock_root_span
        mock_langfuse_class.return_value = mock_client

        trace_id = uuid4()
        tracer = LangFuseTracer(
            trace_name="Test - flow101",
            trace_type="flow",
            project_name="test-project",
            trace_id=trace_id,
        )

        # Add and end a component trace
        tracer.add_trace(
            trace_id="component456",
            trace_name="MyComponent (component456)",
            trace_type="component",
            inputs={"value": "test"},
        )
        tracer.end_trace(
            trace_id="component456",
            trace_name="MyComponent",
            outputs={"result": "success"},
        )

        # Verify end() was called
        mock_child_span.update.assert_called_once()
        mock_child_span.end.assert_called_once()

    @patch.dict(
        "os.environ",
        {
            "LANGFUSE_SECRET_KEY": "test-secret",  # pragma: allowlist secret
            "LANGFUSE_PUBLIC_KEY": "test-public",
            "LANGFUSE_HOST": "https://test.langfuse.com",
        },
    )
    @patch("langfuse.Langfuse")
    @patch("langfuse.langchain.CallbackHandler")
    def test_get_langchain_callback_uses_trace_context(self, mock_callback_class, mock_langfuse_class):
        """Test get_langchain_callback passes trace_context with trace_id.

        Verifies that the callback handler receives the trace_id
        generated by Langfuse.create_trace_id().
        """
        from langflow.services.tracing.langfuse import LangFuseTracer

        mock_client = MagicMock()
        mock_root_span = MagicMock()
        mock_root_span.id = "root-span-id"
        mock_client.start_span.return_value = mock_root_span
        mock_client.auth_check.return_value = True
        # Mock create_trace_id to return a deterministic value
        generated_trace_id = "generated-trace-id-12345678"
        mock_langfuse_class.create_trace_id.return_value = generated_trace_id
        mock_langfuse_class.return_value = mock_client

        mock_handler = MagicMock()
        mock_callback_class.return_value = mock_handler

        trace_id = uuid4()

        tracer = LangFuseTracer(
            trace_name="Test - flow202",
            trace_type="flow",
            project_name="test-project",
            trace_id=trace_id,
        )

        tracer.get_langchain_callback()

        # Verify CallbackHandler was called with trace_context using the generated trace_id
        mock_callback_class.assert_called_once_with(trace_context={"trace_id": generated_trace_id})

    @patch.dict(
        "os.environ",
        {
            "LANGFUSE_SECRET_KEY": "test-secret",  # pragma: allowlist secret
            "LANGFUSE_PUBLIC_KEY": "test-public",
            "LANGFUSE_HOST": "https://test.langfuse.com",
        },
    )
    @patch("langfuse.Langfuse")
    @patch("langfuse.langchain.CallbackHandler")
    def test_get_langchain_callback_with_parent_span(self, mock_callback_class, mock_langfuse_class):
        """Test get_langchain_callback includes parent_span_id when spans exist.

        Verifies that when component spans are active, the callback handler
        receives both trace_id and parent_span_id for proper nesting.
        """
        from langflow.services.tracing.langfuse import LangFuseTracer

        mock_client = MagicMock()
        mock_root_span = MagicMock()
        mock_root_span.id = "root-span-id"
        mock_child_span = MagicMock()
        mock_child_span.id = "child-span-id"
        mock_root_span.start_span.return_value = mock_child_span
        mock_client.start_span.return_value = mock_root_span
        mock_client.auth_check.return_value = True
        generated_trace_id = "generated-trace-id-12345678"
        mock_langfuse_class.create_trace_id.return_value = generated_trace_id
        mock_langfuse_class.return_value = mock_client

        mock_handler = MagicMock()
        mock_callback_class.return_value = mock_handler

        trace_id = uuid4()
        tracer = LangFuseTracer(
            trace_name="Test - flow404",
            trace_type="flow",
            project_name="test-project",
            trace_id=trace_id,
        )

        # Add a component trace so spans dict is non-empty
        tracer.add_trace(
            trace_id="component789",
            trace_name="MyComponent (component789)",
            trace_type="component",
            inputs={"value": "test"},
        )

        tracer.get_langchain_callback()

        # Verify CallbackHandler was called with both trace_id and parent_span_id
        mock_callback_class.assert_called_once_with(
            trace_context={"trace_id": generated_trace_id, "parent_span_id": "child-span-id"}
        )

    def test_config_not_ready_without_env_vars(self):
        """Test tracer is not ready without environment variables.

        Verifies that the tracer gracefully handles missing Langfuse
        configuration.
        """
        from langflow.services.tracing.langfuse import LangFuseTracer

        # Clear environment variables (use patch to ensure clean state)
        with patch.dict("os.environ", {}, clear=True):
            tracer = LangFuseTracer(
                trace_name="Test - flow303",
                trace_type="flow",
                project_name="test-project",
                trace_id=uuid4(),
            )

            assert tracer.ready is False
