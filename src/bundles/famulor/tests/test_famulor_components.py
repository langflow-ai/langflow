"""Unit tests for the Famulor extension bundle (``lfx-famulor``).

The components call the public Famulor API with ``httpx``. Tests patch
``httpx.request`` on the client module and return real ``httpx.Response``
objects, so no network access and no live API key are required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_famulor import (
    FamulorGetCallComponent,
    FamulorListAssistantsComponent,
    FamulorListCampaignsComponent,
    FamulorMakeCallComponent,
)

REQUEST_PATCH = "lfx_famulor.components.famulor._client.httpx.request"
API_ROOT = "https://app.famulor.io/api/v1"
ASSISTANT_ID = "11111111-1111-1111-1111-111111111111"
CALL_ID = "22222222-2222-2222-2222-222222222222"
CALLER_ID = "33333333-3333-3333-3333-333333333333"
# Test fixture only. Not a live credential.
TEST_KEY = "fam_test_key"  # pragma: allowlist secret


def _response(method: str, path: str, status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request(method, f"{API_ROOT}{path}"), **kwargs)


def _mock_request(method: str, path: str, payload: object, status_code: int = 200) -> MagicMock:
    return MagicMock(return_value=_response(method, path, status_code, json=payload))


@pytest.fixture
def make_call() -> FamulorMakeCallComponent:
    component = FamulorMakeCallComponent()
    component.famulor_api_key = TEST_KEY
    component.assistant_id = ASSISTANT_ID
    component.phone_number = "+4930123456"
    component.call_variables = {}
    component.phone_number_id = ""
    return component


@pytest.fixture
def get_call() -> FamulorGetCallComponent:
    component = FamulorGetCallComponent()
    component.famulor_api_key = TEST_KEY
    component.call_id = CALL_ID
    return component


@pytest.fixture
def list_assistants() -> FamulorListAssistantsComponent:
    component = FamulorListAssistantsComponent()
    component.famulor_api_key = TEST_KEY
    component.limit = 50
    component.offset = 0
    return component


@pytest.fixture
def list_campaigns() -> FamulorListCampaignsComponent:
    component = FamulorListCampaignsComponent()
    component.famulor_api_key = TEST_KEY
    component.campaign_status = "all"
    component.limit = 50
    component.offset = 0
    return component


def test_component_class_names_stay_stable():
    """Class names are saved-flow identifiers and must not be renamed."""
    assert FamulorMakeCallComponent.__name__ == "FamulorMakeCallComponent"
    assert FamulorGetCallComponent.__name__ == "FamulorGetCallComponent"
    assert FamulorListAssistantsComponent.__name__ == "FamulorListAssistantsComponent"
    assert FamulorListCampaignsComponent.__name__ == "FamulorListCampaignsComponent"


def test_make_call_requires_api_key(make_call):
    """A missing key becomes an error row and never calls the API."""
    make_call.famulor_api_key = ""
    mock_request = _mock_request("POST", "/calls", {"data": {}})
    with patch(REQUEST_PATCH, mock_request):
        result = make_call.famulor_make_call()
    mock_request.assert_not_called()
    assert "Famulor API key is required" in result.data["error"]


def test_make_call_posts_bearer_token_and_body(make_call):
    """POST /calls sends the key as a Bearer token and the documented body."""
    payload = {"data": {"id": CALL_ID, "status": "queued", "direction": "outbound"}}
    mock_request = _mock_request("POST", "/calls", payload, status_code=201)
    with patch(REQUEST_PATCH, mock_request):
        result = make_call.famulor_make_call()
    assert mock_request.call_args.args[0] == "POST"
    assert mock_request.call_args.args[1] == f"{API_ROOT}/calls"
    headers = mock_request.call_args.kwargs["headers"]
    assert headers["Authorization"] == f"Bearer {TEST_KEY}"
    assert headers["User-Agent"] == "langflow-famulor-bundle"
    assert mock_request.call_args.kwargs["json"] == {
        "assistant_id": ASSISTANT_ID,
        "to_number": "+4930123456",
    }
    assert result.data["id"] == CALL_ID
    assert result.text == f"Call {CALL_ID} is queued."


def test_make_call_sends_variables_and_caller_id(make_call):
    """Optional variables and caller ID are included only when set."""
    make_call.call_variables = {"customer_name": "Ada", "attempts": 2, "vip": True}
    make_call.phone_number_id = f"  {CALLER_ID}  "
    payload = {"data": {"id": CALL_ID, "status": "queued"}}
    mock_request = _mock_request("POST", "/calls", payload, status_code=201)
    with patch(REQUEST_PATCH, mock_request):
        make_call.famulor_make_call()
    assert mock_request.call_args.kwargs["json"] == {
        "assistant_id": ASSISTANT_ID,
        "to_number": "+4930123456",
        "variables": {"customer_name": "Ada", "attempts": 2, "vip": True},
        "phone_number_id": CALLER_ID,
    }


def test_make_call_parses_variable_json_string(make_call):
    """A JSON object string is accepted the same way the dict input is."""
    make_call.call_variables = '{"customer_name": "Ada"}'
    payload = {"data": {"id": CALL_ID, "status": "queued"}}
    mock_request = _mock_request("POST", "/calls", payload, status_code=201)
    with patch(REQUEST_PATCH, mock_request):
        make_call.famulor_make_call()
    assert mock_request.call_args.kwargs["json"]["variables"] == {"customer_name": "Ada"}


def test_make_call_rejects_bad_phone_without_request(make_call):
    """A non-E.164 number is reported locally."""
    make_call.phone_number = "030123456"
    mock_request = _mock_request("POST", "/calls", {"data": {}})
    with patch(REQUEST_PATCH, mock_request):
        result = make_call.famulor_make_call()
    mock_request.assert_not_called()
    assert "E.164" in result.data["error"]


def test_make_call_rejects_nested_variables(make_call):
    """Nested variable values are rejected before the request."""
    make_call.call_variables = {"lead": {"name": "Ada"}}
    mock_request = _mock_request("POST", "/calls", {"data": {}})
    with patch(REQUEST_PATCH, mock_request):
        result = make_call.famulor_make_call()
    mock_request.assert_not_called()
    assert "string, number, or boolean" in result.data["error"]


def test_make_call_rejects_non_uuid_assistant(make_call):
    """Assistant ID must be a UUID."""
    make_call.assistant_id = "42"
    mock_request = _mock_request("POST", "/calls", {"data": {}})
    with patch(REQUEST_PATCH, mock_request):
        result = make_call.famulor_make_call()
    mock_request.assert_not_called()
    assert "Assistant ID must be a UUID" in result.data["error"]


def test_make_call_surfaces_api_error(make_call):
    """A 403 keeps the API error code and message."""
    body = {"error": {"code": "destination_forbidden", "message": "This destination is not allowed."}}
    mock_request = MagicMock(return_value=_response("POST", "/calls", 403, json=body))
    with patch(REQUEST_PATCH, mock_request):
        result = make_call.famulor_make_call()
    assert result.data["error"] == "Famulor API error 403 (destination_forbidden): This destination is not allowed."


def test_make_call_http_error_without_json(make_call):
    """A non-JSON error body falls back to the HTTP reason phrase."""
    mock_request = MagicMock(return_value=_response("POST", "/calls", 502, text="upstream down"))
    with patch(REQUEST_PATCH, mock_request):
        result = make_call.famulor_make_call()
    assert result.data["error"] == "Famulor API error 502: Bad Gateway"


def test_make_call_wraps_transport_error(make_call):
    """A transport error is a single error Data row."""
    mock_request = MagicMock(side_effect=httpx.HTTPError("boom"))
    with patch(REQUEST_PATCH, mock_request):
        result = make_call.famulor_make_call()
    assert "boom" in result.data["error"]


def test_make_call_rejects_non_object_payload(make_call):
    """A JSON body that is not an object becomes an error row."""
    mock_request = _mock_request("POST", "/calls", ["unexpected"], status_code=201)
    with patch(REQUEST_PATCH, mock_request):
        result = make_call.famulor_make_call()
    assert "expected a JSON object" in result.data["error"]


def test_make_call_message_uses_status_text(make_call):
    """The message output repeats the call status without a second request shape."""
    payload = {"data": {"id": CALL_ID, "status": "queued"}}
    mock_request = _mock_request("POST", "/calls", payload, status_code=201)
    with patch(REQUEST_PATCH, mock_request):
        message = make_call.famulor_make_call_message()
    assert message.text == f"Call {CALL_ID} is queued."
    assert message.error is False


def test_get_call_reads_summary_and_transcript(get_call):
    """GET /calls/{id} maps status, summary, and spoken transcript lines."""
    payload = {
        "data": {
            "id": CALL_ID,
            "status": "completed",
            "summary": "Booked a follow-up.",
            "transcript": {
                "items": [
                    {"type": "message", "role": "assistant", "content": [{"text": "Hello from Famulor."}]},
                    {"type": "message", "role": "user", "content": "Hi."},
                    {"type": "function_call", "name": "lookup", "arguments": "{}"},
                ]
            },
        }
    }
    mock_request = _mock_request("GET", f"/calls/{CALL_ID}", payload)
    with patch(REQUEST_PATCH, mock_request):
        result = get_call.famulor_get_call()
    assert mock_request.call_args.args == ("GET", f"{API_ROOT}/calls/{CALL_ID}")
    assert result.data["status"] == "completed"
    assert "Booked a follow-up." in result.text
    assert "assistant: Hello from Famulor." in result.text
    assert "user: Hi." in result.text
    assert "lookup" not in result.text


def test_get_call_includes_failure_guidance(get_call):
    """A failed call keeps the provider-neutral failure message."""
    payload = {
        "data": {
            "id": CALL_ID,
            "status": "failed",
            "failure": {"code": "no_answer", "message": "The destination did not answer."},
            "summary": None,
            "transcript": None,
        }
    }
    mock_request = _mock_request("GET", f"/calls/{CALL_ID}", payload)
    with patch(REQUEST_PATCH, mock_request):
        result = get_call.famulor_get_call()
    assert "The destination did not answer." in result.text


def test_get_call_surfaces_not_found(get_call):
    """A 404 keeps the API's not_found message."""
    body = {"error": {"code": "not_found", "message": "Call not found."}}
    mock_request = MagicMock(return_value=_response("GET", f"/calls/{CALL_ID}", 404, json=body))
    with patch(REQUEST_PATCH, mock_request):
        result = get_call.famulor_get_call()
    assert result.data["error"] == "Famulor API error 404 (not_found): Call not found."
    with patch(REQUEST_PATCH, mock_request):
        message = get_call.famulor_get_call_message()
    assert message.error is True
    assert "Call not found." in message.text


