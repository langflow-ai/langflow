"""Mailtrap: List Sandbox Messages, Get Sandbox Message and Check Sandbox Message."""

from __future__ import annotations

import asyncio

import pytest
from lfx_mailtrap import (
    MailtrapCheckSandboxMessageComponent,
    MailtrapGetSandboxMessageComponent,
    MailtrapListSandboxMessagesComponent,
)
from lfx_mailtrap._client import MAX_BODY_CHARS

TOKEN = "test-token"  # noqa: S105  # pragma: allowlist secret

MESSAGES_URL = "https://mailtrap.io/api/accounts/1001/inboxes/77/messages"
MESSAGE_URL = f"{MESSAGES_URL}/4242"
SANDBOX_INPUTS = {"api_token": TOKEN, "account_id": "1001", "sandbox_inbox_id": "77"}

SPAM_REPORT = {
    "report": {
        "ResponseCode": 2,
        "ResponseMessage": "Not spam",
        "ResponseVersion": "1.2",
        "Score": 1.2,
        "Spam": False,
        "Threshold": 5,
        "Details": [
            {"Pts": 1.2, "RuleName": "HTML_IMAGE_ONLY_16", "Description": "HTML: images with 1400-1600 bytes of words"}
        ],
    }
}
HTML_ANALYSIS = {
    "report": {
        "status": "success",
        "errors": [
            {
                "error_line": 12,
                "rule_name": "css-display-flex",
                "email_clients": {"desktop": ["Outlook 2016"], "mobile": [], "web": ["Yahoo! Mail"]},
            }
        ],
    }
}


def test_component_identifiers_are_stable():
    assert MailtrapListSandboxMessagesComponent.name == "MailtrapListSandboxMessages"
    assert MailtrapGetSandboxMessageComponent.name == "MailtrapGetSandboxMessage"
    assert MailtrapCheckSandboxMessageComponent.name == "MailtrapCheckSandboxMessage"


def test_list_sandbox_messages_returns_one_row_per_message(mailtrap_api, sandbox_message):
    mailtrap_api.add("GET", MESSAGES_URL, [sandbox_message(), sandbox_message(id=4243, subject="Second")])
    component = MailtrapListSandboxMessagesComponent(**SANDBOX_INPUTS, search="Welcome", page=2)
    data = asyncio.run(component.mailtrap_list_sandbox_messages())

    assert mailtrap_api.calls[-1].params == {"search": "Welcome", "page": 2}
    assert data.data["page"] == 2
    assert data.data["messages"][0] == {
        "id": 4242,
        "subject": "Welcome",
        "from_email": "hello@acme.com",
        "from_name": "Acme",
        "to_email": "jane@example.com",
        "to_name": "Jane",
        "sent_at": "2026-10-21T10:00:00+00:00",
        "is_read": False,
        "size": "1.2 KB",
    }
    assert [message["id"] for message in data.data["messages"]] == [4242, 4243]


def test_list_sandbox_messages_sends_no_empty_search(mailtrap_api):
    mailtrap_api.add("GET", MESSAGES_URL, [])
    data = asyncio.run(MailtrapListSandboxMessagesComponent(**SANDBOX_INPUTS).mailtrap_list_sandbox_messages())
    assert mailtrap_api.calls[-1].params == {"page": 1}
    assert data.data["messages"] == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"account_id": ""}, "Account ID is required"),
        ({"sandbox_inbox_id": "x"}, "Sandbox Inbox ID must be a number"),
        ({"api_token": ""}, "Mailtrap API token is required"),
    ],
)
def test_sandbox_components_validate_before_any_request(mailtrap_api, overrides, message):
    for component_class in (MailtrapListSandboxMessagesComponent, MailtrapGetSandboxMessageComponent):
        component = component_class(**{**SANDBOX_INPUTS, "message_id": "4242", **overrides})
        method = getattr(component, component.outputs[0].method)
        with pytest.raises(ValueError, match=message):
            asyncio.run(method())
    assert mailtrap_api.calls == []


