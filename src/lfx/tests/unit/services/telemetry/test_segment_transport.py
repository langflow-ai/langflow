from unittest.mock import AsyncMock

import pytest
from lfx.services.telemetry.constants import DEFAULT_SEGMENT_WRITE_KEY, get_ibm_common_event
from lfx.services.telemetry.identity import get_hashed_user_id, get_or_create_anonymous_id
from lfx.services.telemetry.schema import BasePayload, ExceptionPayload
from lfx.services.telemetry.service import TelemetryService


@pytest.mark.asyncio
async def test_sends_segment_track_event() -> None:
    service = TelemetryService(base_url="https://api.segment.test/v1/track", write_key="test-key")
    service.anonymous_id = "test-installation"
    service._client = AsyncMock()
    service._client.post.return_value.status_code = 200
    payload = ExceptionPayload(
        exception_type="ValueError",
        exception_message="Test error",
        exception_context="handler",
        stack_trace_hash="abc123",
    )

    await service.send_telemetry_data(payload, "exception")

    service._client.post.assert_awaited_once()
    call = service._client.post.await_args
    assert call.args == ("https://api.segment.test/v1/track",)
    assert call.kwargs["auth"] == ("test-key", "")
    assert call.kwargs["json"]["anonymousId"] == "test-installation"
    assert call.kwargs["json"]["userId"] == get_hashed_user_id("test-installation")
    assert call.kwargs["json"]["event"] == "Ended Process"
    assert call.kwargs["json"]["messageId"]
    assert call.kwargs["json"]["properties"]["exceptionType"] == "ValueError"
    assert call.kwargs["json"]["properties"]["UT30"] == "30AS5"
    assert call.kwargs["json"]["properties"]["productCode"] == "WW3151"
    assert call.kwargs["json"]["properties"]["productCodeType"] == "WWPC"
    assert call.kwargs["json"]["properties"]["productPlanName"] == "opensource"
    assert call.kwargs["json"]["properties"]["productPlanType"] == "freemium"
    assert call.kwargs["json"]["properties"]["productTitle"] == "Langflow"
    assert call.kwargs["json"]["properties"]["instanceId"] == "test-installation"
    assert call.kwargs["json"]["properties"]["subscriptionId"] == "test-installation"
    assert call.kwargs["json"]["properties"]["object"] == "exception"
    assert call.kwargs["json"]["properties"]["processType"] == "Langflow Exception"
    assert "timestamp" in call.kwargs["json"]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (None, ("Started Process", "Langflow", "version")),
        ("run", ("Ran Process", "Langflow Flow", "run")),
        ("shutdown", ("Ended Process", "Langflow", "shutdown")),
        ("email", ("UI Interaction", None, "email")),
        ("mcp_tool", ("Ran Process", "Langflow MCP Tool", "mcp_tool")),
        ("future_event", ("Ran Process", "Langflow Future Event", "future_event")),
    ],
)
def test_maps_langflow_events_to_ibm_common_schema(path, expected) -> None:
    assert get_ibm_common_event(path) == expected


@pytest.mark.asyncio
async def test_adds_ui_interaction_properties() -> None:
    service = TelemetryService(base_url="https://api.segment.test/v1/track", write_key="test-key")
    service.anonymous_id = "test-installation"
    service._client = AsyncMock()
    service._client.post.return_value.status_code = 200

    await service.send_telemetry_data(BasePayload(), "email")

    body = service._client.post.await_args.kwargs["json"]
    assert body["event"] == "UI Interaction"
    assert body["properties"]["object"] == "email"
    assert body["properties"]["action"] == "registered"
    assert body["properties"]["name"] == "Email"
    assert body["properties"]["namespace"] == "Langflow"
    assert "processType" not in body["properties"]


@pytest.mark.asyncio
async def test_does_not_start_send_or_create_identity_when_opted_out(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("LANGFLOW_SEGMENT_WRITE_KEY", raising=False)
    service = TelemetryService(do_not_track=True)
    service._client = AsyncMock()
    payload = ExceptionPayload(
        exception_type="ValueError",
        exception_message="Test error",
        exception_context="handler",
    )

    service.start()
    await service.send_telemetry_data(payload, "exception")

    assert not service._running
    assert service.anonymous_id == ""
    assert not (tmp_path / "telemetry_id").exists()
    service._client.post.assert_not_awaited()


def test_has_no_write_key_in_source_checkout(monkeypatch) -> None:
    monkeypatch.delenv("LANGFLOW_SEGMENT_WRITE_KEY", raising=False)

    assert DEFAULT_SEGMENT_WRITE_KEY == ""
    assert TelemetryService(do_not_track=True).write_key == DEFAULT_SEGMENT_WRITE_KEY


def test_environment_write_key_enables_telemetry(monkeypatch) -> None:
    monkeypatch.setenv("LANGFLOW_SEGMENT_WRITE_KEY", "segment-test-key")

    assert TelemetryService(do_not_track=True).write_key == "segment-test-key"


def test_anonymous_id_persists_in_config_directory(tmp_path) -> None:
    first = get_or_create_anonymous_id(tmp_path)
    second = get_or_create_anonymous_id(tmp_path)

    assert second == first


def test_hashed_user_id_uses_langflow_realm_prefix() -> None:
    assert get_hashed_user_id("alice") == ("lf-2bd806c97f0e00af1a1fc3328fa763a9269723c8db8fac4f93af71db186d6e90")
