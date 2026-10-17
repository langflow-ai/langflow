"""LFX product telemetry excludes free-form errors at the HTTP boundary."""

import json
from uuid import uuid4

import httpx
import pytest
from lfx.services.telemetry.identity import get_installation_user_id, is_installation_user_id
from lfx.services.telemetry.privacy import get_safe_payload_properties
from lfx.services.telemetry.schema import ComponentPayload, ExceptionPayload, MCPToolPayload, RunPayload
from lfx.services.telemetry.service import TelemetryService
from pydantic import BaseModel, Field

ERROR_TEXT = "synthetic-private-input; SQL parameters: synthetic@example.test"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "path", "safe_fields"),
    [
        (
            ExceptionPayload(
                exception_type="ValueError",
                exception_message=ERROR_TEXT,
                exception_context="handler",
                stack_trace_hash="abc123",
            ),
            "exception",
            {"exceptionType": "ValueError", "stackTraceHash": "abc123"},
        ),
        (RunPayload(run_seconds=2, run_success=False, run_error_message=ERROR_TEXT), "run", {"runSuccess": False}),
        (
            ComponentPayload(
                component_name="Test", component_seconds=2, component_success=False, component_error_message=ERROR_TEXT
            ),
            "component",
            {"componentSuccess": False},
        ),
        (
            MCPToolPayload(tool="run_flow", success=False, ms=2, error=ERROR_TEXT),
            "mcp_tool",
            {"success": False, "ms": 2},
        ),
    ],
)
async def test_outbound_errors_are_removed(tmp_path, monkeypatch, payload, path, safe_fields):
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))
    service = TelemetryService(
        base_url="https://segment.example.test/v1/track", write_key="test-key", do_not_track=False
    )
    requests = []

    def capture(request):
        requests.append(request)
        return httpx.Response(200)

    before = payload.model_dump()
    async with httpx.AsyncClient(transport=httpx.MockTransport(capture)) as client:
        service._client = client
        await service.send_telemetry_data(payload, path)

    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert ERROR_TEXT not in requests[0].content.decode()
    assert not any(key.endswith("ErrorMessage") or key in {"exceptionMessage", "error"} for key in body["properties"])
    for key, value in safe_fields.items():
        assert body["properties"][key] == value
    assert body["properties"]["productTitle"] == "Langflow"
    assert payload.model_dump() == before


def test_new_error_fields_are_excluded_but_safe_codes_remain():
    class FuturePayload(BaseModel):
        error_message: str = Field(serialization_alias="errorMessage")
        future_error_message: str = Field(serialization_alias="futureErrorMessage")
        error_code: str = Field(serialization_alias="errorCode")
        success: bool

    payload = FuturePayload(
        error_message=ERROR_TEXT, future_error_message=ERROR_TEXT, error_code="timeout", success=False
    )
    assert get_safe_payload_properties(payload) == {"errorCode": "timeout", "success": False}
    assert payload.error_message == ERROR_TEXT


def test_current_user_identity_is_stable_within_an_installation():
    user_id = uuid4()
    installation_id = str(uuid4())
    first = get_installation_user_id(user_id, installation_id)
    assert is_installation_user_id(first)
    assert first == get_installation_user_id(user_id, installation_id)
    assert first != get_installation_user_id(user_id, str(uuid4()))
    assert first != get_installation_user_id(uuid4(), installation_id)


@pytest.mark.parametrize("user_id", [None, 42, "lf-old-hash", "lf-user-short", "lf-user-" + "z" * 64])
def test_legacy_and_malformed_user_ids_are_rejected(user_id):
    assert not is_installation_user_id(user_id)
