import re
import socket
import threading
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pytest
from langflow.services.telemetry.opentelemetry import MetricType, OpenTelemetry
from langflow.services.telemetry.service import TelemetryService

fixed_labels = {"flow_id": "this_flow_id", "service": "this", "user": "that"}
fastapi_version_labels = {"version": "0.111.5"}
langflow_version_labels = {"version": "1.2.0"}


# Helper function to find a free port
def find_free_port() -> int:
    """Find and return a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class MockSettings:
    """Mock settings used to simulate Langflow's Settings object for telemetry testing."""

    def __init__(self, prometheus_port: int | None = None, prometheus_enabled: bool = True):  # noqa: FBT001, FBT002
        self.prometheus_port = prometheus_port or find_free_port()
        self.prometheus_enabled = prometheus_enabled
        self.telemetry_base_url = "http://localhost"
        self.do_not_track = True  # Disable actual telemetry reporting for test
        # Add additional required properties
        self.cache_type = "memory"
        self.backend_only = False


class MockSettingsService:
    """Mock settings service to provide access to mocked telemetry configuration."""

    def __init__(self, prometheus_port: int | None = None, prometheus_enabled: bool = True):  # noqa: FBT001, FBT002
        self.settings = MockSettings(prometheus_port, prometheus_enabled)
        # Mock auth settings
        self.auth_settings = type("obj", (object,), {"AUTO_LOGIN": False})


class MockUvicornRun:
    """Mock for uvicorn.run that captures args instead of actually running a server."""

    def __init__(self) -> None:
        self.captured_args: dict[str, Any] = {}
        self.call_count = 0

    def __call__(self, app: Any, **kwargs: Any) -> None:  # noqa: ARG002
        """Capture arguments instead of actually running a server."""
        self.captured_args.update(kwargs)
        self.call_count += 1
        # Simulate server running for a short time then exit
        time.sleep(0.1)


@pytest.fixture(name="fixture_uvicorn_run")
def uvicorn_run() -> MockUvicornRun:
    """Fixture that returns a mock for uvicorn.run."""
    return MockUvicornRun()


@pytest.fixture(name="fixture_telemetry_service")
def telemetry_service(fixture_uvicorn_run: MockUvicornRun) -> Generator[TelemetryService, None, None]:
    """Fixture that returns a fresh instance of TelemetryService with mocked settings and uvicorn."""
    service = TelemetryService(settings_service=MockSettingsService(), uvicorn_run=fixture_uvicorn_run)

    yield service

    # Clean up after the test
    with service._metrics_server_lock:
        service._metrics_server_started = False
        service._metrics_thread = None


@pytest.fixture(name="fixture_opentelemetry_instance")
def opentelemetry_instance() -> OpenTelemetry:
    """Get the OpenTelemetry instance."""
    return OpenTelemetry()


def test_is_test_environment():
    """Test that is_test_environment correctly identifies test environment."""
    assert TelemetryService.is_test_environment() is True


def test_start_metrics_server_skips_in_test_env(
    fixture_telemetry_service: TelemetryService, fixture_uvicorn_run: MockUvicornRun
) -> None:
    """Test that the metrics server doesn't actually start in test environment."""
    # Start the metrics server
    fixture_telemetry_service.start_metrics_server()

    # Allow the thread to potentially start and run
    time.sleep(0.5)

    # Check that uvicorn.run was NOT called due to test environment detection
    assert fixture_uvicorn_run.call_count == 0

    # Flag should still be set to avoid repeated attempts
    assert fixture_telemetry_service._metrics_server_started is True


def test_init(fixture_opentelemetry_instance):
    assert isinstance(fixture_opentelemetry_instance, OpenTelemetry)
    assert len(fixture_opentelemetry_instance._metrics) > 1
    assert len(fixture_opentelemetry_instance._metrics) == len(fixture_opentelemetry_instance._metrics_registry) == 4
    assert "file_uploads" in fixture_opentelemetry_instance._metrics


def test_gauge(fixture_opentelemetry_instance):
    fixture_opentelemetry_instance.update_gauge("file_uploads", 1024, fixed_labels)


def test_gauge_with_counter_method(fixture_opentelemetry_instance):
    with pytest.raises(TypeError, match="Metric 'file_uploads' is not a counter"):
        fixture_opentelemetry_instance.increment_counter(metric_name="file_uploads", value=1, labels=fixed_labels)


def test_gauge_with_historgram_method(fixture_opentelemetry_instance):
    with pytest.raises(TypeError, match="Metric 'file_uploads' is not a histogram"):
        fixture_opentelemetry_instance.observe_histogram("file_uploads", 1, fixed_labels)


