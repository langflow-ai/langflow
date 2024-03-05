from fastapi import FastAPI
from langflow.services.telemetry.service import TelemetryService
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from langflow.service.deps import get_telemetry_service
from langflow.services.deps import get_settings_service


def setup_tracing(
    app: FastAPI,
):
    # Configure the tracer to export traces
    telemetry_service = get_telemetry_service()
    trace.set_tracer_provider(telemetry_service.provider)
    tracer_provider = trace.get_tracer_provider()

    # Configure the OTLP exporter
    otlp_exporter = telemetry_service.provider.get_span_processor().exporter

    # Add the OTLP exporter to the tracer provider
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)

    # Instrument FastAPI app
    FastAPIInstrumentor.instrument_app(app)
