"""Lifespan wiring for the background-execution metrics collector.

The lifespan starts the collector ONLY in the process that actually bound the
Prometheus exposition port (so ``gunicorn -w N`` does not spawn N collectors all
querying the DB while only one process exposes metrics). The start/stop logic is
factored into ``maybe_start_metrics_collector`` / ``stop_metrics_collector`` so it
is testable directly against the REAL collector, real telemetry singleton, and the
real test DB — no mocking, no wall-clock sleeps for correctness.

These prove:
1. Started only when this process bound the port (``prometheus_started=True``) AND
   the feature is on (``prometheus_enabled=True``).
2. NOT started when this process lost the port (EADDRINUSE -> ``prometheus_started
   =False``), even with the feature on — that is the per-process gate that keeps a
   second worker from running a duplicate collector.
3. NOT started when the feature is off.
4. A clean stop that actually finishes the loop task, idempotent and safe when no
   collector was ever started.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from langflow.services.background_execution.metrics_collector import (
    BackgroundMetricsCollector,
    maybe_start_metrics_collector,
    stop_metrics_collector,
)
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from lfx.services.settings.base import Settings

pytestmark = pytest.mark.usefixtures("client")


def _settings(*, prometheus_enabled: bool) -> Settings:
    """A REAL Settings derived from the app's own settings with a fast interval.

    ``Settings`` ignores constructor kwargs (its ``settings_customise_sources``
    drops ``init_settings``), so we ``model_copy`` the live app settings with the
    overrides — the result is a real, validated Settings. A short interval keeps
    the loop responsive in the lifecycle assertion without a wall-clock sleep for
    correctness.
    """
    base = get_settings_service().settings
    return base.model_copy(update={"prometheus_enabled": prometheus_enabled, "background_metrics_interval": 1})


async def test_started_when_port_bound_and_enabled():
    """Started only when this process bound the port and the feature is on."""
    app = FastAPI()

    await maybe_start_metrics_collector(app, _settings(prometheus_enabled=True), prometheus_started=True)

    collector = app.state.background_metrics_collector
    assert isinstance(collector, BackgroundMetricsCollector)
    # The loop task is live: created and not yet finished.
    assert collector._task is not None
    assert not collector._task.done()
    # The registry interval/retention are wired from settings so the online window
    # (3x interval) and the per-tick prune match the worker's own registry config.
    settings = _settings(prometheus_enabled=True)
    assert collector.registry_interval == settings.background_worker_registry_interval_s
    assert collector.registry_retention_s == settings.background_worker_registry_retention_s

    await stop_metrics_collector(app)
    # Stop actually ended the loop: task cleared and the underlying task finished.
    assert collector._task is None


async def test_not_started_when_port_lost_even_if_enabled():
    """A worker that lost the Prometheus port (EADDRINUSE) must not run a collector.

    This is the per-process gate that prevents ``gunicorn -w N`` from spawning N
    DB-querying collectors. ``prometheus_started=False`` even though the feature is
    on.
    """
    app = FastAPI()

    await maybe_start_metrics_collector(app, _settings(prometheus_enabled=True), prometheus_started=False)

    assert app.state.background_metrics_collector is None


async def test_not_started_when_feature_disabled():
    """Feature off -> nothing exposed -> nothing to collect, even if port-started flag is set."""
    app = FastAPI()

    await maybe_start_metrics_collector(app, _settings(prometheus_enabled=False), prometheus_started=True)

    assert app.state.background_metrics_collector is None


async def test_stop_is_safe_when_never_started():
    """Shutdown path must not raise when startup never created a collector.

    Covers both an unset attribute and an explicit ``None`` (the value the start
    helper leaves when gated off).
    """
    app = FastAPI()
    # Attribute never set (startup failed before the start helper ran).
    await stop_metrics_collector(app)

    # Explicit None (start helper ran but gated off).
    app.state.background_metrics_collector = None
    await stop_metrics_collector(app)


async def test_stop_cancels_a_running_task():
    """Stop cancels the live loop task and the task is actually finished afterward."""
    app = FastAPI()
    await maybe_start_metrics_collector(app, _settings(prometheus_enabled=True), prometheus_started=True)
    collector = app.state.background_metrics_collector
    task = collector._task

    # Yield once so the loop task is scheduled and running before we stop it.
    await asyncio.sleep(0)
    assert not task.done()

    await stop_metrics_collector(app)
    assert task.done()
    assert collector._task is None
