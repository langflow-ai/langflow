"""Unit tests for the Firma components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the
real URLs, headers, query parameters, bodies and error handling of the client.
"""

from __future__ import annotations

import base64
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx.schema.dataframe import DataFrame
from lfx.utils.file_path_security import LocalFileAccessError
from lfx_bundles.firma.firma_common import API_BASE_URL, INLINE_DOCUMENT_MAX_BYTES, LANGUAGES
from lfx_bundles.firma.firma_download_document import FirmaDownloadSignedDocumentComponent
from lfx_bundles.firma.firma_get_signing_request import FirmaGetSigningRequestComponent
from lfx_bundles.firma.firma_list_signing_requests import FirmaListSigningRequestsComponent
from lfx_bundles.firma.firma_list_templates import FirmaListTemplatesComponent
from lfx_bundles.firma.firma_send_document import FirmaSendDocumentComponent
from lfx_bundles.firma.firma_send_template import FirmaSendTemplateComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-firma-api-key-placeholder"  # pragma: allowlist secret
TEMPLATE_ID = "a12a33db-4d52-41ad-a66b-b45f6dc2830a"
REQUEST_ID = "5b0c8a52-3f0e-4f43-9d0e-7c1f2b3a4d5e"
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
UPLOAD_URL = "https://storage.example.test/upload/doc-1?token=signed"

ALL_COMPONENTS = [
    FirmaSendTemplateComponent,
    FirmaSendDocumentComponent,
    FirmaGetSigningRequestComponent,
    FirmaListSigningRequestsComponent,
    FirmaListTemplatesComponent,
    FirmaDownloadSignedDocumentComponent,
]

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


ONE_SIGNER_TEMPLATE = {
    "id": TEMPLATE_ID,
    "name": "i-9",
    "recipients": [{"id": "tu-1", "name": None, "email": None, "designation": "Signer", "order": 1}],
}


def _response(
    status_code: int = 200, *, json_body: Any = None, text: str | None = None, headers=None
) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request, headers=headers)
    return httpx.Response(status_code, json=json_body, request=request, headers=headers)


def _component(component_class: type[Component], **values) -> Component:
    component = component_class()
    component.set(**{"api_key": API_KEY, **values})
    return component


def _calls(request) -> list[tuple[str, str, dict[str, Any]]]:
    return [(call.args[0], call.args[1], call.kwargs) for call in request.call_args_list]


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_metadata(component_class: type[Component]) -> None:
    component = component_class()
    assert component.icon == "Firma"
    assert "docs.firma.dev" in component.documentation
    assert component.display_name.startswith("Firma ")
    api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
    assert api_key.required is True
    assert type(api_key).__name__ == "SecretStrInput"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_missing_api_key_makes_no_request(component_class: type[Component]) -> None:
    component = _component(
        component_class,
        api_key="  ",
        template_id=TEMPLATE_ID,
        signing_request_id=REQUEST_ID,
        signer_first_name="Ada",
        signer_email="ada@firma.dev",
        document_base64=base64.b64encode(PDF_BYTES).decode(),
    )
    method = next(output.method for output in component_class.outputs)
    with patch("httpx.Client.request") as request:
        result = getattr(component, method)()

    request.assert_not_called()
    error = result.iloc[0]["error"] if isinstance(result, DataFrame) else result.data["error"]
    assert "Enter a Firma API key" in error