def test_gauge_with_up_down_counter_method(fixture_opentelemetry_instance):
    with pytest.raises(TypeError, match="Metric 'file_uploads' is not an up down counter"):
        fixture_opentelemetry_instance.up_down_counter("file_uploads", 1, labels=fixed_labels)


def test_increment_counter(fixture_opentelemetry_instance):
    fixture_opentelemetry_instance.increment_counter(metric_name="num_files_uploaded", value=5, labels=fixed_labels)


def test_increment_counter_empty_label(fixture_opentelemetry_instance):
    with pytest.raises(ValueError, match="Labels must be provided for the metric"):
        fixture_opentelemetry_instance.increment_counter(metric_name="num_files_uploaded", value=5, labels={})


def test_increment_counter_missing_mandatory_label(fixture_opentelemetry_instance):
    with pytest.raises(ValueError, match=re.escape("Missing required labels: {'flow_id'}")):
        fixture_opentelemetry_instance.increment_counter(
            metric_name="num_files_uploaded", value=5, labels={"service": "one"}
        )


def test_increment_counter_unregisted_metric(fixture_opentelemetry_instance):
    with pytest.raises(ValueError, match="Metric 'num_files_uploaded_1' is not registered"):
        fixture_opentelemetry_instance.increment_counter(
            metric_name="num_files_uploaded_1", value=5, labels=fixed_labels
        )


def test_opentelementry_singleton(fixture_opentelemetry_instance):
    fixture_opentelemetry_instance_2 = OpenTelemetry()
    assert fixture_opentelemetry_instance is fixture_opentelemetry_instance_2

    fixture_opentelemetry_instance_3 = OpenTelemetry(prometheus_enabled=False)
    assert fixture_opentelemetry_instance is fixture_opentelemetry_instance_3
    assert fixture_opentelemetry_instance.prometheus_enabled == fixture_opentelemetry_instance_3.prometheus_enabled


def test_missing_labels(fixture_opentelemetry_instance):
    with pytest.raises(ValueError, match="Labels must be provided for the metric"):
        fixture_opentelemetry_instance.increment_counter(metric_name="num_files_uploaded", labels=None, value=1.0)
    with pytest.raises(ValueError, match="Labels must be provided for the metric"):
        fixture_opentelemetry_instance.up_down_counter("num_files_uploaded", 1, None)
    with pytest.raises(ValueError, match="Labels must be provided for the metric"):
        fixture_opentelemetry_instance.update_gauge(metric_name="num_files_uploaded", value=1.0, labels={})
    with pytest.raises(ValueError, match="Labels must be provided for the metric"):
        fixture_opentelemetry_instance.observe_histogram("num_files_uploaded", 1, {})


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


### Metrics Tests ###


def test_fastapi_version_metric_exists(fixture_opentelemetry_instance: OpenTelemetry):
    """Test that the fastapi_version metric is registered and can be updated."""
    assert "fastapi_version" in fixture_opentelemetry_instance._metrics_registry
    metric = fixture_opentelemetry_instance._metrics_registry["fastapi_version"]
    assert metric.name == "fastapi_version"
    assert metric.type == MetricType.OBSERVABLE_GAUGE
    assert metric.unit == ""
    assert metric.labels == {"version": True}


def test_langflow_version_metric_exists(fixture_opentelemetry_instance: OpenTelemetry):
    """Test that the langflow_version metric is registered and can be updated."""
    assert "langflow_version" in fixture_opentelemetry_instance._metrics_registry
    metric = fixture_opentelemetry_instance._metrics_registry["langflow_version"]
    assert metric.name == "langflow_version"
    assert metric.type == MetricType.OBSERVABLE_GAUGE
    assert metric.unit == ""
    assert metric.labels == {"version": True}


def test_fastapi_version_update(fixture_opentelemetry_instance: OpenTelemetry):
    """Test that the fastapi_version metric can be updated."""
    fixture_opentelemetry_instance.update_gauge("fastapi_version", 5.0, fastapi_version_labels)

    gauge = fixture_opentelemetry_instance._metrics["fastapi_version"]
    assert gauge is not None, "FastAPI version gauge not found"

    label_tuple = tuple(fastapi_version_labels.items())
    assert label_tuple in gauge._values, "FastAPI version gauge not found in _values"
    assert gauge._values[label_tuple] == 5.0


def test_langflow_version_update(fixture_opentelemetry_instance: OpenTelemetry):
    """Test that the langflow_version metric can be updated."""
    fixture_opentelemetry_instance.update_gauge("langflow_version", 5.0, langflow_version_labels)

    gauge = fixture_opentelemetry_instance._metrics["langflow_version"]
    assert gauge is not None, "Langflow version gauge not found"

    label_tuple = tuple(langflow_version_labels.items())
    assert label_tuple in gauge._values, "Langflow version gauge not found in _values"
    assert gauge._values[label_tuple] == 5.0


