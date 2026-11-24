"""Send safety for the two Firma send components, with mocked HTTP calls.

The cases follow Firma's create-and-send contract (API 01.45.00):

- The edge forwarder answers any proxy failure, including one after the request was created, with
  502 ``{"error": "Proxy error", "code": "PROXY_ERROR"}``; gateways answer 504 or 546 without a Firma body.
  Firma's own 500 can follow a failed rollback. None of these proves that nothing was created.
- A 409 ``ALREADY_SENT`` / ``SEND_EFFECTS_EXIST`` carries ``signing_request_id`` when the request was kept;
  ``SEND_IN_PROGRESS`` leaves the request in place.
- Create-and-send needs a recipient for every template user (matched by ``template_user_id``, then ``id``,
  then ``order``) and keeps each user's designation and order.
"""

from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx_bundles.firma.firma_common import API_BASE_URL
from lfx_bundles.firma.firma_send_document import FirmaSendDocumentComponent
from lfx_bundles.firma.firma_send_template import FirmaSendTemplateComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-firma-api-key-placeholder"  # pragma: allowlist secret
TEMPLATE_ID = "a12a33db-4d52-41ad-a66b-b45f6dc2830a"
REQUEST_ID = "5b0c8a52-3f0e-4f43-9d0e-7c1f2b3a4d5e"
SEND_URL = f"{API_BASE_URL}/signing-requests/create-and-send"
MAY_HAVE_BEEN_SENT = "may have been sent"
CHECK_DASHBOARD = "Check the signing requests in the Firma dashboard before sending again"

SEND_RESPONSE = {
    "id": REQUEST_ID,
    "name": "Offer letter",
    "status": "sent",
    "first_signer": {
        "id": "u-1",
        "name": "Ada Lovelace",
        "email": "ada@firma.dev",
        "signing_link": "https://app.firma.dev/signing/u-1",
    },
}


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _user(user_id: str, order: int, designation: str = "Signer") -> dict[str, Any]:
    return {"id": user_id, "name": None, "email": None, "designation": designation, "order": order}


def _template(*users: dict[str, Any], name: str = "Offer") -> httpx.Response:
    return _response(json_body={"id": TEMPLATE_ID, "name": name, "recipients": list(users)})


ONE_SIGNER = (_user("tu-1", 1),)


def _send_template(responses: list[Any], **values) -> tuple[Any, Any]:
    component = FirmaSendTemplateComponent()
    component.set(
        api_key=API_KEY,
        template_id=TEMPLATE_ID,
        request_name="Offer letter",
        **({"signer_first_name": "Ada", "signer_email": "ada@firma.dev"} if "recipients_json" not in values else {}),
        **values,
    )
    with patch("httpx.Client.request", side_effect=responses) as request:
        data = component.send_request()
    return data, request


def _send_document(responses: list[Any]) -> tuple[Any, Any]:
    component = FirmaSendDocumentComponent()
    component.set(
        api_key=API_KEY,
        request_name="NDA",
        signer_first_name="Ada",
        signer_email="ada@firma.dev",
        document_base64=base64.b64encode(b"%PDF-1.4\n%%EOF\n").decode(),
    )
    with patch("httpx.Client.request", side_effect=responses) as request:
        data = component.send_document()
    return data, request


def _send_calls(request) -> list[Any]:
    return [call for call in request.call_args_list if call.args[:2] == ("POST", SEND_URL)]


UNKNOWN_FAILURES = [
    pytest.param(_response(502, json_body={"error": "Proxy error", "code": "PROXY_ERROR"}), id="502-proxy-error"),
    pytest.param(_response(504, text=""), id="504-no-body"),
    pytest.param(_response(502, text="<html>Bad gateway</html>"), id="502-html"),
    pytest.param(_response(546, json_body={"code": "WORKER_LIMIT", "message": "Worker limit"}), id="546-gateway"),
    pytest.param(
        _response(500, json_body={"error": "An unexpected error occurred.", "code": "INTERNAL"}), id="500-firma"
    ),
    pytest.param(_response(500, text=""), id="500-no-body"),
    pytest.param(_response(503, json_body={"code": "BOOT_ERROR", "message": "boot"}), id="503-gateway"),
    pytest.param(_response(503, json_body={"error": "Down", "code": "SERVICE_UNAVAILABLE"}), id="503-other-code"),
    pytest.param(httpx.ReadTimeout("read timed out"), id="timeout"),
    pytest.param(httpx.RemoteProtocolError("server disconnected"), id="network-error"),
    pytest.param(_response(201, text="<html>ok</html>"), id="201-not-json"),
    pytest.param(_response(201, json_body=["x"]), id="201-not-an-object"),
    pytest.param(_response(201, json_body={"name": "x"}), id="201-no-id"),
]


