import threading
from collections.abc import Mapping
from enum import Enum
from typing import Any
from weakref import WeakValueDictionary

from lfx.observability import (
    APPLICATION_INSTRUMENTATION_SCOPES,
    APPLICATION_METER_NAME,
    APPLICATION_METRIC_SCOPES,
    APPLICATION_TRACER_NAME,
    DEFAULT_SERVICE_NAME,
    PROCESS_METRICS_CONFIG,
    SUPPORTED_OTLP_PROTOCOLS,
    ApplicationOnlyMetricExporter,
    ApplicationOnlySpanProcessor,
    ApplicationTelemetry,
    bootstrap_application_telemetry,
)
from opentelemetry import metrics
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.metrics._internal.instrument import Counter, Histogram, UpDownCounter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

# The provider bootstrap, the export filters and the runtime metrics now live in
# lfx.observability, so that lfx serve and lfx run get the same application observability as
# the full langflow app. They are re-exported above only so existing importers of this module
# keep working. What stays here is the langflow-specific metric registry (the custom counters
# and gauges below) and the singleton that installs them on the bootstrapped meter provider.

# a default OpenTelemetry meter name
langflow_meter_name = APPLICATION_METER_NAME

# Re-exported for backwards compatibility; the definitions live in lfx.observability.
__all__ = [
    "APPLICATION_INSTRUMENTATION_SCOPES",
    "APPLICATION_METRIC_SCOPES",
    "APPLICATION_TRACER_NAME",
    "DEFAULT_SERVICE_NAME",
    "PROCESS_METRICS_CONFIG",
    "SUPPORTED_OTLP_PROTOCOLS",
    "ApplicationOnlyMetricExporter",
    "ApplicationOnlySpanProcessor",
    "MetricType",
    "OpenTelemetry",
    "langflow_meter_name",
]


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


mandatory_label = True
optional_label = False


class ObservableGaugeWrapper:
    """Wrapper class for ObservableGauge.

    Since OpenTelemetry does not provide a way to set the value of an ObservableGauge,
    instead it uses a callback function to get the value, we need to create a wrapper class.
    """

    def __init__(self, name: str, description: str, unit: str):
        self._values: dict[tuple[tuple[str, str], ...], float] = {}
        self._meter = metrics.get_meter(langflow_meter_name)
        self._gauge = self._meter.create_observable_gauge(
            name=name, description=description, unit=unit, callbacks=[self._callback]
        )

    def _callback(self, _options: CallbackOptions):
        return [Observation(value, attributes=dict(labels)) for labels, value in self._values.items()]

        # return [Observation(self._value)]

    def set_value(self, value: float, labels: Mapping[str, str]) -> None:
        self._values[tuple(sorted(labels.items()))] = value


class Metric:
    def __init__(
        self,
        name: str,
        description: str,
        metric_type: MetricType,
        labels: dict[str, bool],
        unit: str = "",
    ):
        self.name = name
        self.description = description
        self.type = metric_type
        self.unit = unit
        self.labels = labels
        self.mandatory_labels = [label for label, required in labels.items() if required]
        self.allowed_labels = list(labels.keys())

    def validate_labels(self, labels: Mapping[str, str]) -> None:
        """Validate if the labels provided are valid."""
        if labels is None or len(labels) == 0:
            msg = "Labels must be provided for the metric"
            raise ValueError(msg)

        missing_labels = set(self.mandatory_labels) - set(labels.keys())
        if missing_labels:
            msg = f"Missing required labels: {missing_labels}"
            raise ValueError(msg)

    def __repr__(self) -> str:
        return f"Metric(name='{self.name}', description='{self.description}', type={self.type}, unit='{self.unit}')"


class ThreadSafeSingletonMetaUsingWeakref(type):
    """Thread-safe Singleton metaclass using WeakValueDictionary."""

    _instances: WeakValueDictionary[Any, Any] = WeakValueDictionary()
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]


