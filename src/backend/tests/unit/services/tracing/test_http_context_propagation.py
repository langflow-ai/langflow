"""Tests for HTTP client trace context propagation in Arize Phoenix and LangWatch tracers."""

import os
import re
import uuid
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestHTTPClientInstrumentationManager:
    """Test the shared HTTP client instrumentation manager."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset the singleton manager between tests."""
        from langflow.services.tracing.http_instrumentation import HTTPClientInstrumentationManager

        HTTPClientInstrumentationManager._instance = None
        yield
        HTTPClientInstrumentationManager._instance = None

    def test_reference_counting_instrument_once(self):
        """Verify instrumentation only happens on first enable."""
        with (
            patch("opentelemetry.instrumentation.requests.RequestsInstrumentor") as mock_requests,
            patch("opentelemetry.instrumentation.urllib3.URLLib3Instrumentor") as mock_urllib3,
        ):
            mock_requests.return_value.instrument = MagicMock()
            mock_urllib3.return_value.instrument = MagicMock()

            from langflow.services.tracing.http_instrumentation import get_http_instrumentation_manager

            manager = get_http_instrumentation_manager()

            manager.enable()
            manager.enable()
            manager.enable()

            mock_requests.return_value.instrument.assert_called_once()
            mock_urllib3.return_value.instrument.assert_called_once()

    def test_reference_counting_uninstrument_at_zero(self):
        """Verify uninstrumentation only happens when ref count reaches zero."""
        with (
            patch("opentelemetry.instrumentation.requests.RequestsInstrumentor") as mock_requests,
            patch("opentelemetry.instrumentation.urllib3.URLLib3Instrumentor") as mock_urllib3,
        ):
            mock_requests.return_value.instrument = MagicMock()
            mock_requests.return_value.uninstrument = MagicMock()
            mock_urllib3.return_value.instrument = MagicMock()
            mock_urllib3.return_value.uninstrument = MagicMock()

            from langflow.services.tracing.http_instrumentation import get_http_instrumentation_manager

            manager = get_http_instrumentation_manager()

            manager.enable()
            manager.enable()
            manager.enable()

            manager.disable()
            mock_requests.return_value.uninstrument.assert_not_called()
            mock_urllib3.return_value.uninstrument.assert_not_called()

            manager.disable()
            mock_requests.return_value.uninstrument.assert_not_called()
            mock_urllib3.return_value.uninstrument.assert_not_called()

            manager.disable()
            mock_requests.return_value.uninstrument.assert_called_once()
            mock_urllib3.return_value.uninstrument.assert_called_once()

    def test_concurrent_tracers_dont_interfere(self):
        """Verify that multiple tracers can coexist without interfering."""
        with (
            patch("opentelemetry.instrumentation.requests.RequestsInstrumentor") as mock_requests,
            patch("opentelemetry.instrumentation.urllib3.URLLib3Instrumentor") as mock_urllib3,
        ):
            mock_requests.return_value.instrument = MagicMock()
            mock_requests.return_value.uninstrument = MagicMock()
            mock_urllib3.return_value.instrument = MagicMock()
            mock_urllib3.return_value.uninstrument = MagicMock()

            from langflow.services.tracing.http_instrumentation import get_http_instrumentation_manager

            manager = get_http_instrumentation_manager()

            manager.enable()
            manager.enable()

            manager.disable()

            mock_requests.return_value.uninstrument.assert_not_called()
            mock_urllib3.return_value.uninstrument.assert_not_called()

            manager.disable()

            mock_requests.return_value.uninstrument.assert_called_once()

    def test_error_logging_on_uninstrument_failure(self):
        """Verify unexpected errors during uninstrument are logged, not silently suppressed."""
        with (
            patch("opentelemetry.instrumentation.requests.RequestsInstrumentor") as mock_requests,
            patch("opentelemetry.instrumentation.urllib3.URLLib3Instrumentor") as mock_urllib3,
            patch("langflow.services.tracing.http_instrumentation.logger") as mock_logger,
        ):
            mock_requests.return_value.instrument = MagicMock()
            mock_requests.return_value.uninstrument = MagicMock(side_effect=RuntimeError("test error"))
            mock_urllib3.return_value.instrument = MagicMock()
            mock_urllib3.return_value.uninstrument = MagicMock()

            from langflow.services.tracing.http_instrumentation import get_http_instrumentation_manager

            manager = get_http_instrumentation_manager()

            manager.enable()
            manager.disable()

            mock_logger.warning.assert_called()
            call_args = str(mock_logger.warning.call_args)
            assert "Unexpected error uninstrumenting" in call_args