@pytest.mark.unit
class TestFirmaSendTemplate:
    def test_creates_and_sends_with_the_single_signer(self) -> None:
        component = _component(
            FirmaSendTemplateComponent,
            template_id=f" {TEMPLATE_ID} ",
            request_name="Offer letter",
            signer_first_name="Ada",
            signer_last_name="Lovelace",
            signer_email="ada@firma.dev",
        )
        replies = [_response(json_body=ONE_SIGNER_TEMPLATE), _response(201, json_body=SEND_RESPONSE)]
        with patch("httpx.Client.request", side_effect=replies) as request:
            data = component.send_request()

        assert _calls(request)[0][:2] == ("GET", f"{API_BASE_URL}/templates/{TEMPLATE_ID}")
        (method, url, kwargs) = _calls(request)[1]
        assert request.call_count == 2
        assert method == "POST"
        assert url == f"{API_BASE_URL}/signing-requests/create-and-send"
        assert kwargs["headers"]["Authorization"] == API_KEY
        assert kwargs["json"] == {
            "template_id": TEMPLATE_ID,
            "name": "Offer letter",
            "recipients": [
                {
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "email": "ada@firma.dev",
                    "template_user_id": "tu-1",
                    "designation": "Signer",
                    "order": 1,
                }
            ],
        }
        assert data.data["signing_request_id"] == REQUEST_ID
        assert data.data["status"] == "sent"
        assert data.data["signing_link"] == "https://app.firma.dev/signing/u-1"
        assert REQUEST_ID in data.text

    def test_empty_name_uses_the_template_name(self) -> None:
        responses = [_response(json_body={"id": TEMPLATE_ID, "name": "i-9"}), _response(201, json_body=SEND_RESPONSE)]
        component = _component(FirmaSendTemplateComponent, template_id=TEMPLATE_ID)
        with patch("httpx.Client.request", side_effect=responses) as request:
            component.send_request()

        calls = _calls(request)
        assert calls[0][:2] == ("GET", f"{API_BASE_URL}/templates/{TEMPLATE_ID}")
        assert calls[1][2]["json"] == {"template_id": TEMPLATE_ID, "name": "i-9"}

    def test_recipients_json_and_options_are_sent(self) -> None:
        recipients = (
            '[{"first_name": "Ada", "email": "ada@firma.dev"},'
            ' {"first_name": "Bob", "email": "bob@firma.dev", "designation": "cc", "order": 5}]'
        )
        component = _component(
            FirmaSendTemplateComponent,
            template_id=TEMPLATE_ID,
            request_name="Pack",
            recipients_json=recipients,
            message="Please sign",
            expiration_hours=48,
            language="de",
        )
        replies = [_response(json_body=ONE_SIGNER_TEMPLATE), _response(201, json_body=SEND_RESPONSE)]
        with patch("httpx.Client.request", side_effect=replies) as request:
            component.send_request()

        body = request.call_args.kwargs["json"]
        assert body["recipients"] == [
            {"first_name": "Ada", "email": "ada@firma.dev", "designation": "Signer", "order": 1},
            {"first_name": "Bob", "email": "bob@firma.dev", "designation": "CC", "order": 5},
        ]
        assert body["description"] == "Please sign"
        assert body["expiration_hours"] == 48
        assert body["language"] == "de"

    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            ({"template_id": ""}, "Enter the template ID"),
            ({"signer_first_name": "Ada"}, "first name and email"),
            ({"signer_email": "a@firma.dev", "signer_first_name": "A", "recipients_json": "[]"}, "not both"),
            ({"recipients_json": "{not json"}, "must be a JSON array"),
            ({"recipients_json": '[{"first_name": "A", "email": "a@x.test", "designation": "CC"}]'}, "Signer"),
            ({"recipients_json": '[{"first_name": "A", "email": "a@x.test", "designation": "Boss"}]'}, "designation"),
            ({"expiration_hours": -2}, "at least 1"),
            ({"language": "xx"}, "Choose a language"),
        ],
    )
    def test_invalid_input_makes_no_request(self, values: dict[str, Any], expected: str) -> None:
        component = _component(
            FirmaSendTemplateComponent, **{"template_id": TEMPLATE_ID, "request_name": "R", **values}
        )
        with patch("httpx.Client.request") as request:
            data = component.send_request()

        request.assert_not_called()
        assert expected in data.data["error"]

    def test_api_validation_error_is_returned_and_key_is_redacted(self) -> None:
        body = {
            "error": f"Invalid request for {API_KEY}",
            "code": "VALIDATION_ERROR",
            "errors": [{"field": "recipients", "message": "recipients[0].email is invalid"}],
        }
        component = _component(
            FirmaSendTemplateComponent,
            template_id=TEMPLATE_ID,
            request_name="R",
            signer_first_name="A",
            signer_email="a",
        )
        replies = [_response(json_body=ONE_SIGNER_TEMPLATE), _response(400, json_body=body)]
        with patch("httpx.Client.request", side_effect=replies) as request:
            data = component.send_request()

        assert _calls(request)[1][:2] == ("POST", f"{API_BASE_URL}/signing-requests/create-and-send")

        error = data.data["error"]
        assert error.startswith("Firma API error (400) VALIDATION_ERROR: Invalid request for ***")
        assert "recipients[0].email is invalid" in error
        assert API_KEY not in error