def test_fastapi_version_gauge_with_counter_method(fixture_opentelemetry_instance: OpenTelemetry):
    """Test that the fastapi_version metric is not a counter."""
    with pytest.raises(TypeError, match="Metric 'fastapi_version' is not a counter"):
        fixture_opentelemetry_instance.increment_counter(
            metric_name="fastapi_version", value=1, labels=fastapi_version_labels
        )


def test_fastapi_version_gauge_with_historgram_method(fixture_opentelemetry_instance: OpenTelemetry):
    """Test that the fastapi_version metric is not a histogram."""
    with pytest.raises(TypeError, match="Metric 'fastapi_version' is not a histogram"):
        fixture_opentelemetry_instance.observe_histogram("fastapi_version", 1, fastapi_version_labels)


def test_fastapi_version_gauge_with_up_down_counter_method(fixture_opentelemetry_instance: OpenTelemetry):
    """Test that the fastapi_version metric is not an up down counter."""
    with pytest.raises(TypeError, match="Metric 'fastapi_version' is not an up down counter"):
        fixture_opentelemetry_instance.up_down_counter("fastapi_version", 1, labels=fastapi_version_labels)


def test_langflow_version_gauge_with_counter_method(fixture_opentelemetry_instance: OpenTelemetry):
    """Test that the langflow_version metric is not a counter."""
    with pytest.raises(TypeError, match="Metric 'langflow_version' is not a counter"):
        fixture_opentelemetry_instance.increment_counter(
            metric_name="langflow_version", value=1, labels=langflow_version_labels
        )


def test_langflow_version_gauge_with_historgram_method(fixture_opentelemetry_instance: OpenTelemetry):
    """Test that the langflow_version metric is not a histogram."""
    with pytest.raises(TypeError, match="Metric 'langflow_version' is not a histogram"):
        fixture_opentelemetry_instance.observe_histogram("langflow_version", 1, langflow_version_labels)


def test_langflow_version_gauge_with_up_down_counter_method(fixture_opentelemetry_instance: OpenTelemetry):
    """Test that the langflow_version metric is not an up down counter."""
    with pytest.raises(TypeError, match="Metric 'langflow_version' is not an up down counter"):
        fixture_opentelemetry_instance.up_down_counter("langflow_version", 1, labels=langflow_version_labels)


### Metrics Server Tests ###
def test_start_metrics_server_starts_thread(
    fixture_telemetry_service: TelemetryService, fixture_uvicorn_run: MockUvicornRun
) -> None:
    """Test that the metrics server starts and calls uvicorn run with expected args."""
    # Start the metrics server
    fixture_telemetry_service.start_metrics_server(bypass_test_check=True)

    # Allow the thread to start and run
    time.sleep(0.5)

    # Check that uvicorn.run was called
    assert fixture_uvicorn_run.call_count == 1

    # Verify expected arguments
    port = fixture_telemetry_service.settings_service.settings.prometheus_port
    assert fixture_uvicorn_run.captured_args["port"] == port
    assert fixture_uvicorn_run.captured_args["access_log"] is False
    assert fixture_uvicorn_run.captured_args["timeout_keep_alive"] == 5


def test_start_metrics_server_is_idempotent(
    fixture_telemetry_service: TelemetryService, fixture_uvicorn_run: MockUvicornRun
) -> None:
    """Test that calling start_metrics_server() multiple times doesn't start multiple servers."""
    # Start the server for the first time
    fixture_telemetry_service.start_metrics_server(bypass_test_check=True)
    time.sleep(0.5)

    # Check initial call count
    first_call_count = fixture_uvicorn_run.call_count
    assert first_call_count == 1

    # Try calling it again
    fixture_telemetry_service.start_metrics_server(bypass_test_check=True)
    time.sleep(0.5)

    # Verify that uvicorn.run wasn't called again
    assert fixture_uvicorn_run.call_count == first_call_count

    # Check that the flag remains set
    assert fixture_telemetry_service._metrics_server_started is True


def test_metrics_server_thread_named_correctly(monkeypatch: pytest.MonkeyPatch):
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
    service.start_metrics_server(bypass_test_check=True)

    # Assert the thread name used
    assert "PrometheusMetricsServer" in started_threads


