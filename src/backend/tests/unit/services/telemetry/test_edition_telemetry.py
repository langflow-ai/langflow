"""The configured edition is reported to Segment as productPlanName on every event."""

import json
from types import SimpleNamespace

import httpx
import pytest
from langflow.services.telemetry.schema import EmailPayload, RunPayload, VersionPayload
from langflow.services.telemetry.service import TelemetryService

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


@pytest.mark.asyncio
@pytest.mark.parametrize("edition", ["opensource", "enterprise"])
@pytest.mark.parametrize(
    ("payload", "path"),
    [
        (VERSION_PAYLOAD, None),
        (RunPayload(run_seconds=1, run_success=True), "run"),
        (EmailPayload(email="registered@example.com"), "email"),
    ],
)
async def test_edition_is_sent_as_product_plan_name(tmp_path, edition, payload, path):
    settings = SimpleNamespace(
        settings=SimpleNamespace(
            config_dir=str(tmp_path),
            segment_api_url="https://segment.example.test/v1/track",
            segment_write_key="test-key",
            edition=edition,
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
    properties = json.loads(requests[0].content)["properties"]
    assert properties["productPlanName"] == edition
    assert properties["productCode"] == "WW3151"
