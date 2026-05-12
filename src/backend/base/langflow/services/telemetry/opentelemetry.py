import os
import threading
from collections.abc import Mapping
from enum import Enum
from typing import Any
from weakref import WeakValueDictionary

import orjson
from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.metrics._internal.instrument import Counter, Histogram, UpDownCounter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode

# a default OpenTelemetry meter name
langflow_meter_name = "langflow"
langflow_tracer_name = "langflow.telemetry"
telemetry_event_prefix = "langflow.telemetry"

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

    def __init__(self, *, prometheus_enabled: bool = True):
        # Only initialize once
        self.prometheus_enabled = prometheus_enabled
        if OpenTelemetry._initialized:
            if self._meter_provider is not None:
                self.meter = self._meter_provider.get_meter(langflow_meter_name)
            self.tracer = trace.get_tracer(langflow_tracer_name)
            return

        if not self._metrics_registry:
            self._register_metric()

        if self._meter_provider is None:
            # Get existing meter provider if any
            existing_provider = metrics.get_meter_provider()

            # Check if FastAPI instrumentation is already set up
            if hasattr(existing_provider, "get_meter") and existing_provider.get_meter("http.server"):
                self._meter_provider = existing_provider
            else:
                resource = Resource.create({"service.name": "langflow"})
                metric_readers = []
                if self.prometheus_enabled:
                    metric_readers.append(PrometheusMetricReader())

                self._meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
                metrics.set_meter_provider(self._meter_provider)

        self.meter = self._meter_provider.get_meter(langflow_meter_name)

        for name, metric in self._metrics_registry.items():
            if name != metric.name:
                msg = f"Key '{name}' does not match metric name '{metric.name}'"
                raise ValueError(msg)
            if name not in self._metrics:
                self._metrics[metric.name] = self._create_metric(metric)

        self._configure_tracer_provider_from_environment()
        self.tracer = trace.get_tracer(langflow_tracer_name)

        OpenTelemetry._initialized = True

    def _configure_tracer_provider_from_environment(self) -> None:
        """Install a default OTLP tracer provider when standard OTel env vars opt in.

        If another provider has already been installed by application code or
        opentelemetry-instrument, leave it untouched.
        """
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint:
            return

        existing_provider = trace.get_tracer_provider()
        if existing_provider.__class__.__name__ != "ProxyTracerProvider":
            return

        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "langflow")})
            tracer_provider = TracerProvider(resource=resource)
            tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            trace.set_tracer_provider(tracer_provider)
            self._tracer_provider = tracer_provider
        except Exception:  # noqa: BLE001
            return

    def _normalize_attribute_value(self, value: Any) -> bool | str | bytes | int | float | list[Any]:
        if isinstance(value, bool | str | bytes | int | float):
            return value
        if isinstance(value, tuple | list):
            return [self._normalize_attribute_value(item) for item in value]
        return orjson.dumps(value, default=str).decode("utf-8")

    def _normalize_attributes(
        self, attributes: Mapping[str, Any]
    ) -> dict[str, bool | str | bytes | int | float | list[Any]]:
        return {key: self._normalize_attribute_value(value) for key, value in attributes.items() if value is not None}

    def emit_event(self, event_name: str, attributes: Mapping[str, Any], *, error: bool = False) -> None:
        normalized_attributes = self._normalize_attributes(attributes)
        normalized_attributes[f"{telemetry_event_prefix}.event"] = event_name

        with self.tracer.start_as_current_span(
            f"{telemetry_event_prefix}.{event_name}",
            kind=SpanKind.INTERNAL,
            attributes=normalized_attributes,
        ) as span:
            span.add_event(event_name, attributes=normalized_attributes)
            if error:
                span.set_status(Status(StatusCode.ERROR))

    def force_flush(self, timeout_millis: int = 5000) -> bool:
        provider = trace.get_tracer_provider()
        force_flush = getattr(provider, "force_flush", None)
        if force_flush is None:
            return True
        try:
            return bool(force_flush(timeout_millis=timeout_millis))
        except TypeError:
            return bool(force_flush())

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
        if self._meter_provider:
            readers = getattr(self._meter_provider, "_metric_readers", [])
            for reader in readers:
                if hasattr(reader, "shutdown"):
                    reader.shutdown()
        self._metrics.clear()
        OpenTelemetry._initialized = False