class TestArizePhoenixHttpInstrumentation:
    """Test HTTP client instrumentation in ArizePhoenixTracer."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset the singleton manager between tests."""
        from langflow.services.tracing.http_instrumentation import HTTPClientInstrumentationManager

        HTTPClientInstrumentationManager._instance = None
        yield
        HTTPClientInstrumentationManager._instance = None

    @pytest.fixture
    def mock_phoenix_imports(self):
        """Mock phoenix.otel imports to avoid requiring the actual package."""
        mock_provider = MagicMock(spec=TracerProvider)
        mock_provider.get_tracer.return_value = MagicMock()

        with (
            patch.dict(os.environ, {"PHOENIX_COLLECTOR_ENDPOINT": "http://localhost:6006"}),
            patch("phoenix.otel.TracerProvider", return_value=mock_provider),
            patch("phoenix.otel.Resource"),
            patch("phoenix.otel.SimpleSpanProcessor"),
            patch("phoenix.otel.BatchSpanProcessor"),
            patch("phoenix.otel.HTTPSpanExporter"),
            patch("phoenix.otel.GRPCSpanExporter"),
            patch("phoenix.otel.PROJECT_NAME", "test"),
            patch("openinference.instrumentation.langchain.LangChainInstrumentor"),
        ):
            yield mock_provider

    def test_instrument_http_clients_called_on_setup(self, mock_phoenix_imports):
        """Verify that HTTP client instrumentors are called during tracer setup."""
        _ = mock_phoenix_imports
        with (
            patch("opentelemetry.instrumentation.requests.RequestsInstrumentor") as mock_requests_inst,
            patch("opentelemetry.instrumentation.urllib3.URLLib3Instrumentor") as mock_urllib3_inst,
        ):
            mock_requests_inst.return_value.instrument = MagicMock()
            mock_urllib3_inst.return_value.instrument = MagicMock()

            from langflow.services.tracing.arize_phoenix import ArizePhoenixTracer

            tracer = ArizePhoenixTracer(
                trace_name="test - abc123",
                trace_type="chain",
                project_name="test",
                trace_id=uuid.uuid4(),
            )

            if tracer.ready:
                mock_requests_inst.return_value.instrument.assert_called_once()
                mock_urllib3_inst.return_value.instrument.assert_called_once()

    def test_uninstrument_http_clients_called_on_end(self, mock_phoenix_imports):
        """Verify that HTTP client instrumentors are uninstrumented when tracer ends."""
        _ = mock_phoenix_imports
        with (
            patch("opentelemetry.instrumentation.requests.RequestsInstrumentor") as mock_requests_inst,
            patch("opentelemetry.instrumentation.urllib3.URLLib3Instrumentor") as mock_urllib3_inst,
        ):
            mock_requests_inst.return_value.instrument = MagicMock()
            mock_requests_inst.return_value.uninstrument = MagicMock()
            mock_urllib3_inst.return_value.instrument = MagicMock()
            mock_urllib3_inst.return_value.uninstrument = MagicMock()

            from langflow.services.tracing.arize_phoenix import ArizePhoenixTracer

            tracer = ArizePhoenixTracer(
                trace_name="test - abc123",
                trace_type="chain",
                project_name="test",
                trace_id=uuid.uuid4(),
            )

            if tracer.ready:
                tracer.end(inputs={}, outputs={})
                mock_requests_inst.return_value.uninstrument.assert_called_once()
                mock_urllib3_inst.return_value.uninstrument.assert_called_once()


_langwatch_available = False
try:
    import langwatch  # noqa: F401

    _langwatch_available = True
except ImportError:
    # langwatch is gated to python_version<'3.14' upstream.
    pass


@pytest.mark.skipif(not _langwatch_available, reason="langwatch not available on Python 3.14+")
class TestLangWatchHttpInstrumentation:
    """Test HTTP client instrumentation in LangWatchTracer."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset the singleton manager between tests."""
        from langflow.services.tracing.http_instrumentation import HTTPClientInstrumentationManager

        HTTPClientInstrumentationManager._instance = None
        yield
        HTTPClientInstrumentationManager._instance = None

    @pytest.fixture
    def mock_langwatch_imports(self):
        """Mock langwatch imports to avoid requiring the actual package."""
        mock_trace = MagicMock()
        mock_trace.root_span = MagicMock()
        mock_trace.api_key = "test-key"  # pragma: allowlist secret
        mock_trace.__enter__ = MagicMock(return_value=mock_trace)
        mock_trace.__exit__ = MagicMock(return_value=None)

        mock_client = MagicMock()
        mock_client.trace.return_value = mock_trace
        mock_client._api_key = "test-key"  # pragma: allowlist secret

        with (
            patch.dict(os.environ, {"LANGWATCH_API_KEY": "test-key"}),  # pragma: allowlist secret
            patch("langwatch.setup"),
            patch("langwatch.trace", return_value=mock_trace),
            patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"),
        ):
            yield mock_client

    def test_instrument_http_clients_called_on_setup(self, mock_langwatch_imports):
        """Verify that HTTP client instrumentors are called during tracer setup."""
        _ = mock_langwatch_imports
        from langflow.services.tracing.langwatch import LangWatchTracer

        LangWatchTracer.tracer_provider = None

        with (
            patch("opentelemetry.instrumentation.requests.RequestsInstrumentor") as mock_requests_inst,
            patch("opentelemetry.instrumentation.urllib3.URLLib3Instrumentor") as mock_urllib3_inst,
        ):
            mock_requests_inst.return_value.instrument = MagicMock()
            mock_urllib3_inst.return_value.instrument = MagicMock()

            tracer = LangWatchTracer(
                trace_name="test - abc123",
                trace_type="chain",
                project_name="test",
                trace_id=uuid.uuid4(),
            )

            if tracer.ready:
                mock_requests_inst.return_value.instrument.assert_called_once()
                mock_urllib3_inst.return_value.instrument.assert_called_once()

    def test_uninstrument_http_clients_called_on_end(self, mock_langwatch_imports):
        """Verify that HTTP client instrumentors are uninstrumented when tracer ends."""
        _ = mock_langwatch_imports
        from langflow.services.tracing.langwatch import LangWatchTracer

        LangWatchTracer.tracer_provider = None

        with (
            patch("opentelemetry.instrumentation.requests.RequestsInstrumentor") as mock_requests_inst,
            patch("opentelemetry.instrumentation.urllib3.URLLib3Instrumentor") as mock_urllib3_inst,
        ):
            mock_requests_inst.return_value.instrument = MagicMock()
            mock_requests_inst.return_value.uninstrument = MagicMock()
            mock_urllib3_inst.return_value.instrument = MagicMock()
            mock_urllib3_inst.return_value.uninstrument = MagicMock()

            tracer = LangWatchTracer(
                trace_name="test - abc123",
                trace_type="chain",
                project_name="test",
                trace_id=uuid.uuid4(),
            )

            if tracer.ready:
                tracer.end(inputs={}, outputs={})
                mock_requests_inst.return_value.uninstrument.assert_called_once()
                mock_urllib3_inst.return_value.uninstrument.assert_called_once()


