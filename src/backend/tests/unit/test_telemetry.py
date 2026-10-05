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
from langflow.services.telemetry.schema import DeploymentPayload, IntegrationActionPayload, RunPayload
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
@pytest.mark.parametrize("do_not_track", [False, True])
async def test_run_completion_is_recorded_before_tracking_consent(telemetry_service, do_not_track):
    from langflow.services.telemetry.run_event_store import pop_all

    pop_all()
    telemetry_service.do_not_track = do_not_track
    payload = RunPayload(run_seconds=1, run_success=True)
    await telemetry_service.log_package_run(payload)
    events = pop_all()
    assert len(events) == 1
    assert events[0].run_completed_at is not None
    assert telemetry_service.telemetry_queue.empty() is do_not_track


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
        send, queued, path = telemetry_service.telemetry_queue.get_nowait()
        assert send == telemetry_service.send_telemetry_data
        assert queued == payload
        assert path == "integration_action"
        telemetry_service.telemetry_queue.task_done()
    await telemetry_service.client.aclose()


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
    # The background job metrics, keyed by the type they must be registered as. Observable
    # counters have to stay counters: the collector feeds cumulative values, and a gauge would
    # make rate() read them as a level.
    expected_bg_metrics = {
        "langflow_bg_jobs": MetricType.OBSERVABLE_GAUGE,
        "langflow_bg_oldest_queued_seconds": MetricType.OBSERVABLE_GAUGE,
        "langflow_bg_jobs_started_total": MetricType.OBSERVABLE_COUNTER,
        "langflow_bg_jobs_completed_total": MetricType.OBSERVABLE_COUNTER,
        "langflow_bg_jobs_failed_total": MetricType.OBSERVABLE_COUNTER,
        "langflow_bg_job_duration_p50_seconds": MetricType.OBSERVABLE_GAUGE,
        "langflow_bg_job_duration_p95_seconds": MetricType.OBSERVABLE_GAUGE,
    }
    expected_metrics = {
        "file_uploads",
        "num_files_uploaded",
        "langflow_job_queue_cancel_events_total",
        "langflow_job_queue_active_jobs",
        *expected_bg_metrics,
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
    for name, metric_type in expected_bg_metrics.items():
        registered = opentelemetry_instance._metrics_registry[name]
        assert registered.type is metric_type, f"{name} is registered as {registered.type}"
        # Every background metric is per-backend, so a deployment running more than one can
        # tell them apart rather than reading one summed series.
        assert registered.labels.get("backend") is True, f"{name} must carry a mandatory backend label"


def test_prometheus_exports_job_queue_metrics():
    script = """
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families

otel = OpenTelemetry(prometheus_enabled=True)
otel.increment_counter("langflow_job_queue_cancel_events_total", {"event_type": "published"})
otel.up_down_counter("langflow_job_queue_active_jobs", 1, {"backend": "redis"})
gauges = {
    "langflow_bg_jobs": ({"backend": "default", "status": "suspended"}, 2),
    "langflow_bg_oldest_queued_seconds": ({"backend": "default"}, 3),
    "langflow_bg_job_duration_p50_seconds": ({"backend": "default"}, 10),
    "langflow_bg_job_duration_p95_seconds": ({"backend": "default"}, 20),
}
counters = {
    "langflow_bg_jobs_started_total": ({"backend": "default"}, 10),
    "langflow_bg_jobs_completed_total": ({"backend": "default"}, 8),
    "langflow_bg_jobs_failed_total": ({"backend": "default", "reason": "input_timeout"}, 2),
}
for name, (labels, value) in gauges.items():
    otel.update_gauge(name, value, labels)
for name, (labels, value) in counters.items():
    otel.set_observable_counter(name, value, labels)
metrics = generate_latest().decode()
assert "langflow_job_queue_cancel_events_total" in metrics
assert 'event_type="published"' in metrics
assert "langflow_job_queue_active_jobs" in metrics
assert 'backend="redis"' in metrics
for _ in range(2):
    snapshot = generate_latest().decode()
    samples = {
        sample.name: sample
        for family in text_string_to_metric_families(snapshot)
        for sample in family.samples
        if sample.name.startswith("langflow_bg_")
    }
    assert set(samples) == gauges.keys() | counters.keys(), samples
    for name, (labels, value) in (gauges | counters).items():
        assert labels.items() <= samples[name].labels.items(), samples[name]
        assert samples[name].value == value, samples[name]
    # Corrections between scrapes must not export a counter decrease.
    for name, (labels, value) in counters.items():
        otel.set_observable_counter(name, value - 1, labels)

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


@pytest.mark.parametrize("metric_name", ["langflow_bg_jobs_started_total", "langflow_bg_jobs_completed_total"])
def test_observable_counter_preserves_max_per_labels(opentelemetry_instance, metric_name):
    """Reclassification cannot export a decrease, and backend series are independent."""
    from opentelemetry.metrics import CallbackOptions

    ot = opentelemetry_instance
    for value in (10, 7, 11, 0):
        ot.set_observable_counter(metric_name, value, {"backend": "default"})
    ot.set_observable_counter(metric_name, 2, {"backend": "scaled"})
    observations = ot._metrics[metric_name]._callback(CallbackOptions())
    assert {o.attributes["backend"]: o.value for o in observations} == {"default": 11, "scaled": 2}


@pytest.mark.parametrize(
    ("name", "labels", "error", "message"),
    [
        ("missing", {}, ValueError, "not registered"),
        ("langflow_bg_jobs_started_total", {}, ValueError, "Labels must be provided"),
        ("langflow_bg_jobs_started_total", {"reason": "error"}, ValueError, "backend"),
        ("langflow_bg_jobs", {"backend": "default", "status": "queued"}, TypeError, "not an observable counter"),
    ],
)
def test_observable_counter_validates_metric_and_labels(opentelemetry_instance, name, labels, error, message):
    """The observable setter preserves registry, label, and instrument type validation."""
    with pytest.raises(error, match=message):
        opentelemetry_instance.set_observable_counter(name, 1, labels)