@pytest.mark.unit
class TestFirmaSendDocument:
    def _send(self, response_list: list[httpx.Response], **values) -> tuple[Any, Any]:
        component = _component(
            FirmaSendDocumentComponent,
            **{
                "request_name": "NDA",
                "signer_first_name": "Ada",
                "signer_email": "ada@firma.dev",
                "document_base64": base64.b64encode(PDF_BYTES).decode(),
                **values,
            },
        )
        with patch("httpx.Client.request", side_effect=response_list) as request:
            data = component.send_document()
        return data, request

    def test_small_document_is_sent_inline_with_a_default_signature_box(self) -> None:
        data, request = self._send([_response(201, json_body=SEND_RESPONSE)])

        (method, url, kwargs) = _calls(request)[0]
        assert request.call_count == 1
        assert (method, url) == ("POST", f"{API_BASE_URL}/signing-requests/create-and-send")
        body = kwargs["json"]
        assert base64.b64decode(body["document"]) == PDF_BYTES
        assert body["name"] == "NDA"
        assert body["recipients"] == [
            {"first_name": "Ada", "email": "ada@firma.dev", "designation": "Signer", "order": 1, "id": "temp_1"}
        ]
        assert body["fields"] == [
            {
                "type": "signature",
                "recipient_id": "temp_1",
                "page_number": 1,
                "position": {"x": 5, "y": 86, "width": 28, "height": 8},
                "required": True,
            }
        ]
        assert "anchor_tags" not in body
        assert data.data["signing_link"] == "https://app.firma.dev/signing/u-1"

    def test_data_url_prefix_is_accepted(self) -> None:
        encoded = "data:application/pdf;base64," + base64.b64encode(PDF_BYTES).decode()
        _, request = self._send([_response(201, json_body=SEND_RESPONSE)], document_base64=encoded)

        assert base64.b64decode(request.call_args.kwargs["json"]["document"]) == PDF_BYTES

    def test_default_boxes_wrap_into_rows_for_many_signers(self) -> None:
        recipients = ",".join(f'{{"first_name": "S{i}", "email": "s{i}@firma.dev"}}' for i in range(1, 5))
        _, request = self._send(
            [_response(201, json_body=SEND_RESPONSE)],
            signer_first_name="",
            signer_email="",
            recipients_json=f"[{recipients}]",
            signature_page=2,
        )

        fields = request.call_args.kwargs["json"]["fields"]
        assert [(f["recipient_id"], f["page_number"], f["position"]["x"], f["position"]["y"]) for f in fields] == [
            ("temp_1", 2, 5, 86),
            ("temp_2", 2, 36, 86),
            ("temp_3", 2, 67, 86),
            ("temp_4", 2, 5, 76),
        ]

    def test_anchor_text_places_one_tag_per_signer(self) -> None:
        recipients = '[{"first_name": "A", "email": "a@firma.dev"}, {"first_name": "B", "email": "b@firma.dev"}]'
        _, request = self._send(
            [_response(201, json_body=SEND_RESPONSE)],
            signer_first_name="",
            signer_email="",
            recipients_json=recipients,
            signature_anchor="{{sign_{n}}}",
        )

        body = request.call_args.kwargs["json"]
        assert "fields" not in body
        assert body["anchor_tags"] == [
            {"anchor_string": "{{sign_1}}", "type": "signature", "recipient_id": "temp_1"},
            {"anchor_string": "{{sign_2}}", "type": "signature", "recipient_id": "temp_2"},
        ]

    def test_anchor_without_placeholder_is_refused_for_several_signers(self) -> None:
        recipients = '[{"first_name": "A", "email": "a@firma.dev"}, {"first_name": "B", "email": "b@firma.dev"}]'
        data, request = self._send(
            [], signer_first_name="", signer_email="", recipients_json=recipients, signature_anchor="SIGN HERE"
        )

        request.assert_not_called()
        assert "{n}" in data.data["error"]

    def test_explicit_fields_and_anchor_tags_are_passed_through(self) -> None:
        fields = '[{"type": "date", "recipient_id": "temp_1", "page_number": 1, "position": {"x": 1, "y": 2}}]'
        tags = '[{"anchor_string": "INIT", "type": "initial", "recipient_id": "temp_1"}]'
        _, request = self._send([_response(201, json_body=SEND_RESPONSE)], fields_json=fields, anchor_tags_json=tags)

        body = request.call_args.kwargs["json"]
        assert body["fields"][0]["type"] == "date"
        assert body["anchor_tags"][0]["anchor_string"] == "INIT"

    def test_large_document_uses_the_presigned_upload(self) -> None:
        large = PDF_BYTES + b"0" * INLINE_DOCUMENT_MAX_BYTES
        upload = {"document_id": "doc-1", "upload_url": UPLOAD_URL, "expires_in": 3600}
        data, request = self._send(
            [_response(201, json_body=upload), _response(200, text=""), _response(201, json_body=SEND_RESPONSE)],
            document_base64=base64.b64encode(large).decode(),
            document_file_name="big.pdf",
        )

        calls = _calls(request)
        assert calls[0][:2] == ("POST", f"{API_BASE_URL}/documents")
        assert calls[0][2]["json"] == {
            "file_name": "big.pdf",
            "file_size": len(large),
            "content_type": "application/pdf",
        }
        assert calls[1][:2] == ("PUT", UPLOAD_URL)
        assert calls[1][2]["content"] == large
        assert calls[1][2]["headers"] == {"Content-Type": "application/pdf"}
        assert "Authorization" not in calls[1][2]["headers"]
        body = calls[2][2]["json"]
        assert body["document_id"] == "doc-1"
        assert "document" not in body
        assert data.data["signing_request_id"] == REQUEST_ID

    def test_failed_storage_upload_stops_before_sending(self) -> None:
        upload = {"document_id": "doc-1", "upload_url": UPLOAD_URL}
        large = PDF_BYTES + b"0" * INLINE_DOCUMENT_MAX_BYTES
        data, request = self._send(
            [_response(201, json_body=upload), _response(403, text="denied")],
            document_base64=base64.b64encode(large).decode(),
        )

        assert request.call_count == 2
        assert "HTTP 403" in data.data["error"]

    def test_docx_is_detected_from_the_file_name(self) -> None:
        large = b"PK\x03\x04" + b"0" * INLINE_DOCUMENT_MAX_BYTES
        upload = {"document_id": "doc-1", "upload_url": UPLOAD_URL}
        _, request = self._send(
            [_response(201, json_body=upload), _response(200, text=""), _response(201, json_body=SEND_RESPONSE)],
            document_base64=base64.b64encode(large).decode(),
            document_file_name="contract.docx",
        )

        assert _calls(request)[0][2]["json"]["content_type"] == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            ({"document_base64": ""}, "Attach a PDF or DOCX file"),
            ({"document_base64": "not base64!!"}, "not valid base64"),
            ({"document_base64": base64.b64encode(b"hello").decode()}, "PDF or DOCX"),
            ({"document_base64": base64.b64encode(PDF_BYTES).decode(), "document_file_name": "x.txt"}, "PDF or DOCX"),
            ({"signer_email": ""}, "first name and email"),
            ({"signature_page": -1}, "at least 1"),
        ],
    )
    def test_invalid_input_makes_no_request(self, values: dict[str, Any], expected: str) -> None:
        data, request = self._send([], **values)

        request.assert_not_called()
        assert expected in data.data["error"]

    def test_uploaded_file_is_read_through_the_confined_storage_reader(self) -> None:
        component = _component(
            FirmaSendDocumentComponent,
            request_name="NDA",
            signer_first_name="Ada",
            signer_email="ada@firma.dev",
            document_file="flow-1/nda.pdf",
        )
        reader = AsyncMock(return_value=PDF_BYTES)
        with (
            patch("lfx_bundles.firma.firma_send_document.read_file_bytes", reader),
            patch("httpx.Client.request", return_value=_response(201, json_body=SEND_RESPONSE)) as request,
        ):
            data = component.send_document()

        assert reader.await_args.args[0] == "flow-1/nda.pdf"
        assert reader.await_args.kwargs["resolve_path"] == component._confine_local_path
        assert base64.b64decode(request.call_args.kwargs["json"]["document"]) == PDF_BYTES
        assert data.data["signing_request_id"] == REQUEST_ID

    def test_unreadable_file_is_an_error(self) -> None:
        component = _component(
            FirmaSendDocumentComponent,
            signer_first_name="Ada",
            signer_email="ada@firma.dev",
            document_file="/etc/x.pdf",
        )
        reader = AsyncMock(side_effect=LocalFileAccessError("Access to local file paths is disabled"))
        with (
            patch("lfx_bundles.firma.firma_send_document.read_file_bytes", reader),
            patch("httpx.Client.request") as request,
        ):
            data = component.send_document()

        request.assert_not_called()
        assert "Could not read the document file" in data.data["error"]

    def test_local_paths_are_confined_to_the_component_scope(self) -> None:
        component = _component(FirmaSendDocumentComponent)
        with (
            patch("lfx.utils.file_path_security.is_local_file_access_restricted", return_value=True),
            pytest.raises(LocalFileAccessError),
        ):
            component._confine_local_path("/etc/passwd")


