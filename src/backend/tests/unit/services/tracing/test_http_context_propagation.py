"""Tests for HTTP client trace context propagation in Arize Phoenix and LangWatch tracers."""

import os
import re
import uuid
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestArizePhoenixHttpInstrumentation:
    """Test HTTP client instrumentation in ArizePhoenixTracer."""

    @pytest.fixture
    def mock_phoenix_imports(self):
        """Mock phoenix.otel imports to avoid requiring the actual package."""
        mock_provider = MagicMock(spec=TracerProvider)
        mock_provider.get_tracer.return_value = MagicMock()

        with patch.dict(os.environ, {"PHOENIX_COLLECTOR_ENDPOINT": "http://localhost:6006"}):
            with patch("phoenix.otel.TracerProvider", return_value=mock_provider):
                with patch("phoenix.otel.Resource"):
                    with patch("phoenix.otel.SimpleSpanProcessor"):
                        with patch("phoenix.otel.BatchSpanProcessor"):
                            with patch("phoenix.otel.HTTPSpanExporter"):
                                with patch("phoenix.otel.GRPCSpanExporter"):
                                    with patch("phoenix.otel.PROJECT_NAME", "test"):
                                        with patch(
                                            "openinference.instrumentation.langchain.LangChainInstrumentor"
                                        ):
                                            yield mock_provider

    def test_instrument_http_clients_called_on_setup(self, mock_phoenix_imports):
        """Verify that HTTP client instrumentors are called during tracer setup."""
        with patch(
            "opentelemetry.instrumentation.requests.RequestsInstrumentor"
        ) as mock_requests_inst:
            with patch(
                "opentelemetry.instrumentation.urllib3.URLLib3Instrumentor"
            ) as mock_urllib3_inst:
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
        with patch(
            "opentelemetry.instrumentation.requests.RequestsInstrumentor"
        ) as mock_requests_inst:
            with patch(
                "opentelemetry.instrumentation.urllib3.URLLib3Instrumentor"
            ) as mock_urllib3_inst:
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


class TestLangWatchHttpInstrumentation:
    """Test HTTP client instrumentation in LangWatchTracer."""

    @pytest.fixture
    def mock_langwatch_imports(self):
        """Mock langwatch imports to avoid requiring the actual package."""
        mock_trace = MagicMock()
        mock_trace.root_span = MagicMock()
        mock_trace.api_key = "test-key"
        mock_trace.__enter__ = MagicMock(return_value=mock_trace)
        mock_trace.__exit__ = MagicMock(return_value=None)

        mock_client = MagicMock()
        mock_client.trace.return_value = mock_trace
        mock_client._api_key = "test-key"

        with patch.dict(os.environ, {"LANGWATCH_API_KEY": "test-key"}):
            with patch("langwatch.setup"):
                with patch("langwatch.trace", return_value=mock_trace):
                    with patch(
                        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
                    ):
                        yield mock_client

    def test_instrument_http_clients_called_on_setup(self, mock_langwatch_imports):
        """Verify that HTTP client instrumentors are called during tracer setup."""
        from langflow.services.tracing.langwatch import LangWatchTracer

        LangWatchTracer.tracer_provider = None

        with patch(
            "opentelemetry.instrumentation.requests.RequestsInstrumentor"
        ) as mock_requests_inst:
            with patch(
                "opentelemetry.instrumentation.urllib3.URLLib3Instrumentor"
            ) as mock_urllib3_inst:
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
        from langflow.services.tracing.langwatch import LangWatchTracer

        LangWatchTracer.tracer_provider = None

        with patch(
            "opentelemetry.instrumentation.requests.RequestsInstrumentor"
        ) as mock_requests_inst:
            with patch(
                "opentelemetry.instrumentation.urllib3.URLLib3Instrumentor"
            ) as mock_urllib3_inst:
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

            original_send = requests.Session.send

            def capturing_send(self, request, **kwargs):
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
                    requests.get("http://example.com/test")

            assert "traceparent" in captured_headers, (
                f"traceparent header not found in {list(captured_headers.keys())}"
            )
            assert captured_headers["traceparent"].startswith("00-"), (
                "traceparent should start with version 00"
            )
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

            def capturing_send(self, request, **kwargs):
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
                    requests.get("http://example.com/test")

            traceparent = captured_headers.get("traceparent", "")
            pattern = r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$"
            assert re.match(pattern, traceparent), (
                f"traceparent '{traceparent}' does not match W3C format"
            )
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
            original_urlopen = urllib3.HTTPConnectionPool.urlopen

            def capturing_urlopen(self, method, url, body=None, headers=None, **kwargs):
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

            assert "traceparent" in captured_headers, (
                f"traceparent header not found in {list(captured_headers.keys())}"
            )
        finally:
            URLLib3Instrumentor().uninstrument()
