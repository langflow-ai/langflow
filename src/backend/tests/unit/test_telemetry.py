from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from langflow.services.telemetry.run_event_store import pop_all
from langflow.services.telemetry.schema import RunPayload
from langflow.services.telemetry.service import TelemetryService


@pytest.fixture
def telemetry_service():
    service = TelemetryService(SimpleNamespace(settings=SimpleNamespace(prometheus_enabled=False)))
    pop_all()
    yield service
    pop_all()


async def test_run_completion_is_recorded_without_network_io(telemetry_service):
    payload = RunPayload(run_seconds=1, run_success=True, run_id="run-1")

    await telemetry_service.log_package_run(payload)

    assert pop_all() == [payload]


@pytest.mark.parametrize("legacy_optout", [None, False])
async def test_run_and_lifecycle_issue_no_http_requests(monkeypatch, legacy_optout):
    requests = []
    pop_all()
    settings = SimpleNamespace(prometheus_enabled=False)
    if legacy_optout is not None:
        settings.do_not_track = legacy_optout
    telemetry_service = TelemetryService(SimpleNamespace(settings=settings))

    async def fail_send(*args, **kwargs):
        requests.append((args, kwargs))
        raise AssertionError

    monkeypatch.setattr(httpx.AsyncClient, "send", fail_send)

    try:
        telemetry_service.start()
        await telemetry_service.log_package_run(RunPayload(run_seconds=1, run_success=True))
        await telemetry_service.flush()
    finally:
        await telemetry_service.teardown()
        pop_all()

    assert requests == []


async def test_run_completion_preserves_existing_timestamp(telemetry_service):
    completed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    payload = RunPayload(run_seconds=1, run_success=True, run_completed_at=completed_at)

    await telemetry_service.log_package_run(payload)

    assert pop_all()[0].run_completed_at == completed_at


async def test_lifecycle_keeps_open_telemetry_provider(telemetry_service):
    telemetry_service.start()
    assert telemetry_service.running

    await telemetry_service.flush()
    await telemetry_service.stop()
    assert not telemetry_service.running
