from enum import Enum
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import Observation, CallbackOptions
from opentelemetry.metrics._internal.instrument import Counter, Histogram, UpDownCounter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from typing import Any, Dict, Mapping, Tuple, Union
from weakref import WeakValueDictionary

import threading

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


mandatory_label = True
optional_label = False


class ObservableGaugeWrapper:
    """
    Wrapper class for ObservableGauge
    Since OpenTelemetry does not provide a way to set the value of an ObservableGauge,
    instead it uses a callback function to get the value, we need to create a wrapper class.
    """

    def __init__(self, name: str, description: str, unit: str):
        self._values: Dict[Tuple[Tuple[str, str], ...], float] = {}
        self._meter = metrics.get_meter(langflow_meter_name)
        self._gauge = self._meter.create_observable_gauge(
            name=name, description=description, unit=unit, callbacks=[self._callback]
        )

    def _callback(self, options: CallbackOptions):
        return [Observation(value, attributes=dict(labels)) for labels, value in self._values.items()]

        # return [Observation(self._value)]

    def set_value(self, value: float, labels: Mapping[str, str]):
        self._values[tuple(sorted(labels.items()))] = value


class Metric:
    def __init__(
        self,
        name: str,
        description: str,
        type: MetricType,
        labels: Dict[str, bool],
        unit: str = "",
    ):
        self.name = name
        self.description = description
        self.type = type
        self.unit = unit
        self.labels = labels
        self.mandatory_labels = [label for label, required in labels.items() if required]
        self.allowed_labels = [label for label in labels.keys()]

    def validate_labels(self, labels: Mapping[str, str]):
        """
        Validate if the labels provided are valid
        """
        if labels is None or len(labels) == 0:
            raise ValueError("Labels must be provided for the metric")

        missing_labels = set(self.mandatory_labels) - set(labels.keys())
        if missing_labels:
            raise ValueError(f"Missing required labels: {missing_labels}")

    def __repr__(self):
        return f"Metric(name='{self.name}', description='{self.description}', type={self.type}, unit='{self.unit}')"


class ThreadSafeSingletonMetaUsingWeakref(type):
    """
    Thread-safe Singleton metaclass using WeakValueDictionary
    """

    _instances: WeakValueDictionary[Any, Any] = WeakValueDictionary()
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super(ThreadSafeSingletonMetaUsingWeakref, cls).__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]


class OpenTelemetry(metaclass=ThreadSafeSingletonMetaUsingWeakref):
    _metrics_registry: Dict[str, Metric] = dict()

    def _add_metric(self, name: str, description: str, unit: str, metric_type: MetricType, labels: Dict[str, bool]):
        metric = Metric(name=name, description=description, type=metric_type, unit=unit, labels=labels)
        self._metrics_registry[name] = metric
        if labels is None or len(labels) == 0:
            raise ValueError("Labels must be provided for the metric upon registration")

    def _register_metric(self):
        """
        Define any custom metrics here
        A thread safe singleton class to manage metrics
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

    _metrics: Dict[str, Union[Counter, ObservableGaugeWrapper, Histogram, UpDownCounter]] = {}

    def __init__(self, prometheus_enabled: bool = True):
        self._register_metric()

        resource = Resource.create({"service.name": "langflow"})
        meter_provider = MeterProvider(resource=resource)

        # configure prometheus exporter
        self.prometheus_enabled = prometheus_enabled
        if prometheus_enabled:
            reader = PrometheusMetricReader()
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])

        metrics.set_meter_provider(meter_provider)
        self.meter = meter_provider.get_meter(langflow_meter_name)

        for name, metric in self._metrics_registry.items():
            # enforce the key in the mapping and metric's name are the same
            # this error can get caught at unit test
            if name != metric.name:
                raise ValueError(f"Key '{name}' does not match metric name '{metric.name}'")
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

    def validate_labels(self, metric_name: str, labels: Mapping[str, str]):
        reg = self._metrics_registry.get(metric_name)
        if reg is None:
            raise ValueError(f"Metric '{metric_name}' is not registered")
        reg.validate_labels(labels)

    def increment_counter(self, metric_name: str, labels: Mapping[str, str], value: float = 1.0):
        self.validate_labels(metric_name, labels)
        counter = self._metrics.get(metric_name)
        if isinstance(counter, Counter):
            counter.add(value, labels)
        else:
            raise ValueError(f"Metric '{metric_name}' is not a counter")

    def up_down_counter(self, metric_name: str, value: float, labels: Mapping[str, str]):
        self.validate_labels(metric_name, labels)
        up_down_counter = self._metrics.get(metric_name)
        if isinstance(up_down_counter, UpDownCounter):
            up_down_counter.add(value, labels)
        else:
            raise ValueError(f"Metric '{metric_name}' is not an up down counter")

    def update_gauge(self, metric_name: str, value: float, labels: Mapping[str, str]):
        self.validate_labels(metric_name, labels)
        gauge = self._metrics.get(metric_name)
        if isinstance(gauge, ObservableGaugeWrapper):
            gauge.set_value(value, labels)
        else:
            raise ValueError(f"Metric '{metric_name}' is not a gauge")

    def observe_histogram(self, metric_name: str, value: float, labels: Mapping[str, str]):
        self.validate_labels(metric_name, labels)
        histogram = self._metrics.get(metric_name)
        if isinstance(histogram, Histogram):
            histogram.record(value, labels)
        else:
            raise ValueError(f"Metric '{metric_name}' is not a histogram")