@pytest.mark.skip(reason="These tests mock at the wrong layer - Session.send mock bypasses OTel instrumentation")
class TestTraceContextPropagation:
    """Integration tests verifying traceparent header is actually injected."""

    def test_traceparent_header_injected_on_requests(self):
        """Verify that traceparent header is injected on outgoing HTTP requests."""
        import requests
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        RequestsInstrumentor().instrument(tracer_provider=provider)

        try:
            captured_headers = {}

            def capturing_send(_self, request, **_kwargs):
                captured_headers.update(dict(request.headers))
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {}
                mock_response.content = b""
                mock_response.text = ""
                mock_response.json.return_value = {}
                mock_response.elapsed = MagicMock()
                mock_response.elapsed.total_seconds.return_value = 0.1
                return mock_response

            with patch.object(requests.Session, "send", capturing_send):
                tracer = provider.get_tracer(__name__)
                with tracer.start_as_current_span("test-span"):
                    requests.get("http://example.com/test", timeout=10)

            assert "traceparent" in captured_headers, f"traceparent header not found in {list(captured_headers.keys())}"
            assert captured_headers["traceparent"].startswith("00-"), "traceparent should start with version 00"
        finally:
            RequestsInstrumentor().uninstrument()

    def test_traceparent_format_is_valid(self):
        """Verify that the traceparent header has valid W3C format."""
        import requests
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        provider = TracerProvider()
        RequestsInstrumentor().instrument(tracer_provider=provider)

        try:
            captured_headers = {}

            def capturing_send(_self, request, **_kwargs):
                captured_headers.update(dict(request.headers))
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {}
                mock_response.content = b""
                mock_response.text = ""
                mock_response.json.return_value = {}
                mock_response.elapsed = MagicMock()
                mock_response.elapsed.total_seconds.return_value = 0.1
                return mock_response

            with patch.object(requests.Session, "send", capturing_send):
                tracer = provider.get_tracer(__name__)
                with tracer.start_as_current_span("test-span"):
                    requests.get("http://example.com/test", timeout=10)

            traceparent = captured_headers.get("traceparent", "")
            pattern = r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$"
            assert re.match(pattern, traceparent), f"traceparent '{traceparent}' does not match W3C format"
        finally:
            RequestsInstrumentor().uninstrument()

    def test_urllib3_traceparent_header_injected(self):
        """Verify that traceparent header is injected on urllib3 requests."""
        import urllib3
        from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor

        provider = TracerProvider()
        URLLib3Instrumentor().instrument(tracer_provider=provider)

        try:
            captured_headers = {}

            def capturing_urlopen(_self, _method, _url, body=None, headers=None, **_kwargs):  # noqa: ARG001
                if headers:
                    captured_headers.update(dict(headers))
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.headers = {}
                mock_response.data = b""
                return mock_response

            with patch.object(urllib3.HTTPConnectionPool, "urlopen", capturing_urlopen):
                tracer = provider.get_tracer(__name__)
                with tracer.start_as_current_span("test-span"):
                    http = urllib3.PoolManager()
                    http.request("GET", "http://example.com/test")

            assert "traceparent" in captured_headers, f"traceparent header not found in {list(captured_headers.keys())}"
        finally:
            URLLib3Instrumentor().uninstrument()
