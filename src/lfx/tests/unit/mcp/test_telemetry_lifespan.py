"""MCP telemetry honors configured settings, environment overrides, and consent."""

import json
from contextlib import nullcontext
from types import SimpleNamespace

import httpx
import pytest
from lfx.services.deps import get_settings_service


@pytest.fixture(autouse=True)
def segment_requests(monkeypatch):
    requests = []
    real_client = httpx.AsyncClient

    def capture(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200)

    # Keep the shared AsyncClient class intact for MCP's import-time annotations.
    monkeypatch.setattr(
        "lfx.services.telemetry.service.httpx",
        SimpleNamespace(AsyncClient=lambda **kwargs: real_client(transport=httpx.MockTransport(capture), **kwargs)),
    )
    return requests


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("edition", "expected"), [("premium", "opensource"), ("", "opensource"), ("enterprise", "enterprise")]
)
@pytest.mark.parametrize("opt_out", [False, True])
async def test_lifespan_resolves_edition_from_fresh_settings(tmp_path, monkeypatch, edition, expected, opt_out) -> None:
    """MCP startup resolves telemetry editions before constructing its transport."""
    from lfx.mcp import server
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LANGFLOW_EDITION", edition)
    monkeypatch.setenv("LANGFLOW_SEGMENT_WRITE_KEY", "test-key")
    monkeypatch.setenv("LANGFLOW_DO_NOT_TRACK", str(opt_out).lower())
    monkeypatch.setenv("DO_NOT_TRACK", str(opt_out).lower())
    monkeypatch.delitem(get_service_manager().services, ServiceType.SETTINGS_SERVICE, raising=False)

    async with server._telemetry_lifespan(server.mcp):
        assert get_settings_service().settings.edition == expected
        assert server._telemetry.edition == expected
        assert server._telemetry.do_not_track is opt_out
        assert server._telemetry._running is not opt_out

    assert server._telemetry is None


@pytest.mark.asyncio
@pytest.mark.parametrize("environment_override", [False, True])
async def test_lifespan_uses_segment_settings(tmp_path, monkeypatch, environment_override) -> None:
    from lfx.mcp import server

    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("LANGFLOW_SEGMENT_API_URL", raising=False)
    monkeypatch.delenv("LANGFLOW_SEGMENT_WRITE_KEY", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "segment_api_url", "https://configured.segment.test/v1/track")
    monkeypatch.setattr(settings, "segment_write_key", "configured-test-key")
    monkeypatch.setattr(settings, "do_not_track", False)
    expected_url = settings.segment_api_url
    expected_key = settings.segment_write_key
    if environment_override:
        expected_url = "https://environment.segment.test/v1/track"
        expected_key = "environment-test-key"
        monkeypatch.setenv("LANGFLOW_SEGMENT_API_URL", expected_url)
        monkeypatch.setenv("LANGFLOW_SEGMENT_WRITE_KEY", expected_key)

    async with server._telemetry_lifespan(server.mcp):
        assert server._telemetry.base_url == expected_url
        assert server._telemetry.write_key == expected_key
        assert server._telemetry._running

    assert server._telemetry is None


@pytest.mark.asyncio
@pytest.mark.parametrize("consent_source", ["settings", "environment"])
async def test_lifespan_respects_both_opt_out_sources(tmp_path, monkeypatch, consent_source) -> None:
    from lfx.mcp import server

    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("LANGFLOW_SEGMENT_WRITE_KEY", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "segment_write_key", "configured-test-key")
    monkeypatch.setattr(settings, "do_not_track", consent_source == "settings")
    if consent_source == "environment":
        monkeypatch.setenv("DO_NOT_TRACK", "true")

    async with server._telemetry_lifespan(server.mcp):
        assert server._telemetry.do_not_track
        assert not server._telemetry._running
        assert server._telemetry.anonymous_id == ""
        assert not (tmp_path / "telemetry_id").exists()

    assert server._telemetry is None


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
@pytest.mark.parametrize("opt_out", [False, True])
async def test_lifespan_delivers_process_events(tmp_path, monkeypatch, segment_requests, fails, opt_out):
    from lfx.mcp import server
    from lfx.services.telemetry import MCPToolPayload

    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("LANGFLOW_SEGMENT_WRITE_KEY", "test-key")
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    monkeypatch.setattr(get_settings_service().settings, "do_not_track", opt_out)
    with pytest.raises(ValueError, match="forced failure") if fails else nullcontext():
        async with server._telemetry_lifespan(server.mcp):
            service = server._telemetry
            await service.log_mcp_tool(MCPToolPayload(tool="list_flows", success=True))
            if fails:
                message = "forced failure"
                raise ValueError(message)

    assert [(event["event"], event["properties"]["object"]) for event in segment_requests] == (
        [("Started Process", "version"), ("Ran Process", "mcp_tool"), ("Ended Process", "shutdown")]
        if not opt_out
        else []
    )
    for event in segment_requests:
        assert event["properties"]["subProductTitle"] == "Langflow MCP"
    if not opt_out:
        assert segment_requests[-1]["properties"]["timeRunning"] >= 0
    assert server._telemetry is None
    assert not service._running
    assert service._client is None
    assert service._queue.empty()
