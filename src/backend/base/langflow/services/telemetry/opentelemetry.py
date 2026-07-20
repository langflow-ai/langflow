import os
import threading
from collections.abc import Mapping
from enum import Enum
from typing import Any
from weakref import WeakValueDictionary

from lfx.log.logger import logger
from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.metrics._internal.instrument import Counter, Histogram, UpDownCounter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, OTELResourceDetector, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# a default OpenTelemetry meter name
langflow_meter_name = "langflow"


DEFAULT_SERVICE_NAME = "langflow"
SUPPORTED_OTLP_PROTOCOLS = ("grpc", "http/protobuf")

# The tracer name Langflow's own application spans must use to reach the APM. Deliberately
# not "langflow": the LLM tracer integrations already take a tracer under that name, and
# their spans carry flow inputs and outputs.
APPLICATION_TRACER_NAME = "langflow.observability"

# Instrumentation scopes whose spans describe the service itself. This is an allowlist, not
# a denylist, because the LLM instrumentors ship inside the very same
# opentelemetry.instrumentation.* namespace as the application ones (openai, anthropic,
# langchain, bedrock, ... are all installed alongside fastapi and sqlalchemy). Their spans
# carry prompt and completion text, which must never reach the operator's APM, so anything
# not named here is dropped. Adding an application instrumentation means adding it here.
APPLICATION_INSTRUMENTATION_SCOPES = frozenset(
    {
        "opentelemetry.instrumentation.asgi",
        "opentelemetry.instrumentation.fastapi",
        "opentelemetry.instrumentation.httpx",
        "opentelemetry.instrumentation.requests",
        "opentelemetry.instrumentation.sqlalchemy",
        "opentelemetry.instrumentation.urllib3",
        APPLICATION_TRACER_NAME,
    }
)


class ApplicationOnlySpanProcessor(BatchSpanProcessor):
    """Exports only spans that describe the application, dropping everything else.

    Langflow installs a global tracer provider, so any library that takes a tracer from it
    ends up exporting through this processor. That includes the LLM tracing integrations,
    whose spans carry prompts and completions. Filtering on the way out keeps the boundary
    in one place and costs the vendor integrations nothing.

    Drops are logged once per scope at debug level; they are the expected case for LLM
    instrumentation, and logging every one would be noise.

    Known consequence: an exported span whose parent was dropped arrives at the APM with a
    parent that never shows up, so the trace renders with a gap. That follows from the
    requirement of zero component spans in the APM, and it cannot be repaired here because
    a child ends before its parent, so there is no way to know at the child's on_end that
    the parent will be dropped. Scrubbing attributes instead of dropping would keep the
    tree intact, but the requirement is no component spans, not merely no content.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._dropped_scopes: set[str] = set()

    def on_end(self, span) -> None:
        scope = span.instrumentation_scope.name if span.instrumentation_scope else ""
        if scope in APPLICATION_INSTRUMENTATION_SCOPES:
            super().on_end(span)
            return
        if scope not in self._dropped_scopes:
            self._dropped_scopes.add(scope)
            logger.debug(f"Not exporting spans from {scope!r}; only application telemetry is sent to the APM.")


def _resource() -> Resource:
    """Build the resource, letting OTEL_SERVICE_NAME and OTEL_RESOURCE_ATTRIBUTES win.

    Resource.create() gives explicit attributes precedence over both env vars, so passing
    service.name unconditionally would make them unsettable. Ask the SDK's own detector
    whether the environment supplied one, and only fall back to our default when it did
    not. Parsing the env ourselves gets keys that merely end in service.name
    (k8s.service.name=...) and values with spaces around the = wrong.
    """
    if OTELResourceDetector().detect().attributes.get(SERVICE_NAME):
        return Resource.create()
    return Resource.create({SERVICE_NAME: DEFAULT_SERVICE_NAME})


def _otlp_protocol() -> str:
    """Resolve the OTLP protocol, per-signal variable first, then the generic one.

    The SDK's own auto-configuration strips whitespace and rejects unknown values; match
    that leniency so a stray space does not silently route gRPC traffic at an HTTP exporter.
    """
    protocol = (
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL") or os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL") or "http/protobuf"
    ).strip()
    if protocol not in SUPPORTED_OTLP_PROTOCOLS:
        logger.warning(
            f"Unsupported OTLP protocol {protocol!r}; falling back to http/protobuf. "
            f"Supported values: {', '.join(SUPPORTED_OTLP_PROTOCOLS)}."
        )
        return "http/protobuf"
    return protocol


def _otlp_span_exporter(protocol: str):
    """Build the OTLP span exporter; it reads endpoint, headers and timeout from the environment."""
    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    return OTLPSpanExporter()


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

        if self._meter_provider is None:
            # Get existing meter provider if any
            existing_provider = metrics.get_meter_provider()

            # Reuse a concrete SDK provider installed by another integration. The
            # default API proxy also returns meters, but it has no readers and must
            # be replaced so Prometheus can collect Langflow metrics.
            if isinstance(existing_provider, MeterProvider):
                self._meter_provider = existing_provider
            else:
                resource = _resource()
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

        OpenTelemetry._initialized = True

    def _configure_tracer_provider_from_environment(self) -> None:
        """Install an OTLP tracer provider when the standard OTel env vars opt in.

        Nothing sets a tracer provider otherwise, so spans go nowhere. If application code
        or opentelemetry-instrument already installed one, leave it alone.
        """
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint:
            return

        # The operator's documented way to turn traces off while leaving a shared endpoint set.
        if os.getenv("OTEL_TRACES_EXPORTER", "otlp").strip().lower() == "none":
            return

        if trace.get_tracer_provider().__class__.__name__ != "ProxyTracerProvider":
            return

        protocol = _otlp_protocol()
        try:
            tracer_provider = TracerProvider(resource=_resource())
            tracer_provider.add_span_processor(ApplicationOnlySpanProcessor(_otlp_span_exporter(protocol)))
        except Exception:  # noqa: BLE001
            logger.warning("Could not configure the OTLP tracer provider; traces will not be exported.")
            return

        trace.set_tracer_provider(tracer_provider)
        self._tracer_provider = tracer_provider
        # Without this, a protocol/port mismatch is indistinguishable from never having booted.
        logger.info(f"OTLP trace export enabled (protocol={protocol}, endpoint={endpoint}).")

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
