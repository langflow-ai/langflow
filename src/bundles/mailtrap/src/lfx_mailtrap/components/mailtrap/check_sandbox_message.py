"""Mailtrap: Check Sandbox Message -- the spam report and the HTML analysis of a Sandbox message."""

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
)


def _fetch_reports(messages_api: Any, inbox_id: int, message_id: int) -> tuple[Any, Any]:
    return (
        messages_api.get_spam_report(inbox_id, message_id),
        messages_api.get_html_analysis(inbox_id, message_id),
    )


class MailtrapCheckSandboxMessageComponent(Component):
    display_name = "Mailtrap: Check Sandbox Message"
    description = "Get the spam score and the HTML analysis of a Mailtrap Email Sandbox message."
    documentation = DOCUMENTATION_URL
    icon = "Mailtrap"
    name = "MailtrapCheckSandboxMessage"

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
        Output(display_name="Report", name="report", method="mailtrap_check_sandbox_message"),
    ]

    async def mailtrap_check_sandbox_message(self) -> Data:
        """Return the spam score, the spam rules that matched, and the HTML issues by email client."""
        token = require_token(self.api_token)
        account_id = require_id(self.account_id, "Account ID")
        inbox_id = require_id(self.sandbox_inbox_id, "Sandbox Inbox ID")
        message_id = require_id(self.message_id, "Message ID")
        messages_api = sandbox_client(token, account_id).testing_api.messages
        spam, analysis = await call_mailtrap(_fetch_reports, messages_api, inbox_id, message_id)

        data = Data(
            data={
                "message_id": message_id,
                "spam_score": spam.score,
                "spam_threshold": spam.threshold,
                "is_spam": spam.spam,
                "spam_rules": [
                    {"rule_name": detail.rule_name, "points": detail.pts, "description": detail.description}
                    for detail in spam.details
                ],
                "html_analysis_status": analysis.status,
                # A successful analysis lists issues; a failed one carries a message instead.
                "html_issues": [
                    {
                        "rule_name": issue.rule_name,
                        "line": issue.error_line,
                        "desktop": issue.email_clients.desktop,
                        "mobile": issue.email_clients.mobile,
                        "web": issue.email_clients.web,
                    }
                    for issue in getattr(analysis, "errors", None) or []
                ],
                "html_analysis_message": getattr(analysis, "msg", None),
            }
        )
        self.status = data
        return data