@pytest.mark.unit
class TestUnknownOutcome:
    @pytest.mark.parametrize("reply", UNKNOWN_FAILURES)
    def test_template_send_says_the_document_may_have_been_sent(self, reply: Any) -> None:
        data, request = _send_template([_template(*ONE_SIGNER), reply])

        error = data.data["error"]
        assert MAY_HAVE_BEEN_SENT in error
        assert CHECK_DASHBOARD in error
        assert data.data["may_have_been_sent"] is True
        assert len(_send_calls(request)) == 1

    @pytest.mark.parametrize("reply", UNKNOWN_FAILURES)
    def test_document_send_says_the_document_may_have_been_sent(self, reply: Any) -> None:
        data, request = _send_document([reply])

        assert MAY_HAVE_BEEN_SENT in data.data["error"]
        assert CHECK_DASHBOARD in data.data["error"]
        assert len(_send_calls(request)) == 1

    @pytest.mark.parametrize(
        ("status", "body"),
        [
            (400, {"error": "Bad", "code": "VALIDATION_ERROR"}),
            (402, {"error": "Insufficient credits", "code": "INSUFFICIENT_CREDITS"}),
            (404, {"error": "Template not found", "code": "NOT_FOUND"}),
            (409, {"error": "Conflict", "code": "CONFLICT"}),
            (409, {"error": "Already sent", "code": "ALREADY_SENT"}),
            (409, {"error": "Effects", "code": "SEND_EFFECTS_EXIST"}),
            (429, {"error": "Too many requests", "code": "RATE_LIMITED"}),
            (503, {"error": "Anchors off", "code": "ANCHOR_DISABLED_EDGE"}),
            (503, {"error": "Seals off", "code": "SEALS_DISABLED"}),
        ],
    )
    def test_definite_failures_keep_the_normal_error_text(self, status: int, body: dict[str, str]) -> None:
        data, _ = _send_template([_template(*ONE_SIGNER), _response(status, json_body=body)])

        error = data.data["error"]
        assert f"{body['code']}: {body['error']}" in error
        assert MAY_HAVE_BEEN_SENT not in error
        assert "may_have_been_sent" not in data.data


@pytest.mark.unit
class TestKeptRequest:
    @pytest.mark.parametrize(
        ("code", "phrase"),
        [("ALREADY_SENT", "was sent"), ("SEND_EFFECTS_EXIST", "was kept"), ("SEND_IN_PROGRESS", "was kept")],
    )
    def test_409_with_an_id_names_the_kept_request(self, code: str, phrase: str) -> None:
        body = {"error": "Send conflict", "code": code, "signing_request_id": "sr-kept"}
        data, request = _send_template([_template(*ONE_SIGNER), _response(409, json_body=body)])

        error = data.data["error"]
        assert f"The signing request sr-kept {phrase}" in error
        assert "check it in Firma instead of sending again" in error
        assert data.data["signing_request_id"] == "sr-kept"
        assert len(_send_calls(request)) == 1

    def test_409_send_in_progress_without_an_id_says_to_check_firma(self) -> None:
        body = {"error": "In progress", "code": "SEND_IN_PROGRESS"}
        data, _ = _send_template([_template(*ONE_SIGNER), _response(409, json_body=body)])

        assert CHECK_DASHBOARD in data.data["error"]

    def test_document_send_409_names_the_kept_request(self) -> None:
        body = {"error": "Sent", "code": "ALREADY_SENT", "signing_request_id": "sr-9"}
        data, _ = _send_document([_response(409, json_body=body)])

        assert "The signing request sr-9 was sent" in data.data["error"]
        assert data.data["signing_request_id"] == "sr-9"


