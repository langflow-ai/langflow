"""Mailtrap: Get Sandbox Message -- one Email Sandbox message with its text and HTML bodies."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_mailtrap._client import (
    DOCUMENTATION_URL,
    account_id_input,
    api_token_input,
    call_mailtrap,
    require_id,
    require_token,
    sandbox_client,
    sandbox_inbox_input,
    sandbox_message_fields,
    truncate,
)


def _fetch_message(messages_api: Any, inbox_id: int, message_id: int) -> tuple[Any, str, str]:
    """Read the message, then only the bodies it has."""
    message = messages_api.show_message(inbox_id, message_id)
    text = messages_api.get_text_message(inbox_id, message_id) if message.text_body_size else None
    html = messages_api.get_html_message(inbox_id, message_id) if message.html_body_size else None
    return message, "" if text is None else str(text), "" if html is None else str(html)


class MailtrapGetSandboxMessageComponent(Component):
    display_name = "Mailtrap: Get Sandbox Message"
    description = "Get one message from a Mailtrap Email Sandbox inbox, with its text and HTML bodies."
    documentation = DOCUMENTATION_URL
    icon = "Mailtrap"
    name = "MailtrapGetSandboxMessage"

    inputs = [
        api_token_input(),
        account_id_input(),
        sandbox_inbox_input(for_sending=False),
        MessageTextInput(
            name="message_id",
            display_name="Message ID",
            required=True,
            tool_mode=True,
            info="The Sandbox message ID, as listed by List Sandbox Messages.",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.
        Output(display_name="Message", name="message", method="mailtrap_get_sandbox_message"),
    ]

    async def mailtrap_get_sandbox_message(self) -> Data:
        """Return the message fields plus its bodies, each cut to a fixed length."""
        token = require_token(self.api_token)
        account_id = require_id(self.account_id, "Account ID")
        inbox_id = require_id(self.sandbox_inbox_id, "Sandbox Inbox ID")
        message_id = require_id(self.message_id, "Message ID")
        messages_api = sandbox_client(token, account_id).testing_api.messages
        message, text, html = await call_mailtrap(_fetch_message, messages_api, inbox_id, message_id)

        text_body, text_truncated = truncate(text)
        html_body, html_truncated = truncate(html)
        data = Data(
            data={
                **sandbox_message_fields(message),
                "text_body": text_body,
                "text_body_truncated": text_truncated,
                "html_body": html_body,
                "html_body_truncated": html_truncated,
            }
        )
        self.status = data
        return data
