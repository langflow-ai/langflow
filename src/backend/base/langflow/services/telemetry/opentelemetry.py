from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource


class OpenTelemetry:
    def __init__(self, prometheus_enabled: bool = True):
        resource = Resource.create({"service.name": "langflow"})
        meter_provider = MeterProvider(resource=resource)
        self.prometheus_enabled = prometheus_enabled
        if prometheus_enabled:
            reader = PrometheusMetricReader()
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])

        metrics.set_meter_provider(meter_provider)
        self.meter = meter_provider.get_meter("langflow")

        self._register_metrics()

    def _register_metrics(self):
        pass
        """
        metrics can be registered in this function
        self.counter = self.meter.create_counter(
            name = "requests",
            unit = "bytes",
            description="The number of requests",
        )
        """