@pytest.mark.unit
class TestTemplateRoles:
    def test_single_signer_fills_the_single_template_user(self) -> None:
        template = _template(_user("tu-2", 2, "Approver"), _user("cc-1", 1, "CC"))
        _, request = _send_template([template, _response(201, json_body=SEND_RESPONSE)])

        assert request.call_args_list[0].args[:2] == ("GET", f"{API_BASE_URL}/templates/{TEMPLATE_ID}")
        assert _send_calls(request)[0].kwargs["json"]["recipients"] == [
            {
                "first_name": "Ada",
                "email": "ada@firma.dev",
                "template_user_id": "tu-2",
                "designation": "Approver",
                "order": 2,
            }
        ]

    def test_single_signer_with_a_template_without_users_is_added_as_signer(self) -> None:
        _, request = _send_template([_template(), _response(201, json_body=SEND_RESPONSE)])

        assert _send_calls(request)[0].kwargs["json"]["recipients"] == [
            {"first_name": "Ada", "email": "ada@firma.dev", "designation": "Signer", "order": 1}
        ]

    def test_single_signer_with_a_multi_user_template_is_refused_before_sending(self) -> None:
        template = _template(_user("tu-1", 1), _user("tu-2", 2, "Approver"), name="Lease")
        data, request = _send_template([template])

        error = data.data["error"]
        assert 'template "Lease" has 2 recipients who sign or approve' in error
        assert "Recipients (JSON)" in error
        assert _send_calls(request) == []

    def test_recipients_json_covering_every_role_is_passed_through(self) -> None:
        recipients = [
            {"first_name": "A", "email": "a@firma.dev", "template_user_id": "tu-2"},
            {"first_name": "B", "email": "b@firma.dev", "order": 1},
            {"first_name": "C", "email": "c@firma.dev", "designation": "CC"},
        ]
        template = _template(_user("tu-1", 1), _user("tu-2", 2, "Approver"))
        _, request = _send_template(
            [template, _response(201, json_body=SEND_RESPONSE)], recipients_json=json.dumps(recipients)
        )

        assert _send_calls(request)[0].kwargs["json"]["recipients"] == [
            {
                "first_name": "A",
                "email": "a@firma.dev",
                "template_user_id": "tu-2",
                "designation": "Signer",
                "order": 1,
            },
            {"first_name": "B", "email": "b@firma.dev", "order": 1, "designation": "Signer"},
            {"first_name": "C", "email": "c@firma.dev", "designation": "CC", "order": 3},
        ]

    def test_recipients_json_missing_a_role_is_refused_before_sending(self) -> None:
        recipients = [
            {"first_name": "A", "email": "a@firma.dev", "template_user_id": "tu-1"},
            {"first_name": "C", "email": "c@firma.dev", "designation": "CC", "order": 2},
        ]
        template = _template(_user("tu-1", 1), _user("tu-2", 2, "Approver"), name="Lease")
        data, request = _send_template([template], recipients_json=json.dumps(recipients))

        assert "Approver at order 2 (template_user_id tu-2)" in data.data["error"]
        assert _send_calls(request) == []

    def test_a_template_user_id_turns_off_the_order_match(self) -> None:
        recipients = [{"first_name": "A", "email": "a@firma.dev", "template_user_id": "tu-2", "order": 1}]
        template = _template(_user("tu-1", 1), _user("tu-2", 2))
        data, request = _send_template([template], recipients_json=json.dumps(recipients))

        assert "template_user_id tu-1" in data.data["error"]
        assert _send_calls(request) == []


@pytest.mark.unit
class TestSendSummary:
    def test_no_invitation_email_claimed_when_signing_email_is_off(self) -> None:
        response = {**SEND_RESPONSE, "settings": {"send_signing_email": False}}
        data, _ = _send_template([_template(*ONE_SIGNER), _response(201, json_body=response)])

        assert "was notified" not in data.text
        assert "No invitation email was sent" in data.text
        assert "https://app.firma.dev/signing/u-1" in data.text

    def test_notified_when_signing_email_is_on(self) -> None:
        response = {**SEND_RESPONSE, "settings": {"send_signing_email": True}}
        data, _ = _send_template([_template(*ONE_SIGNER), _response(201, json_body=response)])

        assert "The first signer, Ada Lovelace (ada@firma.dev), was notified." in data.text
        assert "No invitation email" not in data.text