def test_list_assistants_maps_page(list_assistants):
    """GET /assistants sends pagination and keeps the identity fields plus total."""
    payload = {
        "data": [
            {
                "id": ASSISTANT_ID,
                "name": "Support",
                "mode": "pipeline",
                "is_active": True,
                "stt_language": "de",
                "greeting_mode": "agent_speaks_first",
                "updated_at": "2026-01-15T10:00:00Z",
                "system_prompt": "ignore this long prompt",
            },
            "not-an-object",
        ],
        "meta": {"pagination": {"limit": 50, "offset": 0, "total": 4}},
    }
    mock_request = _mock_request("GET", "/assistants", payload)
    with patch(REQUEST_PATCH, mock_request):
        result = list_assistants.famulor_list_assistants()
    assert mock_request.call_args.kwargs["params"] == {"limit": 50, "offset": 0}
    assert result.data["total"] == 4
    assert result.data["items"] == [
        {
            "id": ASSISTANT_ID,
            "name": "Support",
            "mode": "pipeline",
            "is_active": True,
            "stt_language": "de",
            "greeting_mode": "agent_speaks_first",
            "updated_at": "2026-01-15T10:00:00Z",
        }
    ]
    assert "system_prompt" not in result.data["items"][0]
    assert result.text == "Showing 1 assistants (total 4)."