@pytest.mark.unit
class TestFirmaGetSigningRequest:
    def test_returns_status_and_recipients(self) -> None:
        request_body = {"id": REQUEST_ID, "name": "NDA", "status": {"sent": True, "finished": False}}
        users = {
            "results": [
                {"id": "u-1", "name": "Ada", "email": "ada@firma.dev", "designation": "Signer", "finished_on": "x"},
                {"id": "u-2", "name": "Bob", "email": "bob@firma.dev", "designation": "Signer"},
            ]
        }
        component = _component(FirmaGetSigningRequestComponent, signing_request_id=REQUEST_ID)
        with patch(
            "httpx.Client.request", side_effect=[_response(json_body=request_body), _response(json_body=users)]
        ) as request:
            data = component.get_signing_request()

        calls = _calls(request)
        assert calls[0][:2] == ("GET", f"{API_BASE_URL}/signing-requests/{REQUEST_ID}")
        assert calls[1][:2] == ("GET", f"{API_BASE_URL}/signing-requests/{REQUEST_ID}/users")
        assert data.data["status"] == "in_progress"
        assert data.data["recipients"] == users["results"]
        assert "1 of 2" in data.text

    @pytest.mark.parametrize(
        ("flags", "expected"),
        [
            ({}, "not_sent"),
            ({"sent": True, "finished": True}, "finished"),
            ({"sent": True, "declined": True}, "declined"),
            ({"sent": True, "cancelled": True}, "cancelled"),
            ({"sent": True, "expired": True}, "expired"),
        ],
    )
    def test_status_is_derived_from_the_flags(self, flags: dict[str, bool], expected: str) -> None:
        responses = [_response(json_body={"id": REQUEST_ID, "status": flags}), _response(json_body={"results": []})]
        component = _component(FirmaGetSigningRequestComponent, signing_request_id=REQUEST_ID)
        with patch("httpx.Client.request", side_effect=responses):
            assert component.get_signing_request().data["status"] == expected

    def test_id_is_escaped_into_one_path_segment(self) -> None:
        component = _component(FirmaGetSigningRequestComponent, signing_request_id="../templates")
        with patch("httpx.Client.request", return_value=_response(404, json_body={"error": "Not found"})) as request:
            data = component.get_signing_request()

        assert request.call_args.args[1] == f"{API_BASE_URL}/signing-requests/..%2Ftemplates"
        assert data.data["error"] == "Firma could not find the resource (404): Not found"


