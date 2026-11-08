"""Unit tests for the TextKit extension bundle (``lfx-textkit``).

The components call the API through ``httpx.AsyncClient``; the tests swap in
``httpx.MockTransport``, so requests are really built and no network is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import httpx
import pytest
from lfx_textkit import (
    TextKitCheckVerificationComponent,
    TextKitListMessagesComponent,
    TextKitSendMessageComponent,
    TextKitSendVerificationComponent,
)

if TYPE_CHECKING:
    from typing_extensions import Self

CLIENT_TARGET = "lfx_textkit.components.textkit.textkit_common.httpx.AsyncClient"
API_KEY = "ssms_sk_test_abc"  # pragma: allowlist secret
RealClient = httpx.AsyncClient


class Api:
    """Answers one request with a canned response and records what it received."""

    def __init__(self, status_code: int = 200, payload: object = None, *, raises: Exception | None = None):
        self.status_code = status_code
        self.payload = {} if payload is None else payload
        self.raises = raises
        self.request: httpx.Request | None = None

    def __enter__(self) -> Self:
        def handler(request: httpx.Request) -> httpx.Response:
            self.request = request
            if self.raises:
                raise self.raises
            return httpx.Response(self.status_code, json=self.payload)

        self.patcher = patch(
            CLIENT_TARGET, lambda **kwargs: RealClient(transport=httpx.MockTransport(handler), **kwargs)
        )
        self.patcher.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.patcher.stop()

    @property
    def body(self) -> dict:
        return json.loads(self.request.content)


def send_component(**overrides) -> TextKitSendMessageComponent:
    fields = {"textkit_api_key": API_KEY, "to_number": "+15551234567", "message_body": "Hello", "from_number": ""}
    return TextKitSendMessageComponent(**(fields | overrides))


def list_component(**overrides) -> TextKitListMessagesComponent:
    fields = {
        "textkit_api_key": API_KEY,
        "phone_number": "",
        "message_direction": "any",
        "message_status": "any",
        "limit": 25,
    }
    return TextKitListMessagesComponent(**(fields | overrides))


async def test_send_posts_body_field_with_bearer_key():
    message = {"id": "msg_1", "status": "queued", "to": "+15551234567"}
    with Api(201, message) as api:
        result = await send_component().textkit_send_text()

    assert api.request.method == "POST"
    assert str(api.request.url) == "https://api.jointextkit.com/v1/messages"
    assert api.request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert api.body == {"to": "+15551234567", "body": "Hello"}
    assert result.data["id"] == "msg_1"
    assert result.text == "Message msg_1 is queued."


async def test_send_includes_from_when_set():
    with Api(201, {"id": "msg_1"}) as api:
        await send_component(from_number=" +15550001111 ").textkit_send_text()

    assert api.body["from"] == "+15550001111"


async def test_send_surfaces_the_api_error_message():
    error = {"error": {"code": "recipient_opted_out", "message": "This number opted out."}}
    with Api(403, error):
        result = await send_component().textkit_send_text()

    assert result.data["error"] == "TextKit API error 403: This number opted out."


async def test_missing_key_never_calls_the_api():
    with Api() as api:
        result = await send_component(textkit_api_key="").textkit_send_text()

    assert api.request is None
    assert "API key is required" in result.data["error"]


async def test_network_failure_becomes_an_error_row():
    with Api(raises=httpx.ConnectError("boom")):
        result = await send_component().textkit_send_text()

    assert result.data["error"] == "Could not reach TextKit: boom"


async def test_non_json_success_becomes_an_error_row():
    with patch(
        CLIENT_TARGET,
        lambda **kwargs: RealClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>")), **kwargs
        ),
    ):
        result = await send_component().textkit_send_text()

    assert "unexpected response" in result.data["error"]


async def test_list_sends_only_the_filters_that_are_set():
    with Api(200, {"data": [], "has_more": False, "next_cursor": None}) as api:
        await list_component(phone_number="+15551234567", message_direction="inbound").textkit_list_messages()

    assert api.request.method == "GET"
    assert dict(api.request.url.params) == {"limit": "25", "number": "+15551234567", "direction": "inbound"}


@pytest.mark.parametrize(("requested", "sent"), [(0, "1"), (500, "100"), (None, "25")])
async def test_list_clamps_limit(requested, sent):
    with Api(200, {"data": []}) as api:
        await list_component(limit=requested).textkit_list_messages()

    assert api.request.url.params["limit"] == sent


async def test_list_returns_message_columns():
    row = {
        "id": "msg_1",
        "to": "+15551234567",
        "from": "+15550001111",
        "body": "Hi",
        "direction": "outbound",
        "status": "delivered",
        "created_at": "2026-10-30T00:00:00Z",
        "price": 1,
    }
    with Api(200, {"data": [row]}):
        frame = await list_component().textkit_list_messages()

    assert frame.iloc[0]["id"] == "msg_1"
    assert frame.iloc[0]["from"] == "+15550001111"
    assert "price" not in frame.columns


async def test_list_surfaces_errors_as_a_row():
    with Api(401, {"error": {"code": "invalid_api_key", "message": "Invalid API key."}}):
        frame = await list_component().textkit_list_messages()

    assert frame.iloc[0]["error"] == "TextKit API error 401: Invalid API key."


async def test_send_verification_posts_phone():
    with Api(201, {"id": "ver_1", "status": "pending"}) as api:
        component = TextKitSendVerificationComponent(
            textkit_api_key=API_KEY, phone_number="+15551234567", app_name="Acme"
        )
        result = await component.textkit_send_verification()

    assert str(api.request.url) == "https://api.jointextkit.com/v1/verify"
    assert api.body == {"channel": "sms", "phone": "+15551234567", "app_name": "Acme"}
    assert result.data["id"] == "ver_1"


@pytest.mark.parametrize(("verified", "text"), [(True, "Verified."), (False, "Not verified.")])
async def test_check_verification_reports_the_result(verified, text):
    with Api(200, {"verified": verified, "status": "approved"}) as api:
        component = TextKitCheckVerificationComponent(
            textkit_api_key=API_KEY, phone_number="+15551234567", verification_code=" 123456 "
        )
        result = await component.textkit_check_verification()

    assert str(api.request.url) == "https://api.jointextkit.com/v1/verify/check"
    assert api.body == {"phone": "+15551234567", "code": "123456"}
    assert result.data["verified"] is verified
    assert result.text == text


def test_manifest_points_at_the_components():
    manifest = json.loads((Path(__file__).parents[1] / "src/lfx_textkit/extension.json").read_text(encoding="utf-8"))
    assert manifest["id"] == "lfx-textkit"
    assert manifest["bundles"] == [{"name": "textkit", "path": "components/textkit"}]


@pytest.mark.parametrize(
    ("component", "tool"),
    [
        (TextKitSendMessageComponent, "textkit_send_text"),
        (TextKitListMessagesComponent, "textkit_list_messages"),
        (TextKitSendVerificationComponent, "textkit_send_verification"),
        (TextKitCheckVerificationComponent, "textkit_check_verification"),
    ],
)
def test_tool_names_stay_stable(component, tool):
    assert component.outputs[0].method == tool
