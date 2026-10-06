"""Contract tests for the SendHQ REST API components."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

pytest.importorskip("lfx_bundles")

from lfx_bundles.sendhq import (
    SendHQListEmailsComponent,
    SendHQReadEmailComponent,
    SendHQReplyToEmailComponent,
    SendHQSendEmailComponent,
)
from lfx_bundles.sendhq import send_email as send_email_module
from lfx_bundles.sendhq.sendhq_common import MAX_BODY_CHARS, split_addresses

API = "https://sendhq.cc/api/v1"
API_KEY = "re_test_key"  # pragma: allowlist secret

RECEIVED = {
    "id": "em_in1",
    "threadId": "em_out0",
    "direction": "in",
    "status": "received",
    "from": "Ada <ada@customer.test>",
    "to": ["support@acme.test"],
    "cc": [],
    "replyTo": None,
    "subject": "Order 42 is late",
    "text": "Hi, where is my order?",
    "html": "<p>Hi, where is my order?</p>",
    "raw": "MIME...",
    "unread": True,
    "category": "primary",
    "attachmentCount": 1,
    "attachments": [{"id": "att_1", "filename": "receipt.pdf", "sizeBytes": 1200}],
    "createdAt": "2026-10-06T10:00:00.000Z",
    # Every email carries its own delivery `error` (null unless it failed).
    "error": None,
}
SENT = {
    **RECEIVED,
    "id": "em_out0",
    "direction": "out",
    "from": "support@acme.test",
    "to": ["ada@customer.test"],
    "subject": "Your order",
}


def _logged_values(mock_log: AsyncMock) -> str:
    return " ".join(str(value) for call in mock_log.await_args_list for value in (*call.args, *call.kwargs.values()))


def test_split_addresses_accepts_commas_and_newlines() -> None:
    assert split_addresses(" a@x.test, b@x.test\nc@x.test ,, ") == ["a@x.test", "b@x.test", "c@x.test"]
    assert split_addresses(None) == []


@respx.mock
async def test_send_email_posts_payload_without_logging_content() -> None:
    route = respx.post(f"{API}/emails").mock(return_value=httpx.Response(201, json={"id": "em_1", "threadId": "em_1"}))
    component = SendHQSendEmailComponent(
        api_key=f" {API_KEY} ",
        from_email=" Acme <support@acme.test> ",
        to="ada@customer.test, ops@acme.test",
        subject="Welcome",
        body="private message body",
        cc="lead@acme.test",
        reply_to=" help@acme.test ",
        html="",
    )

    with patch.object(send_email_module.logger, "ainfo", new_callable=AsyncMock) as mock_log:
        result = await component.build_output()

    assert result.data["value"] == {"id": "em_1", "thread_id": "em_1", "to": ["ada@customer.test", "ops@acme.test"]}
    request = route.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert json.loads(request.content) == {
        "from": "Acme <support@acme.test>",
        "to": ["ada@customer.test", "ops@acme.test"],
        "subject": "Welcome",
        "text": "private message body",
        "cc": ["lead@acme.test"],
        "reply_to": "help@acme.test",
    }
    assert "private message body" not in _logged_values(mock_log)
    assert "ada@customer.test" not in _logged_values(mock_log)


@respx.mock
async def test_send_email_without_recipient_makes_no_request() -> None:
    route = respx.post(f"{API}/emails")
    component = SendHQSendEmailComponent(api_key=API_KEY, from_email="a@acme.test", to=" , ", subject="x", body="y")

    result = await component.build_output()

    assert result.data["value"] == {"error": "Provide at least one recipient."}
    assert not route.called


@respx.mock
async def test_send_email_flattens_api_error() -> None:
    respx.post(f"{API}/emails").mock(
        return_value=httpx.Response(
            403, json={"error": {"message": "The sender domain is not owned by this workspace", "status": 403}}
        )
    )
    component = SendHQSendEmailComponent(
        api_key=API_KEY, from_email="x@unverified.test", to="ada@customer.test", subject="x", body="y"
    )

    result = await component.build_output()

    assert result.data["value"] == {"error": "The sender domain is not owned by this workspace", "status": 403}
    assert component.status == result.data["value"]


@respx.mock
async def test_api_error_keeps_code_explanation_and_remedy() -> None:
    error = {
        "message": "Domain not verified",
        "status": 422,
        "code": "domain_unverified",
        "explanation": "acme.test is pending",
        "remedy": "Publish the DNS records",
    }
    respx.post(f"{API}/emails").mock(return_value=httpx.Response(422, json={"error": error}))
    component = SendHQSendEmailComponent(
        api_key=API_KEY, from_email="a@acme.test", to="b@x.test", subject="x", body="y"
    )

    result = await component.build_output()

    assert result.data["value"] == {
        "error": "Domain not verified",
        "status": 422,
        "code": "domain_unverified",
        "explanation": "acme.test is pending",
        "remedy": "Publish the DNS records",
    }


@respx.mock
async def test_network_failure_is_returned_as_error() -> None:
    respx.get(f"{API}/emails").mock(side_effect=httpx.ConnectError("boom"))

    result = await SendHQListEmailsComponent(api_key=API_KEY).build_output()

    assert result.data["value"] == {"error": "Request to SendHQ failed: boom"}


@respx.mock
async def test_list_emails_sends_filters_and_trims_results() -> None:
    route = respx.get(f"{API}/emails").mock(return_value=httpx.Response(200, json={"data": [RECEIVED], "count": 1}))
    component = SendHQListEmailsComponent(
        api_key=API_KEY, direction="Received", unread_only=True, query=" order ", limit=500
    )

    result = await component.build_output()

    params = dict(route.calls[0].request.url.params)
    assert params == {"limit": "100", "direction": "in", "unread": "true", "query": "order"}
    value = result.data["value"]
    assert value["count"] == 1
    email = value["emails"][0]
    assert email["id"] == "em_in1"
    assert email["snippet"] == "Hi, where is my order?"
    assert "raw" not in email
    assert "html" not in email
    # A null delivery error on a received email is not reported.
    assert "error" not in email
    assert "delivery_error" not in email


@respx.mock
async def test_list_all_directions_omits_direction_and_reports_delivery_errors() -> None:
    failed = {**SENT, "status": "failed", "error": "Recipient count exceeds 50."}
    route = respx.get(f"{API}/emails").mock(return_value=httpx.Response(200, json={"data": [failed]}))

    result = await SendHQListEmailsComponent(api_key=API_KEY, direction="All").build_output()

    assert "direction" not in dict(route.calls[0].request.url.params)
    assert result.data["value"]["emails"][0]["delivery_error"] == "Recipient count exceeds 50."


@respx.mock
async def test_read_email_returns_body_and_attachments() -> None:
    respx.get(f"{API}/emails/em_in1").mock(return_value=httpx.Response(200, json=RECEIVED))

    result = await SendHQReadEmailComponent(api_key=API_KEY, email_id=" em_in1 ").build_output()

    value = result.data["value"]
    assert value["body"] == "Hi, where is my order?"
    assert value["attachments"] == [{"id": "att_1", "filename": "receipt.pdf", "size_bytes": 1200}]
    assert "error" not in value
    assert "raw" not in value


@respx.mock
async def test_read_email_truncates_long_bodies() -> None:
    respx.get(f"{API}/emails/em_in1").mock(
        return_value=httpx.Response(200, json={**RECEIVED, "text": "x" * (MAX_BODY_CHARS + 5)})
    )

    result = await SendHQReadEmailComponent(api_key=API_KEY, email_id="em_in1").build_output()

    assert len(result.data["value"]["body"]) == MAX_BODY_CHARS
    assert result.data["value"]["body_truncated"] is True


@respx.mock
async def test_read_whole_thread_follows_thread_id() -> None:
    respx.get(f"{API}/emails/em_in1").mock(return_value=httpx.Response(200, json=RECEIVED))
    thread = respx.get(f"{API}/threads/em_out0").mock(
        return_value=httpx.Response(200, json={"id": "em_out0", "subject": "Your order", "data": [SENT, RECEIVED]})
    )

    result = await SendHQReadEmailComponent(api_key=API_KEY, email_id="em_in1", whole_thread=True).build_output()

    assert thread.called
    value = result.data["value"]
    assert value["thread_id"] == "em_out0"
    assert [message["id"] for message in value["messages"]] == ["em_out0", "em_in1"]


@respx.mock
async def test_read_unknown_email_returns_not_found() -> None:
    respx.get(f"{API}/emails/em_nope").mock(
        return_value=httpx.Response(404, json={"error": {"message": "Email not found", "status": 404}})
    )

    result = await SendHQReadEmailComponent(api_key=API_KEY, email_id="em_nope").build_output()

    assert result.data["value"] == {"error": "Email not found", "status": 404}


@respx.mock
async def test_reply_to_received_email_answers_sender_from_receiving_address() -> None:
    respx.get(f"{API}/emails/em_in1").mock(return_value=httpx.Response(200, json=RECEIVED))
    send = respx.post(f"{API}/emails").mock(
        return_value=httpx.Response(201, json={"id": "em_r1", "threadId": "em_out0"})
    )

    result = await SendHQReplyToEmailComponent(
        api_key=API_KEY, email_id="em_in1", body="It ships today.", from_email=""
    ).build_output()

    assert result.data["value"] == {"id": "em_r1", "thread_id": "em_out0", "to": ["Ada <ada@customer.test>"]}
    assert json.loads(send.calls[0].request.content) == {
        "from": "support@acme.test",
        "to": ["Ada <ada@customer.test>"],
        "subject": "Re: Order 42 is late",
        "text": "It ships today.",
        "reply_to_email_id": "em_in1",
    }


@respx.mock
async def test_reply_prefers_reply_to_and_configured_sender_and_keeps_re_prefix() -> None:
    parent = {**RECEIVED, "replyTo": "tickets@customer.test", "subject": "RE: Order 42"}
    respx.get(f"{API}/emails/em_in1").mock(return_value=httpx.Response(200, json=parent))
    send = respx.post(f"{API}/emails").mock(
        return_value=httpx.Response(201, json={"id": "em_r2", "threadId": "em_out0"})
    )

    await SendHQReplyToEmailComponent(
        api_key=API_KEY, email_id="em_in1", body="Done.", from_email="Acme <help@acme.test>"
    ).build_output()

    payload = json.loads(send.calls[0].request.content)
    assert payload["to"] == ["tickets@customer.test"]
    assert payload["from"] == "Acme <help@acme.test>"
    assert payload["subject"] == "RE: Order 42"


@respx.mock
async def test_follow_up_to_sent_email_goes_to_original_recipients() -> None:
    respx.get(f"{API}/emails/em_out0").mock(return_value=httpx.Response(200, json=SENT))
    send = respx.post(f"{API}/emails").mock(
        return_value=httpx.Response(201, json={"id": "em_f1", "threadId": "em_out0"})
    )

    await SendHQReplyToEmailComponent(
        api_key=API_KEY, email_id="em_out0", body="Checking in.", from_email=""
    ).build_output()

    payload = json.loads(send.calls[0].request.content)
    assert payload["from"] == "support@acme.test"
    assert payload["to"] == ["ada@customer.test"]
    assert payload["subject"] == "Re: Your order"


@respx.mock
async def test_reply_with_empty_body_makes_no_request() -> None:
    get = respx.get(f"{API}/emails/em_in1")

    result = await SendHQReplyToEmailComponent(api_key=API_KEY, email_id="em_in1", body="  ").build_output()

    assert result.data["value"] == {"error": "Provide a reply."}
    assert not get.called


async def test_missing_api_key_makes_no_request() -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.get(f"{API}/emails")
        result = await SendHQListEmailsComponent(api_key="").build_output()

    assert result.data["value"] == {"error": "No SendHQ API key provided."}
    assert not route.called
