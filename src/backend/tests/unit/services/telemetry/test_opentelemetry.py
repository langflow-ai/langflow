import pytest
from langflow.services.telemetry.opentelemetry import MetricType, OpenTelemetry


@pytest.fixture
def ot():
    return OpenTelemetry(prometheus_enabled=False)


BG_METRICS = {
    "langflow_bg_jobs": MetricType.OBSERVABLE_GAUGE,
    "langflow_bg_oldest_queued_seconds": MetricType.OBSERVABLE_GAUGE,
    "langflow_bg_alive_workers": MetricType.OBSERVABLE_GAUGE,
    "langflow_bg_jobs_started_total": MetricType.COUNTER,
    "langflow_bg_jobs_completed_total": MetricType.COUNTER,
    "langflow_bg_jobs_failed_total": MetricType.COUNTER,
    "langflow_bg_orphans_reconciled_total": MetricType.COUNTER,
    "langflow_bg_job_duration_seconds": MetricType.HISTOGRAM,
}


@pytest.mark.parametrize(("name", "mtype"), BG_METRICS.items())
def test_bg_metric_registered(ot, name, mtype):
    reg = ot._metrics_registry[name]
    assert reg.type == mtype
    assert "backend" in reg.allowed_labels