def test_metrics_server_respects_env(monkeypatch: pytest.MonkeyPatch, fixture_uvicorn_run: MockUvicornRun) -> None:
    """Ensure LANGFLOW_METRICS_HOST and LANGFLOW_METRICS_LOG_LEVEL are respected."""
    env_host = "127.0.0.1"
    env_log_level = "info"

    monkeypatch.setenv("LANGFLOW_METRICS_HOST", env_host)
    monkeypatch.setenv("LANGFLOW_METRICS_LOG_LEVEL", env_log_level)

    # Create service with our mock
    service = TelemetryService(settings_service=MockSettingsService(), uvicorn_run=fixture_uvicorn_run)

    # Start the server
    service.start_metrics_server(bypass_test_check=True)
    time.sleep(0.5)

    # Check that our environment variables were used
    assert fixture_uvicorn_run.captured_args["host"] == env_host
    assert fixture_uvicorn_run.captured_args["log_level"] == env_log_level


def test_metrics_server_thread_is_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Check that the metrics server thread is daemonized."""
    created_threads = []

    class MockThread(threading.Thread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created_threads.append(self)

    monkeypatch.setattr(threading, "Thread", MockThread)

    # Use a mock that doesn't actually run the server
    mock_uvicorn = MockUvicornRun()

    # Create and start the service
    service = TelemetryService(settings_service=MockSettingsService(), uvicorn_run=mock_uvicorn)
    service.start_metrics_server(bypass_test_check=True)

    # Look for the thread with the name we expect
    metrics_thread = next(
        (t for t in created_threads if t.name == "PrometheusMetricsServer"),
        None,
    )

    assert metrics_thread is not None, "Expected metrics server thread to be created"
    assert metrics_thread.daemon is True, "Metrics thread should be daemonized"


def test_start_metrics_server_with_custom_parameters(fixture_uvicorn_run: MockUvicornRun) -> None:
    """Test that custom thread name and daemon status are respected."""
    # Create service with our mock
    service = TelemetryService(settings_service=MockSettingsService(), uvicorn_run=fixture_uvicorn_run)

    # Use custom parameters
    custom_thread_name = "CustomMetricsThread"
    service.start_metrics_server(thread_name=custom_thread_name, daemon=False, bypass_test_check=True)

    # Check thread properties
    assert service._metrics_thread is not None
    assert service._metrics_thread.name == custom_thread_name
    assert service._metrics_thread.daemon is False


def test_stop_metrics_server(fixture_telemetry_service: TelemetryService) -> None:
    """Test that stop_metrics_server properly sets flags and events."""
    # Start the server
    fixture_telemetry_service.start_metrics_server(bypass_test_check=True)
    time.sleep(0.5)

    # Check initial state
    assert fixture_telemetry_service._metrics_server_started is True
    assert fixture_telemetry_service._metrics_server_stop_event.is_set() is False

    # Stop the server
    fixture_telemetry_service.stop_metrics_server()

    # Check that flags and events were updated
    assert fixture_telemetry_service._metrics_server_started is False
    assert fixture_telemetry_service._metrics_server_stop_event.is_set() is True


def test_on_error_callback_called() -> None:
    """Test that the on_error callback is called when the server fails to start."""

    # Create a mock function to inject that raises an exception
    def mock_uvicorn_error(*args, **kwargs):  # noqa: ARG001
        raise Exception("Test error")  # noqa: EM101, TRY002, TRY003

    # Create a mock callback that records if it was called
    callback_called = False
    exception_received = None

    def on_error_callback(exc):
        nonlocal callback_called, exception_received
        callback_called = True
        exception_received = exc

    # Create service with our error-raising mock
    service = TelemetryService(settings_service=MockSettingsService(), uvicorn_run=mock_uvicorn_error)

    # Start the server with our callback
    service.start_metrics_server(on_error=on_error_callback, bypass_test_check=True)
    time.sleep(0.5)  # Give thread time to run

    # Check that callback was called with the exception
    assert callback_called is True
    assert isinstance(exception_received, Exception)
    assert str(exception_received) == "Test error"

    # Verify the started flag was reset
    assert service._metrics_server_started is False


def test_port_check_prevents_start_on_used_port(
    monkeypatch: pytest.MonkeyPatch, fixture_uvicorn_run: MockUvicornRun
) -> None:
    """Test that the port check prevents server start if port is already in use."""

    # Mock socket.connect_ex to simulate port already in use
    def mock_connect_ex(self, address):  # noqa: ARG001
        return 0  # Return 0 to indicate connection successful (port in use)

    # Apply the mock
    monkeypatch.setattr("socket.socket.connect_ex", mock_connect_ex)

    # Create service
    service = TelemetryService(settings_service=MockSettingsService(), uvicorn_run=fixture_uvicorn_run)

    # Start the server
    service.start_metrics_server(bypass_test_check=True)
    time.sleep(0.5)

    # Verify that uvicorn.run was not called due to port check
    assert fixture_uvicorn_run.call_count == 0

    # Verify the started flag was reset
    assert service._metrics_server_started is False
