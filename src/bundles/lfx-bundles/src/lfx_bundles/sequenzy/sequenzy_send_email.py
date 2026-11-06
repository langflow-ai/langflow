"""Send a transactional email through Sequenzy."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data

from lfx_bundles.sequenzy.sequenzy_common import (
    DOCUMENTATION_URL,
    SequenzyAPIError,
    api_key_input,
    call_sequenzy,
    error_data,
    parse_json_object,
    text_value,
    timeout_input,
)


class SequenzySendEmailComponent(Component):
    """Send a saved transactional template by slug, or a subject and HTML body."""

    display_name = "Sequenzy Send Email"
    description = "Send a transactional email with Sequenzy, from a saved template or a subject and HTML body."
    documentation = f"{DOCUMENTATION_URL}/api-reference/transactional/send"
    icon = "Sequenzy"
    name = "SequenzySendEmail"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="to",
            display_name="To",
            info="The recipient's email address.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="slug",
            display_name="Template Slug",
            info="The slug of a saved transactional email. Leave empty to send the subject and body below.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="subject",
            display_name="Subject",
            info="The email subject. Required when no template slug is set.",
            tool_mode=True,
        ),
        MultilineInput(
            name="body",
            display_name="HTML Body",
            info="The email body as HTML. Required when no template slug is set.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="template_variables",
            display_name="Variables",
            info='A JSON object of template variables, such as {"name": "Ada"}.',
            tool_mode=True,
            advanced=True,
        ),
        MessageTextInput(
            name="idempotency_key",
            display_name="Idempotency Key",
            info="Optional. Retrying with the same key does not send the email twice.",
            advanced=True,
        ),
        timeout_input(),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="send_email"),
    ]

    def send_email(self) -> Data:
        to = text_value(self.to)
        slug = text_value(self.slug)
        subject = text_value(self.subject)
        html = text_value(self.body)
        if not to:
            return error_data(self, "Enter the recipient's email address.")
        if not slug and not (subject and html):
            return error_data(self, "Enter a template slug, or both a subject and an HTML body.")
        payload: dict[str, object] = {"to": to}
        if slug:
            payload["slug"] = slug
        else:
            payload["subject"] = subject
            payload["body"] = html
        idempotency_key = text_value(self.idempotency_key)
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        try:
            variables = parse_json_object(self.template_variables, "Variables")
            if variables:
                payload["variables"] = variables
            body = call_sequenzy(self, "POST", "/transactional/send", json_body=payload, extra_headers=headers)
        except SequenzyAPIError as exc:
            return error_data(self, str(exc))
        data = Data(text=f"Sent email to {to}.", data=body)
        self.status = data
        return data
