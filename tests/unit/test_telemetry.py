import pytest
import threading
from unittest.mock import MagicMock
from langflow.services.telemetry.opentelemetry import OpenTelemetry, Metric, MetricType
from concurrent.futures import ThreadPoolExecutor, as_completed


fixed_labels = {"service": "this", "user": "that"}


@pytest.fixture
def opentelemetry_instance():
    return OpenTelemetry()


def test_init(opentelemetry_instance):
    assert isinstance(opentelemetry_instance, OpenTelemetry)
    assert len(opentelemetry_instance._metrics) > 1
    assert len(opentelemetry_instance._metrics) == len(opentelemetry_instance._metrics_registry) == 2
    assert "file_uploads" in opentelemetry_instance._metrics


def test_gauge(opentelemetry_instance):
    opentelemetry_instance.update_gauge("file_uploads", 1024, fixed_labels)


def test_gauge_with_update_method(opentelemetry_instance):
    opentelemetry_instance.update_metric("file_uploads", 1, fixed_labels)


def test_gauge_with_counter_method(opentelemetry_instance):
    with pytest.raises(ValueError, match="Metric 'file_uploads' is not a counter"):
        opentelemetry_instance.increment_counter(metric_name="file_uploads", value=1, labels=fixed_labels)


def test_gauge_with_historgram_method(opentelemetry_instance):
    with pytest.raises(ValueError, match="Metric 'file_uploads' is not a histogram"):
        opentelemetry_instance.observe_histogram("file_uploads", 1, fixed_labels)


def test_gauge_with_up_down_counter_method(opentelemetry_instance):
    with pytest.raises(ValueError, match="Metric 'file_uploads' is not an up down counter"):
        opentelemetry_instance.up_down_counter("file_uploads", 1, labels=fixed_labels)


def test_increment_counter(opentelemetry_instance):
    opentelemetry_instance.increment_counter(metric_name="num_files_uploaded", value=5, labels=fixed_labels)


def test_counter_with_update_method(opentelemetry_instance):
    opentelemetry_instance.update_metric("num_files_uploaded", 5, fixed_labels)


def test_regstier_metric(opentelemetry_instance):
    with pytest.raises(NotImplementedError, match="register_metric is not implemented"):
        opentelemetry_instance.register_metric(
            Metric(name="non_existent", description="non_existent", type=MetricType.COUNTER)
        )


def test_opentelementry_singleton(opentelemetry_instance):
    opentelemetry_instance_2 = OpenTelemetry()
    assert opentelemetry_instance is opentelemetry_instance_2

    opentelemetry_instance_3 = OpenTelemetry(prometheus_enabled=False)
    assert opentelemetry_instance is opentelemetry_instance_3
    assert opentelemetry_instance.prometheus_enabled == opentelemetry_instance_3.prometheus_enabled


def test_update_metric_unknown_type(opentelemetry_instance):
    opentelemetry_instance._metrics_registry = {"unknown": MagicMock(type="unknown_type")}
    with pytest.raises(ValueError, match="Unknown metric type: unknown_type"):
        opentelemetry_instance.update_metric("unknown", 1, fixed_labels)


def test_missing_labels(opentelemetry_instance):
    with pytest.raises(ValueError, match="Labels must be provided for Counter"):
        opentelemetry_instance.increment_counter(metric_name="num_files_uploaded", labels=None, value=1.0)
    with pytest.raises(ValueError, match="Labels must be provided for UpDownCounter"):
        opentelemetry_instance.up_down_counter("num_files_uploaded", 1, None)
    with pytest.raises(ValueError, match="Labels must be provided for Gauge"):
        opentelemetry_instance.update_gauge(metric_name="num_files_uploaded", value=1.0, labels=dict())
    with pytest.raises(ValueError, match="Labels must be provided for Histogram"):
        opentelemetry_instance.observe_histogram("num_files_uploaded", 1, dict())


def test_update_metric_not_found(opentelemetry_instance):
    with pytest.raises(ValueError, match="Metric 'non_existent' not found"):
        opentelemetry_instance.update_metric("non_existent", 1, fixed_labels)


def test_multithreaded_singleton():
    def create_instance():
        return OpenTelemetry()

    # Create instances in multiple threads
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_instance) for _ in range(100)]
        instances = [future.result() for future in as_completed(futures)]

    # Check that all instances are the same
    first_instance = instances[0]
    for instance in instances[1:]:
        assert instance is first_instance


def test_multithreaded_singleton_race_condition():
    # This test simulates a potential race condition
    start_event = threading.Event()

    def create_instance():
        start_event.wait()  # Wait for all threads to be ready
        return OpenTelemetry()

    # Create instances in multiple threads, all starting at the same time
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(create_instance) for _ in range(100)]
        start_event.set()  # Start all threads simultaneously
        instances = [future.result() for future in as_completed(futures)]

    # Check that all instances are the same
    first_instance = instances[0]
    for instance in instances[1:]:
        assert instance is first_instance
