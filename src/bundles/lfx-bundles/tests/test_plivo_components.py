"""Contract tests for the Plivo REST API components."""

import json
from collections.abc import Callable
from types import ModuleType
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

pytest.importorskip("lfx_bundles")

from lfx_bundles.plivo import PlivoLookupNumberComponent, PlivoMakeCallComponent, PlivoSendSMSComponent
from lfx_bundles.plivo import lookup_number as lookup_number_module
from lfx_bundles.plivo import make_call as make_call_module
from lfx_bundles.plivo import send_sms as send_sms_module

AUTH_ID = "test-auth-id"
AUTH_TOKEN = "test-auth-token"  # noqa: S105  # pragma: allowlist secret


def _logged_values(mock_log: AsyncMock) -> str:
    return " ".join(str(value) for call in mock_log.await_args_list for value in (*call.args, *call.kwargs.values()))


@respx.mock
async def test_send_sms_posts_expected_payload_without_logging_message_content() -> None:
    response_payload = {"message": "message(s) queued", "message_uuid": ["message-id"]}
    route = respx.post(f"https://api.plivo.com/v1/Account/{AUTH_ID}/Message/").mock(
        return_value=httpx.Response(202, json=response_payload)
    )
    component = PlivoSendSMSComponent(
        auth_id=f" {AUTH_ID} ",
        auth_token=f" {AUTH_TOKEN} ",
        src=" +14155550100 ",
        dst=" +14155550101 ",
        text="private message body",
    )

    with patch.object(send_sms_module.logger, "ainfo", new_callable=AsyncMock) as mock_log:
        result = await component.build_output()

    assert result.data["value"] == response_payload
    assert component.status == response_payload
    assert json.loads(route.calls[0].request.content) == {
        "src": "+14155550100",
        "dst": "+14155550101",
        "text": "private message body",
        "type": "sms",
    }
    assert "private message body" not in _logged_values(mock_log)
    assert "+14155550100" not in _logged_values(mock_log)
    assert "+14155550101" not in _logged_values(mock_log)


@respx.mock
async def test_make_call_posts_expected_payload_without_logging_phone_numbers() -> None:
    response_payload = {"message": "call fired", "request_uuid": "request-id"}
    route = respx.post(f"https://api.plivo.com/v1/Account/{AUTH_ID}/Call/").mock(
        return_value=httpx.Response(201, json=response_payload)
    )
    component = PlivoMakeCallComponent(
        auth_id=AUTH_ID,
        auth_token=AUTH_TOKEN,
        from_number=" +14155550100 ",
        to_number=" +14155550101 ",
        answer_url=" https://example.com/answer ",
        answer_method="post",
    )

    with patch.object(make_call_module.logger, "ainfo", new_callable=AsyncMock) as mock_log:
        result = await component.build_output()

    assert result.data["value"] == response_payload
    assert component.status == response_payload
    assert json.loads(route.calls[0].request.content) == {
        "from": "+14155550100",
        "to": "+14155550101",
        "answer_url": "https://example.com/answer",
        "answer_method": "POST",
    }
    assert "+14155550100" not in _logged_values(mock_log)
    assert "+14155550101" not in _logged_values(mock_log)


@respx.mock
@pytest.mark.parametrize(
    ("lookup_type", "expected_query"),
    [("carrier", b"type=carrier"), ("none", b"")],
)
async def test_lookup_number_sends_supported_query_without_logging_number(
    lookup_type: str, expected_query: bytes
) -> None:
    response_payload = {"phone_number": "+14155550101", "carrier": {"name": "Example"}}
    route = respx.get("https://lookup.plivo.com/v1/Number/+14155550101").mock(
        return_value=httpx.Response(200, json=response_payload)
    )
    component = PlivoLookupNumberComponent(
        auth_id=AUTH_ID,
        auth_token=AUTH_TOKEN,
        number=" +14155550101 ",
        type=lookup_type,
    )

    with patch.object(lookup_number_module.logger, "ainfo", new_callable=AsyncMock) as mock_log:
        result = await component.build_output()

    assert result.data["value"] == response_payload
    assert component.status == response_payload
    assert route.calls[0].request.url.query == expected_query
    assert "+14155550101" not in _logged_values(mock_log)


def test_plivo_component_metadata_matches_provider_contract() -> None:
    answer_url_input = next(input_ for input_ in PlivoMakeCallComponent.inputs if input_.name == "answer_url")
    sender_input = next(input_ for input_ in PlivoSendSMSComponent.inputs if input_.name == "src")

    assert answer_url_input.required is True
    assert PlivoMakeCallComponent.documentation.endswith("/voice/api/calls")
    assert PlivoLookupNumberComponent.documentation.endswith("/lookup/overview")
    assert "phone number in E.164 format, a short code, or an alphanumeric sender ID" in sender_input.info


@pytest.mark.parametrize(
    ("component_factory", "module", "method", "url"),
    [
        pytest.param(
            lambda: PlivoSendSMSComponent(
                auth_id=AUTH_ID,
                auth_token=AUTH_TOKEN,
                src="+14155550100",
                dst="+14155550101",
                text="hello",
            ),
            send_sms_module,
            "post",
            f"https://api.plivo.com/v1/Account/{AUTH_ID}/Message/",
            id="send-sms",
        ),
        pytest.param(
            lambda: PlivoMakeCallComponent(
                auth_id=AUTH_ID,
                auth_token=AUTH_TOKEN,
                from_number="+14155550100",
                to_number="+14155550101",
                answer_url="https://example.com/answer",
                answer_method="GET",
            ),
            make_call_module,
            "post",
            f"https://api.plivo.com/v1/Account/{AUTH_ID}/Call/",
            id="make-call",
        ),
        pytest.param(
            lambda: PlivoLookupNumberComponent(
                auth_id=AUTH_ID,
                auth_token=AUTH_TOKEN,
                number="+14155550101",
                type="carrier",
            ),
            lookup_number_module,
            "get",
            "https://lookup.plivo.com/v1/Number/+14155550101",
            id="lookup-number",
        ),
    ],
)
@pytest.mark.parametrize("failure", ["http-status", "request", "invalid-json"])
async def test_plivo_failures_are_returned_as_data(
    component_factory: Callable[[], object],
    module: ModuleType,
    method: str,
    url: str,
    failure: str,
) -> None:
    component = component_factory()

    with respx.mock:
        route = getattr(respx, method)(url)
        if failure == "http-status":
            route.mock(return_value=httpx.Response(400, text="invalid request"))
            expected = "HTTP error occurred"
        elif failure == "request":
            route.mock(side_effect=httpx.ConnectError("connection failed"))
            expected = "Request failed"
        else:
            route.mock(return_value=httpx.Response(200, text="not-json"))
            expected = "Response parsing failed"

        with patch.object(module.logger, "aexception", new_callable=AsyncMock):
            result = await component.build_output()

    assert expected in result.data["value"]["error"]
    assert component.status == result.data["value"]
