import os
import platform
from typing import Any, Dict

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode


class GenericTelemetry:
    """A class to handle anonymous telemetry for a generic package or application.

    The data being collected is for development purposes, and all data is anonymous.

    Users can customize the data points collected according to their needs.
    """

    def __init__(
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


# Example usage
telemetry = GenericTelemetry(service_name="MyAPI")

# Record a generic event
telemetry.record_event(
    "API Request",
    {
        "endpoint": "/api/data",
        "method": "GET",
        "status_code": 200,
        **telemetry.gather_system_info(),
    },
)