@pytest.mark.unit
class TestFirmaListSigningRequests:
    def test_default_query_and_rows(self) -> None:
        body = {
            "results": [
                {"id": "r-1", "name": "NDA", "status": "finished"},
                {"id": "r-2", "name": "MSA", "status": "not_sent"},
            ],
            "pagination": {"current_page": 1, "page_size": 25, "total_count": 2, "total_pages": 1},
        }
        component = _component(FirmaListSigningRequestsComponent)
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            frame = component.list_dataframe()

        method, url = request.call_args.args
        assert (method, url) == ("GET", f"{API_BASE_URL}/signing-requests")
        assert request.call_args.kwargs["params"] == {
            "page": 1,
            "page_size": 25,
            "sort_by": "created_on",
            "sort_order": "desc",
            "exclude_deleted": "true",
        }
        assert list(frame["id"]) == ["r-1", "r-2"]
        assert list(frame["status"]) == ["finished", "not_sent"]

    def test_filters_are_sent(self) -> None:
        component = _component(
            FirmaListSigningRequestsComponent,
            status_filter="finished",
            name_filter=" NDA ",
            signer_email="ada@firma.dev",
            page=3,
            page_size=500,
            exclude_deleted=False,
        )
        with patch("httpx.Client.request", return_value=_response(json_body={"results": []})) as request:
            component.list_requests()

        assert request.call_args.kwargs["params"] == {
            "page": 3,
            "page_size": 200,
            "sort_by": "created_on",
            "sort_order": "desc",
            "status": "finished",
            "name": "NDA",
            "signer_email": "ada@firma.dev",
        }

    def test_deleted_status_does_not_exclude_deleted(self) -> None:
        component = _component(FirmaListSigningRequestsComponent, status_filter="deleted")
        with patch("httpx.Client.request", return_value=_response(json_body={"results": []})) as request:
            component.list_requests()

        params = request.call_args.kwargs["params"]
        assert params["status"] == "deleted"
        assert "exclude_deleted" not in params

    def test_rate_limit_error_is_one_row(self) -> None:
        component = _component(FirmaListSigningRequestsComponent)
        response = _response(
            429, json_body={"error": "Too many requests", "code": "RATE_LIMITED"}, headers={"Retry-After": "7"}
        )
        with patch("httpx.Client.request", return_value=response):
            rows = component.list_requests()

        assert len(rows) == 1
        assert (
            rows[0].data["error"]
            == "Firma rate limit exceeded (429) RATE_LIMITED: Too many requests Retry after 7 seconds."
        )

    def test_missing_results_list_is_an_error(self) -> None:
        component = _component(FirmaListSigningRequestsComponent)
        with patch("httpx.Client.request", return_value=_response(json_body={"data": []})):
            rows = component.list_requests()

        assert "without a results list" in rows[0].data["error"]


