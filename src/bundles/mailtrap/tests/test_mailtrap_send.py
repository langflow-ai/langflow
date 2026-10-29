"""Mailtrap: Send Email."""

from __future__ import annotations

import asyncio
import re

import pytest
from lfx_mailtrap import MailtrapSendEmailComponent
from lfx_mailtrap._guardrail import RecipientNotAllowedError

TOKEN = "test-token"  # noqa: S105  # pragma: allowlist secret

SEND_URL = "https://send.api.mailtrap.io/api/send"
BULK_SEND_URL = "https://bulk.api.mailtrap.io/api/send"
SANDBOX_SEND_URL = "https://sandbox.api.mailtrap.io/api/send/77"
SEND_OK = {"success": True, "message_ids": ["mid-1"]}


def send_component(**overrides) -> MailtrapSendEmailComponent:
    kwargs = {
        "api_token": TOKEN,
        "from_email": "Acme <hello@acme.com>",
        "to": ["Jane <jane@example.com>"],
        "subject": "Welcome",
        "text": "Hello Jane",
    }
    kwargs.update(overrides)
    return MailtrapSendEmailComponent(**kwargs)


def test_component_identifiers_are_stable():
    # Saved flows reference these; renaming them orphans every flow.
    assert MailtrapSendEmailComponent.__name__ == "MailtrapSendEmailComponent"
    assert MailtrapSendEmailComponent.name == "MailtrapSendEmail"


def test_send_email_posts_the_mail_to_the_transactional_stream(mailtrap_api):
    mailtrap_api.add("POST", SEND_URL, SEND_OK)
    result = asyncio.run(send_component(cc=["bob@example.com"]).mailtrap_send_email())

    call = mailtrap_api.calls[-1]
    assert call.headers["Authorization"] == "Bearer test-token"
    assert call.json == {
        "from": {"email": "hello@acme.com", "name": "Acme"},
        "to": [{"email": "jane@example.com", "name": "Jane"}],
        "cc": [{"email": "bob@example.com"}],
        "subject": "Welcome",
        "text": "Hello Jane",
        "category": "langflow",
    }
    assert result.data == {
        "success": True,
        "message_ids": ["mid-1"],
        "sending_stream": "transactional",
        "to": ["jane@example.com"],
    }


def test_send_email_uses_the_bulk_host_for_bulk(mailtrap_api):
    mailtrap_api.add("POST", BULK_SEND_URL, SEND_OK)
    result = asyncio.run(send_component(sending_stream="Bulk", category="").mailtrap_send_email())
    assert "category" not in mailtrap_api.calls[-1].json
    assert result.data["sending_stream"] == "bulk"


def test_send_email_sends_into_the_sandbox_inbox(mailtrap_api):
    mailtrap_api.add("POST", SANDBOX_SEND_URL, SEND_OK)
    result = asyncio.run(send_component(sending_stream="Sandbox", sandbox_inbox_id="77").mailtrap_send_email())
    assert mailtrap_api.calls[-1].url == SANDBOX_SEND_URL
    assert result.data["sending_stream"] == "sandbox"


def test_send_email_sends_a_template(mailtrap_api):
    mailtrap_api.add("POST", SEND_URL, SEND_OK)
    component = send_component(subject="", text="", template_uuid="tpl-1", template_variables={"name": "Jane"})
    asyncio.run(component.mailtrap_send_email())
    assert mailtrap_api.calls[-1].json == {
        "from": {"email": "hello@acme.com", "name": "Acme"},
        "to": [{"email": "jane@example.com", "name": "Jane"}],
        "template_uuid": "tpl-1",
        "template_variables": {"name": "Jane"},
    }


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"api_token": ""}, "Mailtrap API token is required"),
        ({"to": []}, "At least one recipient in To is required"),
        ({"from_email": ""}, "From is required"),
        ({"subject": ""}, "Subject is required unless Template UUID is set"),
        ({"text": "", "html": ""}, "Text Body or HTML Body is required"),
        ({"template_uuid": "tpl-1"}, "A template sets its own subject and body"),
        ({"sending_stream": "Sandbox"}, "Sandbox Inbox ID is required"),
        ({"sending_stream": "Sandbox", "sandbox_inbox_id": "inbox"}, "Sandbox Inbox ID must be a number"),
        ({"to": ["not-an-address"]}, "not a valid email address"),
    ],
)
def test_send_email_validates_before_any_request(mailtrap_api, overrides, message):
    with pytest.raises(ValueError, match=message):
        asyncio.run(send_component(**overrides).mailtrap_send_email())
    assert mailtrap_api.calls == []


def test_send_email_rejects_recipients_outside_the_allowed_domains(mailtrap_api):
    component = send_component(to=["jane@example.com"], bcc=["eve@evil.io"], allowed_recipient_domains="example.com")
    with pytest.raises(RecipientNotAllowedError, match=re.escape("eve@evil.io")):
        asyncio.run(component.mailtrap_send_email())
    assert mailtrap_api.calls == []


def test_send_email_reports_the_mailtrap_error(mailtrap_api):
    mailtrap_api.add("POST", SEND_URL, {"errors": ["Unauthorized sender domain"]}, status=403)
    with pytest.raises(ValueError, match="Mailtrap API error 403: Unauthorized sender domain"):
        asyncio.run(send_component().mailtrap_send_email())


def test_send_email_shows_the_sandbox_inbox_only_for_sandbox():
    component = send_component()
    build_config = {"sandbox_inbox_id": {"show": False, "required": False}}
    component.update_build_config(build_config, "Sandbox", "sending_stream")
    assert build_config["sandbox_inbox_id"]["show"] is True