class OpenTelemetry(metaclass=ThreadSafeSingletonMetaUsingWeakref):
    _metrics_registry: dict[str, Metric] = {}
    _metrics: dict[str, Counter | ObservableGaugeWrapper | Histogram | UpDownCounter] = {}
    _meter_provider: MeterProvider | None = None
    _tracer_provider: TracerProvider | None = None
    _logger_provider: LoggerProvider | None = None
    _initialized: bool = False  # Add initialization flag
    prometheus_enabled: bool = True

    def _add_metric(
        self, name: str, description: str, unit: str, metric_type: MetricType, labels: dict[str, bool]
    ) -> None:
        metric = Metric(name=name, description=description, metric_type=metric_type, unit=unit, labels=labels)
        self._metrics_registry[name] = metric
        if labels is None or len(labels) == 0:
            msg = "Labels must be provided for the metric upon registration"
            raise ValueError(msg)

    def _register_metric(self) -> None:
        """Define any custom metrics here.

        A thread safe singleton class to manage metrics.
        """
        self._add_metric(
            name="file_uploads",
            description="The uploaded file size in bytes",
            unit="bytes",
            metric_type=MetricType.OBSERVABLE_GAUGE,
            labels={"flow_id": mandatory_label},
        )
        self._add_metric(
            name="num_files_uploaded",
            description="The number of file uploaded",
            unit="",
            metric_type=MetricType.COUNTER,
            labels={"flow_id": mandatory_label},
        )
        self._add_metric(
            name="langflow_job_queue_cancel_events_total",
            description=(
                "Job queue cancel-channel and watchdog events. event_type is one of: "
                "published, marker_hit, dispatched_owned, dispatched_foreign, publish_errors, "
                "dispatcher_reconnects, dispatcher_internal_errors, polling_watchdog_kills, "
                "activity_touch_errors, activity_get_errors, activity_parse_errors."
            ),
            unit="",
            metric_type=MetricType.COUNTER,
            labels={"event_type": mandatory_label},
        )
        self._add_metric(
            name="langflow_job_queue_active_jobs",
            description="Active jobs tracked by the job queue on this worker.",
            unit="",
            metric_type=MetricType.UP_DOWN_COUNTER,
            labels={"backend": mandatory_label},
        )

    def __init__(self, *, prometheus_enabled: bool = True):
        # Only initialize once
        self.prometheus_enabled = prometheus_enabled
        if OpenTelemetry._initialized:
            return

        if not self._metrics_registry:
            self._register_metric()

        # The whole provider bootstrap (meter, tracer and logger providers, the OTLP
        # exporters, the export filters and the runtime metrics) lives in lfx now, so that
        # lfx serve and lfx run get identical application observability. This installs it and
        # hands back the meter provider our custom metrics register on.
        telemetry: ApplicationTelemetry = bootstrap_application_telemetry(prometheus_enabled=prometheus_enabled)
        self._meter_provider = telemetry.meter_provider
        self._owns_meter_provider = telemetry.owns_meter_provider
        self._tracer_provider = telemetry.tracer_provider
        self._logger_provider = telemetry.logger_provider

        # meter_provider is None when nothing is exported and Prometheus is off (the default):
        # the bootstrap declines to install a reader-less provider. Fall back to the global API
        # proxy so the custom metrics still register on a no-op meter rather than crashing here.
        self.meter = (self._meter_provider or metrics.get_meter_provider()).get_meter(langflow_meter_name)

        for name, metric in self._metrics_registry.items():
            if name != metric.name:
                msg = f"Key '{name}' does not match metric name '{metric.name}'"
                raise ValueError(msg)
            if name not in self._metrics:
                self._metrics[metric.name] = self._create_metric(metric)

        OpenTelemetry._initialized = True

    def _create_metric(self, metric):
        # Remove _created_instruments check
        if metric.name in self._metrics:
            return self._metrics[metric.name]

        if metric.type == MetricType.COUNTER:
            return self.meter.create_counter(
                name=metric.name,
                unit=metric.unit,
                description=metric.description,
            )
        if metric.type == MetricType.OBSERVABLE_GAUGE:
            return ObservableGaugeWrapper(
                name=metric.name,
                description=metric.description,
                unit=metric.unit,
            )
        if metric.type == MetricType.UP_DOWN_COUNTER:
            return self.meter.create_up_down_counter(
                name=metric.name,
                unit=metric.unit,
                description=metric.description,
            )
        if metric.type == MetricType.HISTOGRAM:
            return self.meter.create_histogram(
                name=metric.name,
                unit=metric.unit,
                description=metric.description,
            )
        msg = f"Unknown metric type: {metric.type}"
        raise ValueError(msg)

    def validate_labels(self, metric_name: str, labels: Mapping[str, str]) -> None:
        reg = self._metrics_registry.get(metric_name)
        if reg is None:
            msg = f"Metric '{metric_name}' is not registered"
            raise ValueError(msg)
        reg.validate_labels(labels)

    def increment_counter(self, metric_name: str, labels: Mapping[str, str], value: float = 1.0) -> None:
        self.validate_labels(metric_name, labels)
        counter = self._metrics.get(metric_name)
        if isinstance(counter, Counter):
            counter.add(value, labels)
        else:
            msg = f"Metric '{metric_name}' is not a counter"
            raise TypeError(msg)

    def up_down_counter(self, metric_name: str, value: float, labels: Mapping[str, str]) -> None:
        self.validate_labels(metric_name, labels)
        up_down_counter = self._metrics.get(metric_name)
        if isinstance(up_down_counter, UpDownCounter):
            up_down_counter.add(value, labels)
        else:
            msg = f"Metric '{metric_name}' is not an up down counter"
            raise TypeError(msg)

    def update_gauge(self, metric_name: str, value: float, labels: Mapping[str, str]) -> None:
        self.validate_labels(metric_name, labels)
        gauge = self._metrics.get(metric_name)
        if isinstance(gauge, ObservableGaugeWrapper):
            gauge.set_value(value, labels)
        else:
            msg = f"Metric '{metric_name}' is not a gauge"
            raise TypeError(msg)

    def observe_histogram(self, metric_name: str, value: float, labels: Mapping[str, str]) -> None:
        self.validate_labels(metric_name, labels)
        histogram = self._metrics.get(metric_name)
        if isinstance(histogram, Histogram):
            histogram.record(value, labels)
        else:
            msg = f"Metric '{metric_name}' is not a histogram"
            raise TypeError(msg)

    def shutdown(self):
        # Only shut down if initialized
        if not self._initialized:
            return
        if self._meter_provider and self._owns_meter_provider:
            # Not the readers directly: only MeterProvider.shutdown unregisters the atexit
            # handler, and without that the interpreter shuts the readers down a second time
            # and Prometheus raises on the double unregister. Only when we own it: a provider
            # adopted from another integration is theirs to shut down, not ours.
            self._meter_provider.shutdown()
        if self._tracer_provider:
            self._tracer_provider.shutdown()
        if self._logger_provider:
            self._logger_provider.shutdown()
        self._metrics.clear()
        OpenTelemetry._initialized = False