@pytest.mark.unit
class TestFirmaListTemplates:
    def test_query_and_rows(self) -> None:
        body = {"results": [{"id": TEMPLATE_ID, "name": "i-9"}], "pagination": {"total_count": 1}}
        component = _component(FirmaListTemplatesComponent, name_filter="i-9", page_size=10)
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            frame = component.list_dataframe()

        assert request.call_args.args == ("GET", f"{API_BASE_URL}/templates")
        assert request.call_args.kwargs["params"] == {
            "page": 1,
            "page_size": 10,
            "sort_by": "created_on",
            "sort_order": "desc",
            "name": "i-9",
        }
        assert list(frame["name"]) == ["i-9"]

    def test_auth_error_is_returned(self) -> None:
        component = _component(FirmaListTemplatesComponent)
        response = _response(401, json_body={"error": "Invalid API key", "code": "UNAUTHORIZED"})
        with patch("httpx.Client.request", return_value=response):
            rows = component.list_templates()

        assert rows[0].data["error"] == "Firma rejected the API key (401) UNAUTHORIZED: Invalid API key"

    def test_timeout_is_an_error(self) -> None:
        component = _component(FirmaListTemplatesComponent, timeout=2.5)
        with patch("httpx.Client.request", side_effect=httpx.ReadTimeout("slow")):
            rows = component.list_templates()

        assert rows[0].data["error"] == "Firma request timed out after 2.5 seconds."

    def test_unreachable_api_is_an_error(self) -> None:
        component = _component(FirmaListTemplatesComponent)
        with patch("httpx.Client.request", side_effect=httpx.ConnectError("connection refused")):
            rows = component.list_templates()

        assert rows[0].data["error"].startswith("Could not reach the Firma API: ConnectError")

    def test_non_json_response_is_an_error(self) -> None:
        component = _component(FirmaListTemplatesComponent)
        with patch("httpx.Client.request", return_value=_response(text="<html>bad gateway</html>")):
            rows = component.list_templates()

        assert "not JSON" in rows[0].data["error"]


