"""Process shutdown sends its final event before closing the transport."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from langflow.services.telemetry.schema import RunPayload
from langflow.services.telemetry.service import TelemetryService


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_teardown_delivers_shutdown_once_after_pending_events(tmp_path, monkeypatch, enabled):
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    settings = SimpleNamespace(
        settings=SimpleNamespace(
            config_dir=str(tmp_path),
            segment_api_url="https://segment.example.test/v1/track",
            segment_write_key="test-key",
            do_not_track=not enabled,
            edition="opensource",
            prometheus_enabled=False,
            cache_type="async",
            backend_only=True,
            database_url="sqlite:///test.db",
        ),
        auth_settings=SimpleNamespace(AUTO_LOGIN=True),
    )
    requests = []
    real_client = httpx.AsyncClient

    def capture(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200)

    monkeypatch.setattr(
        "langflow.services.telemetry.service.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(capture), **kwargs),
    )
    service = TelemetryService(settings)
    service.start()
    if service.log_package_version_task:
        await service.log_package_version_task
    await service.log_package_run(RunPayload(run_seconds=1, run_success=True))

    await asyncio.wait_for(service.teardown(), timeout=2)
    await service.teardown()

    assert [(event["event"], event["properties"]["object"]) for event in requests] == (
        [("Started Process", "version"), ("Ran Process", "run"), ("Ended Process", "shutdown")] if enabled else []
    )
    if enabled:
        assert requests[-1]["properties"]["subProductTitle"] == "Langflow OSS"
        assert requests[-1]["properties"]["timeRunning"] >= 0
    assert not service.running
    assert service.client is None
    assert service.telemetry_queue.empty()
    if service.worker_task:
        assert service.worker_task.done()