def test_get_sandbox_message_returns_both_bodies(mailtrap_api, sandbox_message):
    mailtrap_api.add("GET", MESSAGE_URL, sandbox_message())
    mailtrap_api.add("GET", f"{MESSAGE_URL}/body.txt", text="Hello Jane")
    mailtrap_api.add("GET", f"{MESSAGE_URL}/body.html", text="<p>Hello Jane</p>")
    data = asyncio.run(
        MailtrapGetSandboxMessageComponent(**SANDBOX_INPUTS, message_id="4242").mailtrap_get_sandbox_message()
    )

    assert data.data["subject"] == "Welcome"
    assert data.data["text_body"] == "Hello Jane"
    assert data.data["html_body"] == "<p>Hello Jane</p>"
    assert data.data["text_body_truncated"] is False


def test_get_sandbox_message_skips_missing_bodies_and_cuts_long_ones(mailtrap_api, sandbox_message):
    mailtrap_api.add("GET", MESSAGE_URL, sandbox_message(html_body_size=0))
    mailtrap_api.add("GET", f"{MESSAGE_URL}/body.txt", text="x" * (MAX_BODY_CHARS + 10))
    data = asyncio.run(
        MailtrapGetSandboxMessageComponent(**SANDBOX_INPUTS, message_id="4242").mailtrap_get_sandbox_message()
    )

    assert [call.url for call in mailtrap_api.calls] == [MESSAGE_URL, f"{MESSAGE_URL}/body.txt"]
    assert len(data.data["text_body"]) == MAX_BODY_CHARS
    assert data.data["text_body_truncated"] is True
    assert data.data["html_body"] == ""


def test_get_sandbox_message_reports_a_missing_message(mailtrap_api):
    mailtrap_api.add("GET", MESSAGE_URL, status=404)
    with pytest.raises(ValueError, match="Mailtrap API error 404: Not Found"):
        asyncio.run(
            MailtrapGetSandboxMessageComponent(**SANDBOX_INPUTS, message_id="4242").mailtrap_get_sandbox_message()
        )


def test_check_sandbox_message_returns_spam_score_and_html_issues(mailtrap_api):
    mailtrap_api.add("GET", f"{MESSAGE_URL}/spam_report", SPAM_REPORT)
    mailtrap_api.add("GET", f"{MESSAGE_URL}/analyze", HTML_ANALYSIS)
    component = MailtrapCheckSandboxMessageComponent(**SANDBOX_INPUTS, message_id="4242")
    data = asyncio.run(component.mailtrap_check_sandbox_message())

    assert data.data == {
        "message_id": 4242,
        "spam_score": 1.2,
        "spam_threshold": 5,
        "is_spam": False,
        "spam_rules": [
            {
                "rule_name": "HTML_IMAGE_ONLY_16",
                "points": 1.2,
                "description": "HTML: images with 1400-1600 bytes of words",
            }
        ],
        "html_analysis_status": "success",
        "html_issues": [
            {
                "rule_name": "css-display-flex",
                "line": 12,
                "desktop": ["Outlook 2016"],
                "mobile": [],
                "web": ["Yahoo! Mail"],
            }
        ],
        "html_analysis_message": None,
    }


def test_check_sandbox_message_keeps_a_failed_html_analysis(mailtrap_api):
    mailtrap_api.add("GET", f"{MESSAGE_URL}/spam_report", SPAM_REPORT)
    mailtrap_api.add("GET", f"{MESSAGE_URL}/analyze", {"report": {"status": "error", "msg": "Message has no HTML"}})
    component = MailtrapCheckSandboxMessageComponent(**SANDBOX_INPUTS, message_id="4242")
    data = asyncio.run(component.mailtrap_check_sandbox_message())

    assert data.data["html_analysis_status"] == "error"
    assert data.data["html_issues"] == []
    assert data.data["html_analysis_message"] == "Message has no HTML"