@pytest.mark.unit
class TestFirmaDownloadSignedDocument:
    def test_returns_the_download_url(self) -> None:
        body = {
            "status": "finished",
            "is_partial": False,
            "download_url": "https://storage.example.test/signed.pdf?token=t",
            "expires_at": "2026-11-24T10:00:00Z",
        }
        component = _component(FirmaDownloadSignedDocumentComponent, signing_request_id=REQUEST_ID)
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            data = component.get_download()

        assert request.call_args.args == ("GET", f"{API_BASE_URL}/signing-requests/{REQUEST_ID}/download")
        assert data.text == body["download_url"]
        assert data.data["download_url"] == body["download_url"]
        assert data.data["signing_request_id"] == REQUEST_ID

    def test_conflict_explains_the_retry(self) -> None:
        body = {"error": "No document available yet", "code": "DOCUMENT_NOT_READY"}
        component = _component(FirmaDownloadSignedDocumentComponent, signing_request_id=REQUEST_ID)
        with patch("httpx.Client.request", return_value=_response(409, json_body=body)):
            data = component.get_download()

        error = data.data["error"]
        assert error.startswith("Firma API error (409) DOCUMENT_NOT_READY: No document available yet")
        assert "retry in a minute" in error

    def test_missing_id_makes_no_request(self) -> None:
        component = _component(FirmaDownloadSignedDocumentComponent, signing_request_id=" ")
        with patch("httpx.Client.request") as request:
            data = component.get_download()

        request.assert_not_called()
        assert data.data["error"] == "Enter the signing request ID."


@pytest.mark.unit
def test_language_options_cover_every_supported_language() -> None:
    language = next(inp for inp in FirmaSendTemplateComponent.inputs if inp.name == "language")
    assert language.options[1:] == LANGUAGES
    assert len(LANGUAGES) == 15
