"""Every component works as an Agent tool, with a unique name and no credential arguments."""

from __future__ import annotations

import asyncio

import lfx_mailtrap
import pytest
from lfx_mailtrap import MailtrapListSandboxMessagesComponent, MailtrapSendEmailComponent

TOKEN = "test-token"  # noqa: S105  # pragma: allowlist secret

EXPECTED_TOOLS = {
    "MailtrapCheckSandboxMessageComponent": ("mailtrap_check_sandbox_message", ["message_id"]),
    "MailtrapGetSandboxMessageComponent": ("mailtrap_get_sandbox_message", ["message_id"]),
    "MailtrapListSandboxMessagesComponent": ("mailtrap_list_sandbox_messages", ["search", "page"]),
    "MailtrapSendEmailComponent": ("mailtrap_send_email", ["to", "cc", "bcc", "subject", "text", "html"]),
}


def test_every_component_is_exported():
    assert sorted(lfx_mailtrap.__all__) == sorted(EXPECTED_TOOLS)


@pytest.mark.parametrize("class_name", sorted(EXPECTED_TOOLS))
def test_component_exposes_one_mailtrap_tool(class_name):
    # Tools read inputs the way a graph sets them (constructor kwargs).
    component = getattr(lfx_mailtrap, class_name)(api_token=TOKEN)
    tools = asyncio.run(component.to_toolkit())

    name, arguments = EXPECTED_TOOLS[class_name]
    assert [tool.name for tool in tools] == [name]
    assert list(tools[0].args_schema.model_json_schema()["properties"]) == arguments


def test_send_email_tool_call_reaches_mailtrap(mailtrap_api):
    mailtrap_api.add("POST", "https://send.api.mailtrap.io/api/send", {"success": True, "message_ids": ["mid-1"]})
    component = MailtrapSendEmailComponent(
        api_token=TOKEN,
        from_email="hello@acme.com",
        allowed_recipient_domains="example.com",
    )
    tool = asyncio.run(component.to_toolkit())[0]
    output = asyncio.run(tool.ainvoke({"to": ["jane@example.com"], "subject": "Hi", "text": "Hello"}))

    assert mailtrap_api.calls[-1].json["to"] == [{"email": "jane@example.com"}]
    assert output["message_ids"] == ["mid-1"]


def test_tool_errors_reach_the_agent_as_text(mailtrap_api):
    component = MailtrapSendEmailComponent(
        api_token=TOKEN,
        from_email="hello@acme.com",
        allowed_recipient_domains="example.com",
    )
    tool = asyncio.run(component.to_toolkit())[0]
    output = asyncio.run(tool.ainvoke({"to": ["eve@evil.io"], "subject": "Hi", "text": "Hello"}))

    assert "'eve@evil.io' is not allowed" in str(output)
    assert mailtrap_api.calls == []


def test_list_tool_gives_the_agent_every_field(mailtrap_api, sandbox_message):
    # A table reaches an Agent as truncated pandas text; the JSON result keeps every field.
    mailtrap_api.add("GET", "https://mailtrap.io/api/accounts/1001/inboxes/77/messages", [sandbox_message()])
    component = MailtrapListSandboxMessagesComponent(api_token=TOKEN, account_id="1001", sandbox_inbox_id="77")
    tool = asyncio.run(component.to_toolkit())[0]
    output = asyncio.run(tool.ainvoke({"search": "Welcome", "page": 1}))

    assert output["messages"][0]["from_email"] == "hello@acme.com"
    assert output["messages"][0]["to_email"] == "jane@example.com"
