import os
import platform
from typing import TYPE_CHECKING, Any, Dict

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

from langflow.services.base import Service

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


def setup_tracing(app: FastAPI, telemetry_service: TelemetryService):
    # Configure the tracer to export traces
    trace.set_tracer_provider(telemetry_service.provider)
    tracer_provider = trace.get_tracer_provider()

    # Configure the OTLP exporter
    otlp_exporter = telemetry_service.provider.get_span_processor().exporter

    # Add the OTLP exporter to the tracer provider
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)

    # Instrument FastAPI app
    FastAPIInstrumentor.instrument_app(app)


class TelemetryService(Service):
    name = "telemetry_service"

    def __init__(self, settings_service: "SettingsService"):
        super().__init__(service_name="telemetry_service")
        self.settings_service = settings_service
        settings = self.settings_service.settings
        self.init(
            service_name=settings.SERVICE_NAME,
            telemetry_endpoint=settings.TELEMETRY_ENDPOINT,
        )
        self.set_ready()

    def init(
        self,
        service_name: str,
        telemetry_endpoint: str = "http://telemetry.example.com:4318",
    ):
        self.ready = False
        try:
            self.resource = Resource(attributes={SERVICE_NAME: service_name})
            self.provider = TracerProvider(resource=self.resource)
            processor = BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f"{telemetry_endpoint}/v1/traces", timeout=15)
            )
            self.provider.add_span_processor(processor)
            trace.set_tracer_provider(self.provider)
            self.ready = True
        except Exception as e:
            print(f"Failed to initialize telemetry: {e}")

    def teardown(self):
        raise NotImplementedError

    def record_event(self, event_name: str, attributes: Dict[str, Any]):
        """Records a generic event with specified attributes."""
        if self.ready:
            tracer = trace.get_tracer("generic.telemetry")
            with tracer.start_as_current_span(event_name) as span:
                for key, value in attributes.items():
                    self._add_attribute(span, key, value)
                span.set_status(Status(StatusCode.OK))

    def _add_attribute(self, span, key: str, value: Any):
        """Safely adds an attribute to a span."""
        try:
            span.set_attribute(key, value)
        except Exception as e:
            print(f"Failed to add attribute {key}: {e}")

    @staticmethod
    def gather_system_info() -> Dict[str, Any]:
        """Collects generic system information."""
        return {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "platform_release": platform.release(),
            "platform_system": platform.system(),
            "platform_version": platform.version(),
            "cpus": os.cpu_count(),
        }
