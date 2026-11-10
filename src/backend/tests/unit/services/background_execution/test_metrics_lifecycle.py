"""Collector ownership follows the process that successfully binds Prometheus."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from langflow.services.background_execution.metrics_collector import (
    BackgroundMetricsCollector,
    maybe_start_metrics_collector,
    stop_metrics_collector,
)


@pytest.mark.parametrize(("enabled", "bound"), [(False, False), (False, True), (True, False), (True, True)])
async def test_collector_only_starts_for_enabled_prometheus_owner(enabled, bound):
    """Only an enabled exporter that owns the port may start a collector task."""
    app = FastAPI()
    settings = SimpleNamespace(prometheus_enabled=enabled, background_metrics_interval=17)
    await maybe_start_metrics_collector(app, settings, prometheus_started=bound)
    collector = app.state.background_metrics_collector
    try:
        if enabled and bound:
            assert isinstance(collector, BackgroundMetricsCollector)
            assert collector.interval == 17
            assert collector._task is not None
        else:
            assert collector is None
    finally:
        await stop_metrics_collector(app)
    if collector is not None:
        assert collector._task is None


async def test_collector_start_failure_does_not_fail_application_startup(monkeypatch):
    """An unavailable collector leaves the application usable and cleanup safe."""

    def fail_start(_self):
        msg = "collector task could not start"
        raise RuntimeError(msg)

    monkeypatch.setattr(BackgroundMetricsCollector, "start", fail_start)
    app = FastAPI()
    settings = SimpleNamespace(prometheus_enabled=True, background_metrics_interval=15)
    await maybe_start_metrics_collector(app, settings, prometheus_started=True)
    assert app.state.background_metrics_collector is None
    await stop_metrics_collector(app)


async def test_stop_without_started_collector():
    """Early startup failure may leave the collector state attribute unset."""
    await stop_metrics_collector(FastAPI())


async def test_stop_failure_does_not_fail_application_shutdown():
    """Observability teardown must not mask the application's shutdown result."""

    class FailingCollector:
        async def stop(self):
            msg = "collector stop failed"
            raise RuntimeError(msg)

    app = FastAPI()
    app.state.background_metrics_collector = FailingCollector()
    await stop_metrics_collector(app)
