"""Regression tests for tracer configuration.

These tests verify that the refactoring of OTLP tracers does not change:
- Span attributes
- Endpoint URIs
- Headers sent to backends

Run on both base and refactored branches to validate no behavioral changes.
"""

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestArizePhoenixConfiguration:
    """Test Arize/Phoenix tracer configuration is unchanged."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singleton state between tests."""
        # Reset HTTP instrumentation manager
        from langflow.services.tracing.http_instrumentation import HTTPClientInstrumentationManager

        HTTPClientInstrumentationManager._instance = None

        # Reset arize shared provider
        try:
            from langflow.services.tracing.arize_phoenix import _reset_arize_provider

            _reset_arize_provider()
        except ImportError:
            # Older versions may not have this function
            import langflow.services.tracing.arize_phoenix as arize_mod

            arize_mod._shared_provider = None
            arize_mod._shared_tracer = None
            arize_mod._instrumentor_applied = False

        yield

        HTTPClientInstrumentationManager._instance = None
        try:
            from langflow.services.tracing.arize_phoenix import _reset_arize_provider

            _reset_arize_provider()
        except ImportError:
            arize_mod._shared_provider = None
            arize_mod._shared_tracer = None
            arize_mod._instrumentor_applied = False

    def test_arize_endpoint_configuration(self):
        """Verify Arize endpoint and headers are correctly configured."""
        captured_config = {}

        def capture_grpc_exporter(endpoint, headers):
            captured_config["arize_endpoint"] = endpoint
            captured_config["arize_headers"] = headers
            return MagicMock()

        def capture_http_exporter(endpoint, headers):
            captured_config["phoenix_endpoint"] = endpoint
            captured_config["phoenix_headers"] = headers
            return MagicMock()

        mock_provider = MagicMock(spec=TracerProvider)
        mock_provider.get_tracer.return_value = MagicMock()

        with (
            patch.dict(
                os.environ,
                {
                    "ARIZE_API_KEY": "test-arize-key",  # pragma: allowlist secret
                    "ARIZE_SPACE_ID": "test-space-id",
                    "ARIZE_COLLECTOR_ENDPOINT": "https://otlp.arize.com",
                    "PHOENIX_API_KEY": "test-phoenix-key",  # pragma: allowlist secret
                    "PHOENIX_COLLECTOR_ENDPOINT": "https://app.phoenix.arize.com",
                },
            ),
            patch("phoenix.otel.TracerProvider", return_value=mock_provider),
            patch("phoenix.otel.Resource"),
            patch("phoenix.otel.SimpleSpanProcessor"),
            patch("phoenix.otel.BatchSpanProcessor"),
            patch("phoenix.otel.GRPCSpanExporter", side_effect=capture_grpc_exporter),
            patch("phoenix.otel.HTTPSpanExporter", side_effect=capture_http_exporter),
            patch("phoenix.otel.PROJECT_NAME", "test"),
            patch("openinference.instrumentation.langchain.LangChainInstrumentor"),
            patch("opentelemetry.instrumentation.requests.RequestsInstrumentor"),
            patch("opentelemetry.instrumentation.urllib3.URLLib3Instrumentor"),
        ):
            from langflow.services.tracing.arize_phoenix import ArizePhoenixTracer

            tracer = ArizePhoenixTracer(
                trace_name="Test Flow - abc123",
                trace_type="chain",
                project_name="test-project",
                trace_id=uuid.uuid4(),
            )
            _ = tracer  # Suppress unused warning

        # Verify Arize configuration
        assert captured_config["arize_endpoint"] == "https://otlp.arize.com/v1"
        assert captured_config["arize_headers"] == {
            "api_key": "test-arize-key",  # pragma: allowlist secret
            "space_id": "test-space-id",
            "authorization": "Bearer test-arize-key",
        }

        # Verify Phoenix configuration
        assert captured_config["phoenix_endpoint"] == "https://app.phoenix.arize.com/v1/traces"
        assert captured_config["phoenix_headers"] == {
            "api_key": "test-phoenix-key",  # pragma: allowlist secret
            "authorization": "Bearer test-phoenix-key",
        }


