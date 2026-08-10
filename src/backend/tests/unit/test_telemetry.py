import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from langflow.services.telemetry.opentelemetry import (
    MetricType,
    OpenTelemetry,
    ThreadSafeSingletonMetaUsingWeakref,
)
from langflow.services.telemetry.schema import DeploymentPayload
from langflow.services.telemetry.service import TelemetryService


@pytest.fixture
def mock_settings_service(mocker):
    settings = mocker.MagicMock()
    settings.settings.telemetry_base_url = "http://test.telemetry"
    settings.settings.prometheus_enabled = False
    settings.settings.do_not_track = False
    return settings


@pytest.fixture
def telemetry_service(mock_settings_service):
    return TelemetryService(mock_settings_service)


@pytest.mark.asyncio
async def test_log_package_deployment(telemetry_service):
    payload = DeploymentPayload(
        deployment_action="deployment.create",
        deployment_provider="test_provider",
        deployment_seconds=1.0,
        deployment_success=True,
    )
    await telemetry_service.log_package_deployment(payload)
    func, queued_payload, path = await telemetry_service.telemetry_queue.get()
    assert func == telemetry_service.send_telemetry_data
    assert queued_payload == payload
    assert path == "deployment"


@pytest.mark.asyncio
async def test_log_package_deployment_provider(telemetry_service):
    payload = DeploymentPayload(
        deployment_action="provider.create",
        deployment_provider="test_provider",
        deployment_seconds=1.0,
        deployment_success=True,
    )
    await telemetry_service.log_package_deployment_provider(payload)
    func, queued_payload, path = await telemetry_service.telemetry_queue.get()
    assert func == telemetry_service.send_telemetry_data
    assert queued_payload == payload
    assert path == "deployment_provider"


@pytest.mark.asyncio
async def test_log_package_deployment_run(telemetry_service):
    payload = DeploymentPayload(
        deployment_action="deployment.run",
        deployment_provider="test_provider",
        deployment_seconds=1.0,
        deployment_success=True,
    )
    await telemetry_service.log_package_deployment_run(payload)
    func, queued_payload, path = await telemetry_service.telemetry_queue.get()
    assert func == telemetry_service.send_telemetry_data
    assert queued_payload == payload
    assert path == "deployment_run"


@pytest.mark.asyncio
async def test_log_package_deployment_do_not_track(telemetry_service):
    telemetry_service.do_not_track = True
    payload = DeploymentPayload(
        deployment_action="deployment.create",
        deployment_provider="test_provider",
        deployment_seconds=1.0,
        deployment_success=True,
    )
    await telemetry_service.log_package_deployment(payload)
    await telemetry_service.log_package_deployment_provider(payload)
    await telemetry_service.log_package_deployment_run(payload)
    assert telemetry_service.telemetry_queue.empty()


fixed_labels = {"flow_id": "this_flow_id", "service": "this", "user": "that"}


@pytest.fixture
def opentelemetry_instance():
    # Force a fresh, fully initialized singleton. pytest-split can schedule this module
    # without the sibling tests that would otherwise build it, and TelemetryService
    # teardowns elsewhere in the same worker call OpenTelemetry().shutdown(), which empties
    # the instrument dict while the metric definitions survive. Grabbing the singleton
    # as-is in that state fails with "Metric '...' is not a counter".
    ThreadSafeSingletonMetaUsingWeakref._instances.pop(OpenTelemetry, None)
    OpenTelemetry._initialized = False
    return OpenTelemetry()


@pytest.fixture(scope="session", autouse=True)
def cleanup_telemetry():
    yield
    OpenTelemetry().shutdown()


def test_init(opentelemetry_instance):
    expected_metrics = {
        "file_uploads",
        "num_files_uploaded",
        "langflow_job_queue_cancel_events_total",
        "langflow_job_queue_active_jobs",
    }

    assert isinstance(opentelemetry_instance, OpenTelemetry)
    assert set(opentelemetry_instance._metrics) == expected_metrics
    assert set(opentelemetry_instance._metrics_registry) == expected_metrics
    cancel_events = opentelemetry_instance._metrics_registry["langflow_job_queue_cancel_events_total"]
    assert cancel_events.type is MetricType.COUNTER
    assert cancel_events.labels == {"event_type": True}
    active_jobs = opentelemetry_instance._metrics_registry["langflow_job_queue_active_jobs"]
    assert active_jobs.type is MetricType.UP_DOWN_COUNTER
    assert active_jobs.labels == {"backend": True}


def test_prometheus_exports_job_queue_metrics():
    script = """
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from prometheus_client import generate_latest

otel = OpenTelemetry(prometheus_enabled=True)
otel.increment_counter("langflow_job_queue_cancel_events_total", {"event_type": "published"})
otel.up_down_counter("langflow_job_queue_active_jobs", 1, {"backend": "redis"})
metrics = generate_latest().decode()
assert "langflow_job_queue_cancel_events_total" in metrics
assert 'event_type="published"' in metrics
assert "langflow_job_queue_active_jobs" in metrics
assert 'backend="redis"' in metrics
"""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


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


def test_recovers_when_instruments_are_missing():
    """Rebuild instruments when definitions survive but instruments are gone.

    Nightly CI regression: a TelemetryService teardown reached shutdown() while the
    instance stayed referenced, and the next construction had to rebuild the instruments
    instead of raising "Metric 'num_files_uploaded' is not a counter".
    """
    stale = OpenTelemetry()
    stale._metrics.clear()
    OpenTelemetry._initialized = True
    ThreadSafeSingletonMetaUsingWeakref._instances.pop(OpenTelemetry, None)

    healed = OpenTelemetry()
    healed.increment_counter(metric_name="num_files_uploaded", value=1, labels=fixed_labels)


def test_new_instance_after_shutdown_recovers(opentelemetry_instance):
    """shutdown() must not leave a live-but-gutted singleton behind.

    The next OpenTelemetry() call builds a fresh instance with working instruments even
    while a reference to the shut-down one is still alive.
    """
    opentelemetry_instance.shutdown()

    replacement = OpenTelemetry()
    assert replacement is not opentelemetry_instance
    replacement.increment_counter(metric_name="num_files_uploaded", value=1, labels=fixed_labels)


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
