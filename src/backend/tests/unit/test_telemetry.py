import re
import threading
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import pytest
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from langflow.services.telemetry.service import TelemetryService

fixed_labels = {"flow_id": "this_flow_id", "service": "this", "user": "that"}


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


def test_gauge_with_counter_method(opentelemetry_instance):
    with pytest.raises(TypeError, match="Metric 'file_uploads' is not a counter"):
        opentelemetry_instance.increment_counter(metric_name="file_uploads", value=1, labels=fixed_labels)


def test_gauge_with_historgram_method(opentelemetry_instance):
    with pytest.raises(TypeError, match="Metric 'file_uploads' is not a histogram"):
        opentelemetry_instance.observe_histogram("file_uploads", 1, fixed_labels)


def test_gauge_with_up_down_counter_method(opentelemetry_instance):
    with pytest.raises(TypeError, match="Metric 'file_uploads' is not an up down counter"):
        opentelemetry_instance.up_down_counter("file_uploads", 1, labels=fixed_labels)


def test_increment_counter(opentelemetry_instance):
    opentelemetry_instance.increment_counter(metric_name="num_files_uploaded", value=5, labels=fixed_labels)


def test_increment_counter_empty_label(opentelemetry_instance):
    with pytest.raises(ValueError, match="Labels must be provided for the metric"):
        opentelemetry_instance.increment_counter(metric_name="num_files_uploaded", value=5, labels={})


def test_increment_counter_missing_mandatory_label(opentelemetry_instance):
    with pytest.raises(ValueError, match=re.escape("Missing required labels: {'flow_id'}")):
        opentelemetry_instance.increment_counter(metric_name="num_files_uploaded", value=5, labels={"service": "one"})


def test_increment_counter_unregisted_metric(opentelemetry_instance):
    with pytest.raises(ValueError, match="Metric 'num_files_uploaded_1' is not registered"):
        opentelemetry_instance.increment_counter(metric_name="num_files_uploaded_1", value=5, labels=fixed_labels)


def test_opentelementry_singleton(opentelemetry_instance):
    opentelemetry_instance_2 = OpenTelemetry()
    assert opentelemetry_instance is opentelemetry_instance_2

    opentelemetry_instance_3 = OpenTelemetry(prometheus_enabled=False)
    assert opentelemetry_instance is opentelemetry_instance_3
    assert opentelemetry_instance.prometheus_enabled == opentelemetry_instance_3.prometheus_enabled


def test_missing_labels(opentelemetry_instance):
    with pytest.raises(ValueError, match="Labels must be provided for the metric"):
        opentelemetry_instance.increment_counter(metric_name="num_files_uploaded", labels=None, value=1.0)
    with pytest.raises(ValueError, match="Labels must be provided for the metric"):
        opentelemetry_instance.up_down_counter("num_files_uploaded", 1, None)
    with pytest.raises(ValueError, match="Labels must be provided for the metric"):
        opentelemetry_instance.update_gauge(metric_name="num_files_uploaded", value=1.0, labels={})
    with pytest.raises(ValueError, match="Labels must be provided for the metric"):
        opentelemetry_instance.observe_histogram("num_files_uploaded", 1, {})


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


class MockSettings:
    """Mock settings used to simulate Langflow's Settings object for telemetry testing."""

    def __init__(self, prometheus_port: int = 9001, prometheus_enabled: bool = True):
        self.prometheus_port = prometheus_port
        self.prometheus_enabled = prometheus_enabled
        self.telemetry_base_url = "http://localhost"
        self.do_not_track = True  # Disable actual telemetry reporting for test


class MockSettingsService:
    """Mock settings service to provide access to mocked telemetry configuration."""

    def __init__(self):
        self.settings = MockSettings()


@pytest.fixture(name="fixture_telemetry_service")
def telemetry_service() -> Generator[TelemetryService, None, None]:
    """Fixture that returns a fresh instance of TelemetryService with mocked settings."""
    return TelemetryService(settings_service=MockSettingsService())


def test_start_metrics_server_starts_thread_and_serves_metrics(fixture_telemetry_service: TelemetryService) -> None:
    """Test that the metrics server starts in a background thread and exposes the /metrics endpoint."""
    fixture_telemetry_service.start_metrics_server()
    time.sleep(2)  # Allow background thread to start and server to bind to port

    response = httpx.get("http://localhost:9001/metrics")

    # Assert that the server responds successfully and exposes expected Prometheus metrics
    assert response.status_code == 200
    # Check for presence of any known Prometheus metrics
    assert "python_gc_objects_collected_total" in response.text
    assert "python_info" in response.text


def test_start_metrics_server_is_idempotent(fixture_telemetry_service: TelemetryService) -> None:
    """Test that calling start_metrics_server() multiple times doesn't raise errors."""
    fixture_telemetry_service.start_metrics_server()
    time.sleep(1)

    # Try calling it again to verify no exceptions are raised and thread safety is maintained
    fixture_telemetry_service.start_metrics_server()
    time.sleep(2)

    response = httpx.get("http://localhost:9001/metrics")
    assert response.status_code == 200
    # Check for presence of any known Prometheus metrics
    assert "python_gc_objects_collected_total" in response.text
    assert "python_info" in response.text


def test_metrics_server_thread_named_correctly(monkeypatch):
    """Ensure that the Prometheus metrics server thread is named properly."""
    started_threads = []

    # Save the original Thread constructor before patching
    real_thread_class = threading.Thread

    def mock_thread(*args, **kwargs):
        started_threads.append(kwargs["name"])
        return real_thread_class(*args, **kwargs)

    # Patch the threading.Thread reference with our mock
    monkeypatch.setattr("threading.Thread", mock_thread)

    service = TelemetryService(settings_service=MockSettingsService())
    service.start_metrics_server()

    # Assert the thread name used
    assert "PrometheusMetricsServer" in started_threads


def test_metrics_server_respects_env(monkeypatch):
    """Ensure LANGFLOW_METRICS_HOST and LANGFLOW_METRICS_LOG_LEVEL are respected."""
    env_host = "127.0.0.1"
    env_log_level = "info"

    monkeypatch.setenv("LANGFLOW_METRICS_HOST", env_host)
    monkeypatch.setenv("LANGFLOW_METRICS_LOG_LEVEL", env_log_level)

    captured_args = {}

    def mock_run(app, **kwargs):
        captured_args.update(kwargs)

    monkeypatch.setattr("uvicorn.run", mock_run)

    service = TelemetryService(settings_service=MockSettingsService())
    service.start_metrics_server()

    assert captured_args["host"] == env_host
    assert captured_args["log_level"] == env_log_level


def test_metrics_server_thread_is_daemon(monkeypatch):
    """Check that the metrics server thread is daemonized."""
    created_threads = []

    class MockThread(threading.Thread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created_threads.append(self)

    monkeypatch.setattr(threading, "Thread", MockThread)

    service = TelemetryService(settings_service=MockSettingsService())
    service.start_metrics_server()

    # Look for the thread with the name we expect
    metrics_thread = next(
        (t for t in created_threads if t.name == "PrometheusMetricsServer"),
        None,
    )

    assert metrics_thread is not None, "Expected metrics server thread to be created"
    assert metrics_thread.daemon is True, "Metrics thread should be daemonized"
