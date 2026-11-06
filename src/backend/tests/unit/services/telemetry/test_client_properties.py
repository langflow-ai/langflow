"""Client properties use names the IBM tracking plan accepts; the plan drops unknown ones."""

import json
import platform
from types import SimpleNamespace

import httpx
import pytest
from langflow.services.telemetry.schema import RunPayload, VersionPayload
from langflow.services.telemetry.service import TelemetryService
from langflow.utils.version import get_version_info

VERSION_PAYLOAD = VersionPayload(
    package="langflow",
    version="1.0.0",
    platform="linux",
    python="3.12",
    arch="x86_64",
    auto_login=True,
    cache_type="memory",
    backend_only=False,
)


async def _sent_properties(tmp_path, payload, path) -> dict:
    settings = SimpleNamespace(
        settings=SimpleNamespace(
            config_dir=str(tmp_path),
            segment_api_url="https://segment.example.test/v1/track",
            segment_write_key="test-key",
            edition="opensource",
            do_not_track=False,
            prometheus_enabled=False,
        )
    )
    service = TelemetryService(settings)
    requests = []

    def capture(request):
        requests.append(request)
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(capture)) as client:
        service.client = client
        await service.send_telemetry_data(payload, path)

    assert len(requests) == 1
    return json.loads(requests[0].content)["properties"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("desktop", "expected"), [("false", "Langflow OSS"), ("true", "Langflow Desktop")])
@pytest.mark.parametrize(
    ("payload", "path"), [(RunPayload(run_seconds=1, run_success=True), "run"), (VERSION_PAYLOAD, None)]
)
async def test_reports_the_client_as_sub_product_title(tmp_path, monkeypatch, desktop, expected, payload, path):
    monkeypatch.setenv("LANGFLOW_DESKTOP", desktop)

    properties = await _sent_properties(tmp_path, payload.model_copy(), path)

    assert properties["subProductTitle"] == expected
    assert "clientType" not in properties


@pytest.mark.asyncio
async def test_does_not_send_the_dropped_platform_property(tmp_path):
    properties = await _sent_properties(tmp_path, RunPayload(run_seconds=1, run_success=True), "run")

    assert "platform" not in properties


@pytest.mark.asyncio
async def test_reports_the_langflow_version_as_product_version(tmp_path):
    properties = await _sent_properties(tmp_path, RunPayload(run_seconds=1, run_success=True), "run")

    assert properties["productVersion"] == get_version_info()["version"]
    assert "langflow_version" not in properties


@pytest.mark.asyncio
async def test_reports_the_operating_system_as_os_name(tmp_path):
    properties = await _sent_properties(tmp_path, RunPayload(run_seconds=1, run_success=True), "run")

    assert properties["osName"] == platform.system().lower()
    assert "os" not in properties
