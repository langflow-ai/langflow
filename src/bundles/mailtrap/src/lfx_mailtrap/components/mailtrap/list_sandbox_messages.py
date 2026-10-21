"""Mailtrap: List Sandbox Messages -- ``GET /api/accounts/{id}/inboxes/{id}/messages``."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import IntInput, MessageTextInput
from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_mailtrap._client import (
    DOCUMENTATION_URL,
    account_id_input,
    api_token_input,
    call_mailtrap,
    optional_text,
    require_id,
    require_token,
    sandbox_client,
    sandbox_inbox_input,
    sandbox_message_fields,
)

FIRST_PAGE = 1


class MailtrapListSandboxMessagesComponent(Component):
    display_name = "Mailtrap: List Sandbox Messages"
    description = "List the newest messages in a Mailtrap Email Sandbox inbox."
    documentation = DOCUMENTATION_URL
    icon = "Mailtrap"
    name = "MailtrapListSandboxMessages"

    inputs = [
        api_token_input(),
        account_id_input(),
        sandbox_inbox_input(for_sending=False),
        MessageTextInput(
            name="search",
            display_name="Search",
            tool_mode=True,
            info="Only list messages whose subject, To address or To name contains this text.",
        ),
        IntInput(
            name="page",
            display_name="Page",
            value=FIRST_PAGE,
            advanced=True,
            tool_mode=True,
            range_spec=RangeSpec(min=FIRST_PAGE, max=1000, step=1, step_type="int"),
            info="Page of up to 30 messages, newest first, starting at 1.",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.  The output is JSON rather than a
        # table: an Agent receives a table as truncated text, a JSON object in full.
        Output(display_name="Messages", name="messages", method="mailtrap_list_sandbox_messages"),
    ]

    async def mailtrap_list_sandbox_messages(self) -> Data:
        """Return the Sandbox messages, newest first, under ``messages``."""
        token = require_token(self.api_token)
        account_id = require_id(self.account_id, "Account ID")
        inbox_id = require_id(self.sandbox_inbox_id, "Sandbox Inbox ID")
        page = max(FIRST_PAGE, int(self.page or FIRST_PAGE))
        messages_api = sandbox_client(token, account_id).testing_api.messages
        messages = await call_mailtrap(
            messages_api.get_list, inbox_id, search=optional_text(self.search) or None, page=page
        )
        data = Data(data={"messages": [sandbox_message_fields(message) for message in messages], "page": page})
        self.status = data
        return data