class TestLangWatchConfiguration:
    """Test LangWatch tracer configuration is unchanged."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singleton state between tests."""
        from langflow.services.tracing.http_instrumentation import HTTPClientInstrumentationManager

        HTTPClientInstrumentationManager._instance = None

        try:
            from langflow.services.tracing.langwatch import _reset_langwatch_provider

            _reset_langwatch_provider()
        except ImportError:
            import langflow.services.tracing.langwatch as lw_mod

            lw_mod._shared_provider = None

        yield

        HTTPClientInstrumentationManager._instance = None
        try:
            from langflow.services.tracing.langwatch import _reset_langwatch_provider

            _reset_langwatch_provider()
        except ImportError:
            lw_mod._shared_provider = None

    def test_langwatch_endpoint_configuration(self):
        """Verify LangWatch endpoint and headers are correctly configured."""
        captured_config = {}

        def capture_exporter(*_args, **kwargs):
            captured_config["endpoint"] = kwargs.get("endpoint")
            captured_config["headers"] = kwargs.get("headers")
            return MagicMock()

        mock_langwatch = MagicMock()
        mock_langwatch.trace.return_value.__enter__ = MagicMock()
        mock_langwatch.trace.return_value.__exit__ = MagicMock()

        with (
            patch.dict(
                os.environ,
                {
                    "LANGWATCH_API_KEY": "test-langwatch-key",  # pragma: allowlist secret
                    "LANGWATCH_ENDPOINT": "https://app.langwatch.ai",
                },
            ),
            patch.dict("sys.modules", {"langwatch": mock_langwatch}),
            patch("opentelemetry.sdk.trace.TracerProvider"),
            patch("opentelemetry.sdk.resources.Resource"),
            patch("opentelemetry.sdk.trace.export.BatchSpanProcessor"),
            patch(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                side_effect=capture_exporter,
            ),
            patch("opentelemetry.instrumentation.requests.RequestsInstrumentor"),
            patch("opentelemetry.instrumentation.urllib3.URLLib3Instrumentor"),
        ):
            from langflow.services.tracing.langwatch import LangWatchTracer

            tracer = LangWatchTracer(
                trace_name="Test Flow - abc123",
                trace_type="chain",
                project_name="test-project",
                trace_id=uuid.uuid4(),
            )
            _ = tracer

        # Verify endpoint configuration
        assert captured_config["endpoint"] == "https://app.langwatch.ai/api/otel/v1/traces"
        assert captured_config["headers"] == {"Authorization": "Bearer test-langwatch-key"}


class TestOTLPTracerConfiguration:
    """Test generic OTLP tracer configuration is unchanged."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singleton state between tests."""
        try:
            from langflow.services.tracing.otlp import _reset_shared_provider

            _reset_shared_provider()
        except (ImportError, AttributeError):
            # May not exist on all versions
            pass

        yield

        try:
            from langflow.services.tracing.otlp import _reset_shared_provider

            _reset_shared_provider()
        except (ImportError, AttributeError):
            pass

    def test_otlp_tracer_uses_standard_env_vars(self):
        """Verify OTLP tracer respects standard OpenTelemetry env vars."""
        from langflow.services.tracing.otlp import _validate_otlp_env

        # Test with no env vars - need to clear them
        with patch.dict(
            os.environ,
            {
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "",
                "OTEL_SDK_DISABLED": "",
            },
            clear=False,
        ):
            os.environ.pop("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", None)
            os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            os.environ.pop("OTEL_SDK_DISABLED", None)
            assert _validate_otlp_env() is False

        # Test with traces endpoint
        with patch.dict(
            os.environ,
            {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
            clear=False,
        ):
            assert _validate_otlp_env() is True

        # Test with generic endpoint
        with patch.dict(
            os.environ,
            {
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
            },
            clear=False,
        ):
            os.environ.pop("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", None)
            assert _validate_otlp_env() is True

    def test_otlp_root_span_attributes(self):
        """Verify OTLP tracer sets expected root span attributes."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        test_trace_id = uuid.uuid4()
        test_session_id = "test-session-456"
        test_user_id = uuid.uuid4()

        with (
            patch.dict(
                os.environ,
                {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
            ),
            patch(
                "langflow.services.tracing.otlp._get_shared_provider",
                return_value=(provider, provider.get_tracer(__name__)),
            ),
        ):
            from langflow.services.tracing.otlp import OTLPTracer

            tracer = OTLPTracer(
                trace_name="Test Flow - flow123",
                trace_type="chain",
                project_name="test-project",
                trace_id=test_trace_id,
                session_id=test_session_id,
                user_id=test_user_id,
            )

            # End the trace to flush spans
            tracer.end(inputs={"test": "input"}, outputs={"test": "output"})

        spans = exporter.get_finished_spans()
        assert len(spans) >= 1

        root_span = spans[0]
        attrs = dict(root_span.attributes)

        # Verify Langflow workflow attributes
        assert attrs.get("langflow.trace_id") == str(test_trace_id)
        assert attrs.get("langflow.trace_name") == "Test Flow - flow123"
        assert attrs.get("langflow.trace_type") == "chain"
        assert attrs.get("langflow.project_name") == "test-project"
        assert attrs.get("langflow.session_id") == test_session_id
        assert attrs.get("langflow.user_id") == str(test_user_id)
