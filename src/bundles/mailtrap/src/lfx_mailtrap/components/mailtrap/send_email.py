"""Mailtrap: Send Email -- ``POST /api/send`` on the Email API or an Email Sandbox inbox."""

from __future__ import annotations

from typing import Any

import mailtrap as mt
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, MultilineInput, NestedDictInput, StrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_mailtrap._client import (
    DOCUMENTATION_URL,
    allowed_recipients_input,
    api_token_input,
    call_mailtrap,
    category_input,
    optional_text,
    parse_address,
    parse_addresses,
    require_token,
    sandbox_inbox_input,
    sending_client,
    stream_input,
    update_stream_fields,
)
from lfx_mailtrap._guardrail import assert_recipients_allowed


class MailtrapSendEmailComponent(Component):
    display_name = "Mailtrap: Send Email"
    description = "Send an email through Mailtrap, or into an Email Sandbox inbox for testing."
    documentation = DOCUMENTATION_URL
    icon = "Mailtrap"
    name = "MailtrapSendEmail"

    inputs = [
        api_token_input(),
        stream_input(),
        sandbox_inbox_input(),
        MessageTextInput(
            name="from_email",
            display_name="From",
            required=True,
            info="Sender on a verified sending domain, for example 'Acme <hello@acme.com>'. Sandbox accepts any.",
        ),
        MessageTextInput(
            name="to",
            display_name="To",
            is_list=True,
            required=True,
            tool_mode=True,
            info="Recipient addresses, for example 'jane@example.com' or 'Jane <jane@example.com>'.",
        ),
        MessageTextInput(
            name="cc",
            value=[],
            display_name="Cc",
            is_list=True,
            advanced=True,
            tool_mode=True,
            info="Carbon-copy addresses.",
        ),
        MessageTextInput(
            name="bcc",
            value=[],
            display_name="Bcc",
            is_list=True,
            advanced=True,
            tool_mode=True,
            info="Blind carbon-copy addresses.",
        ),
        MessageTextInput(
            name="subject",
            display_name="Subject",
            tool_mode=True,
            info="Required unless Template UUID is set.",
        ),
        MultilineInput(
            name="text",
            display_name="Text Body",
            tool_mode=True,
            info="Plain-text body. Set Text Body, HTML Body or both, unless Template UUID is set.",
        ),
        MultilineInput(
            name="html",
            display_name="HTML Body",
            advanced=True,
            tool_mode=True,
            info="HTML body.",
        ),
        StrInput(
            name="template_uuid",
            display_name="Template UUID",
            advanced=True,
            info="Send a Mailtrap email template. The template sets the subject, the body and the category.",
        ),
        NestedDictInput(
            name="template_variables",
            display_name="Template Variables",
            advanced=True,
            info="Values for the template's variables, as a JSON object.",
        ),
        category_input(),
        allowed_recipients_input(),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.
        Output(display_name="Result", name="result", method="mailtrap_send_email"),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return update_stream_fields(build_config, field_value, field_name)

    def _build_mail(self) -> mt.BaseMail:
        sender = parse_address(self.from_email, "From")
        to = parse_addresses(self.to)
        if not to:
            msg = "At least one recipient in To is required."
            raise ValueError(msg)
        cc = parse_addresses(self.cc)
        bcc = parse_addresses(self.bcc)
        assert_recipients_allowed([address.email for address in [*to, *cc, *bcc]], self.allowed_recipient_domains)

        subject = optional_text(self.subject)
        text = self.text or ""
        html = self.html or ""
        template_uuid = optional_text(self.template_uuid)
        if template_uuid:
            if subject or text.strip() or html.strip():
                msg = (
                    "A template sets its own subject and body. "
                    "Leave Subject, Text Body and HTML Body empty when Template UUID is set."
                )
                raise ValueError(msg)
            return mt.MailFromTemplate(
                sender=sender,
                to=to,
                cc=cc or None,
                bcc=bcc or None,
                template_uuid=template_uuid,
                template_variables=self.template_variables or None,
            )

        if not subject:
            msg = "Subject is required unless Template UUID is set."
            raise ValueError(msg)
        if not text.strip() and not html.strip():
            msg = "Text Body or HTML Body is required unless Template UUID is set."
            raise ValueError(msg)
        return mt.Mail(
            sender=sender,
            to=to,
            cc=cc or None,
            bcc=bcc or None,
            subject=subject,
            text=text or None,
            html=html or None,
            category=optional_text(self.category) or None,
        )

    async def mailtrap_send_email(self) -> Data:
        """Send one email and return Mailtrap's message IDs."""
        token = require_token(self.api_token)
        client = sending_client(token, self.sending_stream, self.sandbox_inbox_id)
        mail = self._build_mail()
        response = await call_mailtrap(client.send, mail)
        data = Data(
            data={
                "success": bool(response.get("success")),
                "message_ids": list(response.get("message_ids") or []),
                "sending_stream": self.sending_stream.lower(),
                "to": [address.email for address in mail.to],
            }
        )
        self.status = data
        return data
