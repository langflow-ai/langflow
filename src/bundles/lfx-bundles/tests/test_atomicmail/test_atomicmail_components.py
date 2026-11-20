"""Unit tests for the Atomic Mail components with mocked HTTP calls.

Requests are intercepted at ``httpx.AsyncClient.post``, so the tests exercise the real
request body, headers and error handling of the client.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.atomicmail.atomicmail_common import API_URL
from lfx_bundles.atomicmail.atomicmail_inbox import AtomicMailInboxComponent
from lfx_bundles.atomicmail.atomicmail_message import AtomicMailMessageComponent
from lfx_bundles.atomicmail.atomicmail_send_email import AtomicMailSendEmailComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "am_test_placeholder_key_0123456789"  # pragma: allowlist secret

ALL_COMPONENTS = [AtomicMailSendEmailComponent, AtomicMailInboxComponent, AtomicMailMessageComponent]

SUMMARY = {
    "id": "M1",
    "subject": "Your code",
    "from": [{"name": "Acme", "email": "no-reply@acme.example"}],
    "to": [{"name": None, "email": "agent@atomicmail.ai"}],
    "preview": "Your code is 123456",
    "receivedAt": "2026-11-20T08:09:52Z",
    "url": "https://mcp.atomicmail.ai/messages/M1",
}
MESSAGE = {
    "id": "M1",
    "threadId": "T1",
    "subject": "Your code",
    "from": [{"name": "Acme", "email": "no-reply@acme.example"}],
    "to": [{"name": None, "email": "agent@atomicmail.ai"}],
    "cc": None,
    "receivedAt": "2026-11-20T08:09:52Z",
    "attachments": None,
    "bodyTruncated": False,
    "body": "----- BEGIN UNTRUSTED EMAIL BODY -----\nYour code is 123456\n----- END UNTRUSTED EMAIL BODY -----",
}


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None, headers: Any = None):
    request = httpx.Request("POST", API_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, headers=headers, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _result(structured: Any = None, *, text: str = "ok"):
    result: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if structured is not None:
        result["structuredContent"] = structured
    return _response(json_body={"jsonrpc": "2.0", "id": 1, "result": result})


def _refused(text: str):
    result = {"content": [{"type": "text", "text": text}], "isError": True}
    return _response(json_body={"jsonrpc": "2.0", "id": 1, "result": result})


def _sent(post) -> dict[str, Any]:
    """The ``params`` of the JSON-RPC request the component posted."""
    assert post.call_args.args[0] == API_URL
    body = post.call_args.kwargs["json"]
    assert body["method"] == "tools/call"
    return body["params"]


def _send(**values) -> AtomicMailSendEmailComponent:
    component = AtomicMailSendEmailComponent()
    component.set(**{"api_key": API_KEY, "to": "anna@example.com", "subject": "Hello", "body": "Hi Anna", **values})
    return component


def _inbox(**values) -> AtomicMailInboxComponent:
    component = AtomicMailInboxComponent()
    component.set(**{"api_key": API_KEY, **values})
    return component


def _message(**values) -> AtomicMailMessageComponent:
    component = AtomicMailMessageComponent()
    component.set(**{"api_key": API_KEY, "message_id": "M1", **values})
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
class TestMetadata:
    def test_inputs_do_not_shadow_component_attributes(self, component_class) -> None:
        shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
        assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"

    def test_metadata_and_required_key(self, component_class) -> None:
        component = component_class()
        assert component.icon == "Mail"
        assert "atomicmail.ai" in component.documentation
        api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
        assert api_key.required is True

    def test_the_key_is_never_a_tool_argument(self, component_class) -> None:
        tool_inputs = {inp.name for inp in component_class.inputs if getattr(inp, "tool_mode", False)}
        assert tool_inputs
        assert not tool_inputs & {"api_key", "timeout", "from_name", "max_messages"}


@pytest.mark.unit
class TestSendEmail:
    async def test_sends_the_message_with_a_bearer_key(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_result(text="Sent.")) as post:
            result = await _send().send_email()

        params = _sent(post)
        assert params == {
            "name": "send_email",
            "arguments": {"to": ["anna@example.com"], "subject": "Hello", "body": "Hi Anna"},
        }
        headers = post.call_args.kwargs["headers"]
        assert headers["authorization"] == f"Bearer {API_KEY}"
        assert "application/json" in headers["accept"]
        assert "text/event-stream" in headers["accept"]
        assert result.text == "Sent to anna@example.com: Hello"
        assert result.data["to"] == ["anna@example.com"]
        assert "error" not in result.data
        assert "message_id" not in result.data

    async def test_result_has_the_id_of_the_stored_message(self) -> None:
        created = {"d1": {"id": "M9", "blobId": "G9", "threadId": "T9", "size": 10}}
        answer = {"methodResponses": [["Email/set", {"created": created}, "c0"], ["EmailSubmission/set", {}, "c1"]]}
        with patch("httpx.AsyncClient.post", return_value=_result(text=json.dumps(answer))):
            result = await _send().send_email()

        assert result.text == "Sent to anna@example.com: Hello"
        assert result.data["message_id"] == "M9"
        assert result.data["thread_id"] == "T9"

    async def test_several_recipients_cc_and_from_name(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_result()) as post:
            component = _send(to="a@example.com; b@example.com,\nc@example.com", cc=" d@example.com ", from_name="Anna")
            await component.send_email()

        arguments = _sent(post)["arguments"]
        assert arguments["to"] == ["a@example.com", "b@example.com", "c@example.com"]
        assert arguments["cc"] == ["d@example.com"]
        assert arguments["from_name"] == "Anna"

    @pytest.mark.parametrize("to", ["", "   ", " , ; "])
    async def test_empty_recipient_makes_no_request(self, to: str) -> None:
        with patch("httpx.AsyncClient.post") as post:
            result = await _send(to=to).send_email()

        post.assert_not_called()
        assert "Enter a recipient" in result.data["error"]

    async def test_empty_message_makes_no_request(self) -> None:
        with patch("httpx.AsyncClient.post") as post:
            result = await _send(subject=" ", body="\n").send_email()

        post.assert_not_called()
        assert "does not send an empty message" in result.data["error"]

    async def test_missing_key_makes_no_request(self) -> None:
        with patch("httpx.AsyncClient.post") as post:
            result = await _send(api_key="").send_email()

        post.assert_not_called()
        assert "Enter an Atomic Mail API key" in result.data["error"]

    async def test_refused_message_is_returned_as_the_error(self) -> None:
        refusal = "send_email failed: Bad recipient address syntax"
        with patch("httpx.AsyncClient.post", return_value=_refused(refusal)):
            result = await _send(to="not-an-address").send_email()

        assert result.data["error"] == refusal
        assert result.text == refusal

    async def test_rejected_key_and_rate_limit_have_clear_labels(self) -> None:
        rejected = _response(401, json_body={"error": "invalid_token", "error_description": "The API key is invalid."})
        with patch("httpx.AsyncClient.post", return_value=rejected):
            assert "rejected the API key (401)" in (await _send().send_email()).data["error"]
        with patch("httpx.AsyncClient.post", return_value=_response(429, text="slow down")):
            assert "rate limit reached (429)" in (await _send().send_email()).data["error"]

    async def test_other_status_keeps_the_server_message(self) -> None:
        body = {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Not Acceptable"}, "id": None}
        with patch("httpx.AsyncClient.post", return_value=_response(406, json_body=body)):
            result = await _send().send_email()

        assert result.data["error"] == "Atomic Mail API error (406): Not Acceptable"

    async def test_key_is_redacted_from_error_text_even_when_cut_at_the_limit(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_response(500, text="x" * 290 + API_KEY)):
            result = await _send().send_email()
        assert API_KEY[:10] not in result.data["error"]

        with patch("httpx.AsyncClient.post", return_value=_refused(f"bad key {API_KEY}")):
            result = await _send().send_email()
        assert API_KEY not in result.data["error"]
        assert "***" in result.data["error"]

    async def test_non_json_and_missing_result_are_errors(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_response(text="<html>bad gateway</html>")):
            assert "not JSON" in (await _send().send_email()).data["error"]
        with patch("httpx.AsyncClient.post", return_value=_response(json_body={"jsonrpc": "2.0", "id": 1})):
            assert "without a result" in (await _send().send_email()).data["error"]
        with patch("httpx.AsyncClient.post", return_value=_response(json_body=[1, 2])):
            assert "unexpected shape" in (await _send().send_email()).data["error"]

    async def test_protocol_error_is_returned(self) -> None:
        body = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid arguments"}}
        with patch("httpx.AsyncClient.post", return_value=_response(json_body=body)):
            result = await _send().send_email()

        assert result.data["error"] == "Atomic Mail refused the request: Invalid arguments"

    async def test_answer_sent_as_an_event_stream_is_read(self) -> None:
        message = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "Sent."}]}}
        stream = f"event: message\ndata: {json.dumps(message)}\n\n"
        response = _response(text=stream, headers={"content-type": "text/event-stream"})
        with patch("httpx.AsyncClient.post", return_value=response):
            result = await _send().send_email()

        assert result.text == "Sent to anna@example.com: Hello"

    async def test_notifications_before_the_answer_are_skipped(self) -> None:
        notice = {"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info", "data": "working"}}
        message = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "Sent."}]}}
        stream = f"event: message\ndata: {json.dumps(notice)}\n\nevent: message\ndata: {json.dumps(message)}\n\n"
        response = _response(text=stream, headers={"content-type": "text/event-stream"})
        with patch("httpx.AsyncClient.post", return_value=response):
            result = await _send().send_email()

        assert result.text == "Sent to anna@example.com: Hello"

    async def test_event_split_over_several_data_lines_is_read(self) -> None:
        message = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "Sent."}]}}
        lines = json.dumps(message, indent=1).splitlines()
        stream = "".join(f"data: {line}\n" for line in lines)
        response = _response(text=stream, headers={"content-type": "text/event-stream"})
        with patch("httpx.AsyncClient.post", return_value=response):
            result = await _send().send_email()

        assert result.text == "Sent to anna@example.com: Hello"

    async def test_stream_without_an_answer_is_an_error(self) -> None:
        notice = {"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info", "data": "working"}}
        headers = {"content-type": "text/event-stream"}
        with patch(
            "httpx.AsyncClient.post", return_value=_response(text=f"data: {json.dumps(notice)}\n\n", headers=headers)
        ):
            assert "without an answer" in (await _send().send_email()).data["error"]
        with patch("httpx.AsyncClient.post", return_value=_response(text="data: <html>\n\n", headers=headers)):
            assert "not JSON" in (await _send().send_email()).data["error"]

    async def test_timeout_and_connection_errors(self) -> None:
        with patch("httpx.AsyncClient.post", side_effect=httpx.ReadTimeout("slow")):
            result = await _send(timeout=2.5).send_email()
        assert result.data["error"] == "Atomic Mail did not answer within 2.5 seconds."
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("connection refused")):
            result = await _send().send_email()
        assert result.data["error"].startswith("Could not reach Atomic Mail: ConnectError")


@pytest.mark.unit
class TestInbox:
    async def test_lists_the_newest_messages_as_rows(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_result({"messages": [SUMMARY]})) as post:
            table = await _inbox().read_inbox()

        assert _sent(post) == {"name": "read_inbox", "arguments": {"limit": 10}}
        rows = table.to_dict(orient="records")
        assert len(rows) == 1
        assert rows[0]["id"] == "M1"
        assert rows[0]["from"] == "no-reply@acme.example"
        assert rows[0]["to"] == "agent@atomicmail.ai"
        assert rows[0]["subject"] == "Your code"
        assert rows[0]["received_at"] == "2026-11-20T08:09:52Z"
        assert rows[0]["preview"] == "Your code is 123456"
        assert rows[0]["text"] == "Your code is 123456"

    async def test_a_query_searches_all_mail(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_result({"messages": [SUMMARY]})) as post:
            await _inbox(query="  code ", max_messages=3).read_inbox()

        assert _sent(post) == {"name": "search_messages", "arguments": {"query": "code", "limit": 3}}

    @pytest.mark.parametrize(("requested", "sent"), [(0, 1), (-5, 1), (500, 50), (None, 1)])
    async def test_limit_is_kept_between_1_and_50(self, requested, sent: int) -> None:
        with patch("httpx.AsyncClient.post", return_value=_result({"messages": []})) as post:
            await _inbox(max_messages=requested).read_inbox()

        assert _sent(post)["arguments"]["limit"] == sent

    async def test_empty_inbox_is_an_empty_table(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_result({"messages": []})):
            table = await _inbox().read_inbox()

        assert len(table) == 0

    async def test_answer_without_messages_is_an_error(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_result({"unexpected": True})):
            table = await _inbox().read_inbox()

        rows = table.to_dict(orient="records")
        assert "without a list of messages" in rows[0]["error"]

    async def test_missing_key_makes_no_request(self) -> None:
        with patch("httpx.AsyncClient.post") as post:
            table = await _inbox(api_key="").read_inbox()

        post.assert_not_called()
        assert "Enter an Atomic Mail API key" in table.to_dict(orient="records")[0]["error"]


@pytest.mark.unit
class TestMessage:
    async def test_returns_the_body_as_text(self) -> None:
        with patch("httpx.AsyncClient.post", return_value=_result(MESSAGE)) as post:
            result = await _message(message_id=" M1 ").read_message()

        assert _sent(post) == {"name": "read_message", "arguments": {"message_id": "M1"}}
        assert result.text == MESSAGE["body"]
        assert result.data["id"] == "M1"
        assert result.data["thread_id"] == "T1"
        assert result.data["from"] == "no-reply@acme.example"
        assert result.data["to"] == "agent@atomicmail.ai"
        assert result.data["cc"] == ""
        assert result.data["subject"] == "Your code"
        assert result.data["attachments"] == []
        assert result.data["body_truncated"] is False

    @pytest.mark.parametrize("message_id", ["", "   "])
    async def test_empty_id_makes_no_request(self, message_id: str) -> None:
        with patch("httpx.AsyncClient.post") as post:
            result = await _message(message_id=message_id).read_message()

        post.assert_not_called()
        assert "Enter a message ID" in result.data["error"]

    async def test_unknown_id_is_returned_as_the_error(self) -> None:
        refusal = "read_message error: Message 'nope' not found."
        with patch("httpx.AsyncClient.post", return_value=_refused(refusal)):
            result = await _message(message_id="nope").read_message()

        assert result.data["error"] == refusal
