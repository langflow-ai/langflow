"""Send an email from an Atomic Mail inbox."""

from __future__ import annotations

import json
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.atomicmail.atomicmail_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    AtomicMailAPIError,
    atomicmail_call,
    split_addresses,
)


def _sent_ids(result: dict[str, Any]) -> dict[str, str]:
    """Pick the id and thread id of the stored message out of a send answer, when it has them."""
    try:
        answer = json.loads(str(result.get("text") or ""))
        for name, payload, _ in answer["methodResponses"]:
            if name == "Email/set":
                created = next(iter(payload["created"].values()))
                return {"message_id": str(created["id"]), "thread_id": str(created["threadId"])}
    except (ValueError, KeyError, TypeError, AttributeError, StopIteration):
        pass
    return {}


class AtomicMailSendEmailComponent(Component):
    """Send one plain-text email from the inbox. This sends real mail."""

    display_name = "Atomic Mail Send Email"
    description = "Send an email from your Atomic Mail inbox, an email inbox built for AI agents."
    documentation = DOCUMENTATION_URL
    icon = "Mail"
    name = "AtomicMailSendEmail"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Atomic Mail API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="to",
            display_name="To",
            info="The recipient's email address. Separate several addresses with commas.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="subject",
            display_name="Subject",
            info="The subject line.",
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="body",
            display_name="Body",
            info="The plain-text body of the message.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="cc",
            display_name="CC",
            info="Addresses to copy. Separate several addresses with commas.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="from_name",
            display_name="From Name",
            info="The display name shown to the recipient, such as Anna from Acme. The address is always the inbox's.",
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Atomic Mail to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="send_email"),
    ]

    async def send_email(self) -> Data:
        """Send the message and return a short confirmation as ``text``."""
        try:
            recipients = split_addresses(self.to)
            if not recipients:
                msg = "Enter a recipient, such as anna@example.com."
                raise AtomicMailAPIError(msg)
            subject = str(self.subject or "").strip()
            body = str(self.body or "")
            if not subject and not body.strip():
                msg = "Enter a subject or a body: Atomic Mail does not send an empty message."
                raise AtomicMailAPIError(msg)
            result = await atomicmail_call(
                "send_email",
                {
                    "to": recipients,
                    "subject": subject,
                    "body": body,
                    "cc": split_addresses(self.cc),
                    "from_name": str(self.from_name or "").strip(),
                },
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
            )
        except AtomicMailAPIError as exc:
            await logger.aerror(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        sent = Data(
            text=f"Sent to {', '.join(recipients)}: {subject}",
            data={"to": recipients, "subject": subject, **_sent_ids(result)},
        )
        self.status = sent
        return sent
