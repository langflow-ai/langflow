import pytest
from langflow.services.telemetry.opentelemetry import MetricType, OpenTelemetry


@pytest.fixture
def ot():
    return OpenTelemetry(prometheus_enabled=False)


BG_METRICS = {
    "langflow_bg_jobs": MetricType.OBSERVABLE_GAUGE,
    "langflow_bg_oldest_queued_seconds": MetricType.OBSERVABLE_GAUGE,
    "langflow_bg_workers_online": MetricType.OBSERVABLE_GAUGE,
    "langflow_bg_workers_busy": MetricType.OBSERVABLE_GAUGE,
    "langflow_bg_workers_idle": MetricType.OBSERVABLE_GAUGE,
    "langflow_bg_jobs_started_total": MetricType.OBSERVABLE_COUNTER,
    "langflow_bg_jobs_completed_total": MetricType.OBSERVABLE_COUNTER,
    "langflow_bg_jobs_failed_total": MetricType.OBSERVABLE_COUNTER,
    "langflow_bg_orphans_reconciled_total": MetricType.OBSERVABLE_COUNTER,
    "langflow_bg_job_duration_p50_seconds": MetricType.OBSERVABLE_GAUGE,
    "langflow_bg_job_duration_p95_seconds": MetricType.OBSERVABLE_GAUGE,
}


@pytest.mark.parametrize(("name", "mtype"), BG_METRICS.items())
def test_bg_metric_registered(ot, name, mtype):
    reg = ot._metrics_registry[name]
    assert reg.type == mtype
    assert "backend" in reg.allowed_labels


def test_set_observable_counter_sets_readable_value(ot):
    labels = {"backend": "scaled"}
    ot.set_observable_counter("langflow_bg_jobs_started_total", 1, labels)
    key = tuple(sorted(labels.items()))
    assert ot._metrics["langflow_bg_jobs_started_total"]._values[key] == 1


def test_set_observable_counter_on_non_observable_counter_raises(ot):
    with pytest.raises(TypeError):
        ot.set_observable_counter("langflow_bg_workers_online", 1, {"backend": "scaled"})
