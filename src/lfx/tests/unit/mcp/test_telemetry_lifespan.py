"""MCP telemetry honors configured settings, environment overrides, and consent."""

import pytest
from lfx.services.deps import get_settings_service


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