def test_list_assistants_clamps_page_size(list_assistants):
    """Limit above 200 is clamped to the API maximum."""
    list_assistants.limit = 500
    list_assistants.offset = -3
    mock_request = _mock_request("GET", "/assistants", {"data": [], "meta": {"pagination": {"total": 0}}})
    with patch(REQUEST_PATCH, mock_request):
        list_assistants.famulor_list_assistants()
    assert mock_request.call_args.kwargs["params"] == {"limit": 200, "offset": 0}


def test_list_assistants_table_shape(list_assistants):
    """The table output has one row per assistant."""
    payload = {
        "data": [{"id": ASSISTANT_ID, "name": "Support", "mode": "pipeline", "is_active": True}],
        "meta": {"pagination": {"total": 1}},
    }
    mock_request = _mock_request("GET", "/assistants", payload)
    with patch(REQUEST_PATCH, mock_request):
        frame = list_assistants.famulor_list_assistants_table()
    assert len(frame) == 1
    assert frame.iloc[0]["name"] == "Support"


def test_list_campaigns_omits_status_when_all(list_campaigns):
    """The default All filter does not send a status query parameter."""
    payload = {
        "data": [
            {
                "id": CALL_ID,
                "name": "Q1",
                "status": "running",
                "channel": "phone_call",
                "assistant_id": ASSISTANT_ID,
                "timezone": "Europe/Berlin",
                "updated_at": "2026-01-15T10:00:00Z",
                "calling_windows": {"mon": [["09:00", "18:00"]]},
            }
        ],
        "meta": {"pagination": {"total": 1}},
    }
    mock_request = _mock_request("GET", "/campaigns", payload)
    with patch(REQUEST_PATCH, mock_request):
        result = list_campaigns.famulor_list_campaigns()
    assert mock_request.call_args.kwargs["params"] == {"limit": 50, "offset": 0}
    assert result.data["items"][0]["name"] == "Q1"
    assert "calling_windows" not in result.data["items"][0]


