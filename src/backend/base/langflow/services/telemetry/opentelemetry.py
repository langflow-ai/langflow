from enum import Enum
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import Observation, CallbackOptions
from opentelemetry.metrics._internal.instrument import Counter, Histogram, ObservableGauge, UpDownCounter
from opentelemetry.sdk.metrics import (
    MeterProvider,
)
from opentelemetry.sdk.resources import Resource
from typing import Dict, Union

# a default OpenTelelmetry meter name
langflow_meter_name = "langflow"

"""
If the measurement values are non-additive, use an Asynchronous Gauge.
    ObservableGauge reports the current absolute value when observed.
If the measurement values are additive: If the value is monotonically increasing - use an Asynchronous Counter.
If the value is NOT monotonically increasing - use an Asynchronous UpDownCounter.
    UpDownCounter reports changes/deltas to the last observed value.
If the measurement values are additive and you want to observe the distribution of the values - use a Histogram.
"""


class MetricType(Enum):
    COUNTER = "counter"
    OBSERVABLE_GAUGE = "observable_gauge"
    HISTOGRAM = "histogram"
    UP_DOWN_COUNTER = "up_down_counter"


class ObservableGaugeWrapper:
    """
    Wrapper class for ObservableGauge
    Since OpenTelemetry does not provide a way to set the value of an ObservableGauge,
    instead it uses a callback function to get the value, we need to create a wrapper class.
    """

    def __init__(self, name: str, description: str, unit: str):
        self._value = 0.0
        self._meter = metrics.get_meter(langflow_meter_name)
        self._gauge = self._meter.create_observable_gauge(
            name=name, description=description, unit=unit, callbacks=[self._callback]
        )

    def _callback(self, options: CallbackOptions):
        return [Observation(self._value)]

    def set_value(self, value: float):
        self._value = value


class Metric:
    def __init__(
        self,
        name: str,
        description: str,
        type: MetricType,
        unit: str = "",
    ):
        self.name = name
        self.description = description
        self.type = type
        self.unit = unit

    def __repr__(self):
        return f"Metric(name='{self.name}', description='{self.description}', type={self.type}, unit='{self.unit}')"


class OpenTelemetry:
    """
    Define any custom metrics here
    """

    _metrics_registry: Dict[str, Metric] = dict[str, Metric](
        {
            "requests": Metric(
                name="file_uploads",
                description="The uploaded file size in bytes",
                type=MetricType.OBSERVABLE_GAUGE,
                unit="bytes",
            )
        }
    )

    _metrics: Dict[str, Union[Counter, ObservableGaugeWrapper, Histogram, UpDownCounter]] = {}

    def __init__(self, prometheus_enabled: bool = True):
        resource = Resource.create({"service.name": "langflow"})
        meter_provider = MeterProvider(resource=resource)

        # configure prometheus exporter
        self.prometheus_enabled = prometheus_enabled
        if prometheus_enabled:
            reader = PrometheusMetricReader()
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])

        metrics.set_meter_provider(meter_provider)
        self.meter = meter_provider.get_meter(langflow_meter_name)

        for metric in self._metrics_registry.values():
            if metric.type == MetricType.COUNTER:
                counter = self.meter.create_counter(
                    name=metric.name,
                    unit=metric.unit,
                    description=metric.description,
                )
                self._metrics[metric.name] = counter
            elif metric.type == MetricType.OBSERVABLE_GAUGE:
                gauge = ObservableGaugeWrapper(
                    name=metric.name,
                    description=metric.description,
                    unit=metric.unit,
                )
                self._metrics[metric.name] = gauge
            elif metric.type == MetricType.UP_DOWN_COUNTER:
                up_down_counter = self.meter.create_up_down_counter(
                    name=metric.name,
                    unit=metric.unit,
                    description=metric.description,
                )
                self._metrics[metric.name] = up_down_counter
            elif metric.type == MetricType.HISTOGRAM:
                histogram = self.meter.create_histogram(
                    name=metric.name,
                    unit=metric.unit,
                    description=metric.description,
                )
                self._metrics[metric.name] = histogram
            else:
                raise ValueError(f"Unknown metric type: {metric.type}")

    def increment_counter(self, metric_name: str, value: int = 1):
        counter = self._metrics.get(metric_name)
        if isinstance(counter, Counter):
            counter.add(value)
        else:
            raise ValueError(f"Metric '{metric_name}' is not a counter")

    def up_down_counter(self, metric_name: str, value: int = 1):
        up_down_counter = self._metrics.get(metric_name)
        if isinstance(up_down_counter, UpDownCounter):
            up_down_counter.add(value)
        else:
            raise ValueError(f"Metric '{metric_name}' is not an up down counter")

    def update_gauge(self, metric_name: str, value: float):
        gauge = self._metrics_registry.get(metric_name)
        if isinstance(gauge, ObservableGauge):
            gauge.set_value(value)
        else:
            raise ValueError(f"Metric '{metric_name}' is not a gauge")

    def observe_histogram(self, metric_name: str, value: float):
        histogram = self._metrics.get(metric_name)
        if isinstance(histogram, Histogram):
            histogram.record(value)
        else:
            raise ValueError(f"Metric '{metric_name}' is not a histogram")

    def update_metric(self, metric_name: str, value: int):
        metric = self._metrics_registry.get(metric_name)
        if metric is None:
            raise ValueError(f"Metric '{metric_name}' not found")
        if metric.type == MetricType.COUNTER:
            self.increment_counter(metric_name, value)
        elif metric.type == MetricType.OBSERVABLE_GAUGE:
            self.update_gauge(metric_name, value)
        elif metric.type == MetricType.UP_DOWN_COUNTER:
            self.up_down_counter(metric_name, value)
        elif metric.type == MetricType.HISTOGRAM:
            self.observe_histogram(metric_name, value)
        else:
            raise ValueError(f"Unknown metric type: {metric.type}")
