import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from langflow.services.telemetry.context import reset_current_telemetry_user, set_current_telemetry_user
from langflow.services.telemetry.opentelemetry import (
    MetricType,
    OpenTelemetry,
    ThreadSafeSingletonMetaUsingWeakref,
)
from langflow.services.telemetry.schema import DeploymentPayload, IntegrationActionPayload, ShutdownPayload
from langflow.services.telemetry.service import TelemetryService
from lfx.services.telemetry.identity import get_hashed_user_id


@pytest.fixture
def mock_settings_service(mocker, tmp_path):
    settings = mocker.MagicMock()
    settings.settings.config_dir = str(tmp_path)
    settings.settings.segment_api_url = "https://api.segment.test/v1/track"
    settings.settings.segment_write_key = "segment-test-key"
    settings.settings.prometheus_enabled = False
    settings.settings.do_not_track = False
    return settings


@pytest.fixture
def telemetry_service(mock_settings_service):
    return TelemetryService(mock_settings_service)


def test_disabled_telemetry_does_not_create_identity(mock_settings_service, tmp_path):
    mock_settings_service.settings.segment_write_key = None

    service = TelemetryService(mock_settings_service)

    assert service.anonymous_id == ""
    assert not (tmp_path / "telemetry_id").exists()


@pytest.mark.asyncio
async def test_log_package_deployment(telemetry_service):
    payload = DeploymentPayload(
        deployment_action="deployment.create",
        deployment_provider="test_provider",
        deployment_seconds=1.0,
        deployment_success=True,
    )
    await telemetry_service.log_package_deployment(payload)
    func, queued_payload, path, user_id = await telemetry_service.telemetry_queue.get()
    assert func == telemetry_service.send_telemetry_data
    assert queued_payload == payload
    assert path == "deployment"
    assert user_id is None


@pytest.mark.asyncio
async def test_queue_captures_request_user_id(telemetry_service):
    payload = DeploymentPayload(
        deployment_action="deployment.create",
        deployment_provider="test_provider",
        deployment_seconds=1.0,
        deployment_success=True,
    )
    token = set_current_telemetry_user("alice")
    try:
        await telemetry_service.log_package_deployment(payload)
    finally:
        reset_current_telemetry_user(token)

    _func, _queued_payload, _path, user_id = telemetry_service.telemetry_queue.get_nowait()
    assert user_id == get_hashed_user_id("alice")


@pytest.mark.asyncio
@pytest.mark.parametrize("do_not_track", [False, True])
async def test_integration_action_uses_telemetry_queue(telemetry_service, do_not_track):
    telemetry_service.do_not_track = do_not_track
    payload = IntegrationActionPayload(
        provider="google",
        capability="drive.read",
        owner_kind="env",
        principal_kind="headless_operator",
        ms=1,
        success=True,
    )
    await telemetry_service.log_integration_action(payload)
    if do_not_track:
        assert telemetry_service.telemetry_queue.empty()
    else:
        send, queued, path, user_id = telemetry_service.telemetry_queue.get_nowait()
        assert send == telemetry_service.send_telemetry_data
        assert queued == payload
        assert path == "integration_action"
        assert user_id is None
        telemetry_service.telemetry_queue.task_done()


@pytest.mark.asyncio
async def test_log_package_deployment_provider(telemetry_service):
    payload = DeploymentPayload(
        deployment_action="provider.create",
        deployment_provider="test_provider",
        deployment_seconds=1.0,
        deployment_success=True,
    )
    await telemetry_service.log_package_deployment_provider(payload)
    func, queued_payload, path, user_id = await telemetry_service.telemetry_queue.get()
    assert func == telemetry_service.send_telemetry_data
    assert queued_payload == payload
    assert path == "deployment_provider"
    assert user_id is None


@pytest.mark.asyncio
async def test_log_package_deployment_run(telemetry_service):
    payload = DeploymentPayload(
        deployment_action="deployment.run",
        deployment_provider="test_provider",
        deployment_seconds=1.0,
        deployment_success=True,
    )
    await telemetry_service.log_package_deployment_run(payload)
    func, queued_payload, path, user_id = await telemetry_service.telemetry_queue.get()
    assert func == telemetry_service.send_telemetry_data
    assert queued_payload == payload
    assert path == "deployment_run"
    assert user_id is None


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


@pytest.mark.asyncio
async def test_log_package_deployment_without_segment_key(telemetry_service):
    telemetry_service.segment_write_key = None
    payload = DeploymentPayload(
        deployment_action="deployment.create",
        deployment_provider="test_provider",
        deployment_seconds=1.0,
        deployment_success=True,
    )

    await telemetry_service.log_package_deployment(payload)

    assert telemetry_service.telemetry_queue.empty()


@pytest.mark.asyncio
async def test_log_package_shutdown_uses_telemetry_queue(telemetry_service):
    await telemetry_service.log_package_shutdown()

    send, payload, path, user_id = telemetry_service.telemetry_queue.get_nowait()
    assert send == telemetry_service.send_telemetry_data
    assert isinstance(payload, ShutdownPayload)
    assert path == "shutdown"
    assert user_id is None


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