def test_list_campaigns_sends_status_filter(list_campaigns):
    """A selected status is sent as the status query parameter."""
    list_campaigns.campaign_status = "paused"
    mock_request = _mock_request("GET", "/campaigns", {"data": [], "meta": {"pagination": {"total": 0}}})
    with patch(REQUEST_PATCH, mock_request):
        list_campaigns.famulor_list_campaigns()
    assert mock_request.call_args.kwargs["params"]["status"] == "paused"


def test_list_campaigns_rejects_unknown_status(list_campaigns):
    """An unknown status is rejected before the request."""
    list_campaigns.campaign_status = "deleted"
    mock_request = _mock_request("GET", "/campaigns", {"data": []})
    with patch(REQUEST_PATCH, mock_request):
        result = list_campaigns.famulor_list_campaigns()
    mock_request.assert_not_called()
    assert "Status must be one of" in result.data["error"]


def test_limit_range_matches_api_bounds():
    """The UI range matches the page size the request clamps to."""
    limit = next(item for item in FamulorListAssistantsComponent.inputs if item.name == "limit")
    assert limit.range_spec is not None
    assert (limit.range_spec.min, limit.range_spec.max) == (1, 200)


def test_tool_mode_names_are_component_specific():
    """Each component exposes one tool, named after its primary method."""
    cases = [
        (FamulorMakeCallComponent(famulor_api_key=TEST_KEY), "famulor_make_call"),
        (FamulorGetCallComponent(famulor_api_key=TEST_KEY), "famulor_get_call"),
        (FamulorListAssistantsComponent(famulor_api_key=TEST_KEY, limit=50, offset=0), "famulor_list_assistants"),
        (
            FamulorListCampaignsComponent(famulor_api_key=TEST_KEY, campaign_status="all", limit=50, offset=0),
            "famulor_list_campaigns",
        ),
    ]
    for component, tool_name in cases:
        tools = asyncio.run(component.to_toolkit())
        assert [tool.name for tool in tools] == [tool_name]


def test_make_call_tool_invokes_with_tool_arguments():
    """The agent tool sends assistant_id, phone_number, and variables."""
    component = FamulorMakeCallComponent(famulor_api_key=TEST_KEY)
    tools = asyncio.run(component.to_toolkit())
    payload = {"data": {"id": CALL_ID, "status": "queued"}}
    mock_request = _mock_request("POST", "/calls", payload, status_code=201)
    with patch(REQUEST_PATCH, mock_request):
        output = asyncio.run(
            tools[0].ainvoke(
                {
                    "assistant_id": ASSISTANT_ID,
                    "phone_number": "+4930123456",
                    "call_variables": {"customer_name": "Ada"},
                    "phone_number_id": "",
                }
            )
        )
    assert mock_request.call_args.kwargs["json"]["to_number"] == "+4930123456"
    assert mock_request.call_args.kwargs["json"]["variables"] == {"customer_name": "Ada"}
    assert CALL_ID in str(output)
