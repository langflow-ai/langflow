"""Send mail as the signed-in user (POST /me/sendMail)."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

from lfx.utils.file_path_security import component_file_access_scopes, enforce_local_file_access

from lfx_microsoft.base import (
    BoolInput,
    Data,
    FileInput,
    MessageTextInput,
    MicrosoftGraphComponent,
    MultilineInput,
    Output,
    as_list,
    recipients,
)
from lfx_microsoft.manifest import connection_input

HTTP_ACCEPTED = 202

# ``sendMail`` inlines every attachment as base64 inside the request body, and
# Graph caps that body at 4 MB. Microsoft documents 3 MB of raw bytes as the
# largest set of attachments that survives the base64 expansion; anything
# bigger needs an upload session against a draft message, which this action
# deliberately does not create. Refuse before reading the file so a 2 GB path
# never lands in memory on its way to a Graph 413.
MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024
MAX_MESSAGE_BYTES = 4 * 1024 * 1024


class OutlookSendComponent(MicrosoftGraphComponent):
    """Send an Outlook message through delegated Microsoft Graph permissions."""

    display_name = "Outlook: Send Mail"
    description = "Send an email as the connected Microsoft 365 user."
    documentation = "https://learn.microsoft.com/en-us/graph/api/user-sendmail"
    name = "OutlookSendMail"
    capability_id = "microsoft.outlook.send"

    inputs = [
        connection_input(capability_id),
        MessageTextInput(
            name="to",
            display_name="To",
            info="Recipient addresses.",
            is_list=True,
            required=True,
        ),
        MessageTextInput(name="cc", display_name="Cc", info="Carbon-copy addresses.", is_list=True),
        MessageTextInput(name="bcc", display_name="Bcc", info="Blind-carbon-copy addresses.", is_list=True),
        MessageTextInput(name="subject", display_name="Subject", required=True),
        MultilineInput(name="body", display_name="Body", required=True),
        BoolInput(
            name="body_is_html",
            display_name="Body is HTML",
            info="Send the body as HTML instead of plain text.",
            value=False,
        ),
        FileInput(
            name="attachments",
            display_name="Attachments",
            info="Files attached as Graph fileAttachment entries. Exchange Online caps message size.",
            is_list=True,
            advanced=True,
        ),
        BoolInput(
            name="save_to_sent_items",
            display_name="Save to Sent Items",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Result", name="result", method="send_mail")]

    def _attachments(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        remaining = MAX_ATTACHMENT_BYTES
        paths = getattr(self, "attachments", None) or []
        if isinstance(paths, str):
            paths = [paths]
        for raw_path in paths:
            resolved = enforce_local_file_access(
                Path(self.resolve_path(raw_path)), scope_ids=component_file_access_scopes(self)
            )
            if resolved.stat().st_size > remaining:
                msg = (
                    f"Attachments exceed the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB that Microsoft Graph "
                    f"accepts inline on sendMail (reached at {resolved.name!r}). Send fewer or smaller files, "
                    f"or share a link instead."
                )
                raise ValueError(msg)
            with resolved.open("rb") as attachment:
                payload = attachment.read(remaining + 1)
            if len(payload) > remaining:
                msg = "Attachments exceed Microsoft Graph's inline size limit. Send fewer or smaller files."
                raise ValueError(msg)
            remaining -= len(payload)
            entries.append(
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": resolved.name,
                    "contentBytes": base64.b64encode(payload).decode("ascii"),
                }
            )
        return entries

    def _message(self) -> dict[str, Any]:
        message: dict[str, Any] = {
            "subject": self.subject,
            "body": {
                "contentType": "html" if self.body_is_html else "text",
                "content": self.body,
            },
            "toRecipients": recipients(self.to),
        }
        if cc := recipients(self.cc):
            message["ccRecipients"] = cc
        if bcc := recipients(self.bcc):
            message["bccRecipients"] = bcc
        if attachments := self._attachments():
            message["attachments"] = attachments
        # Include the body, recipients, JSON envelope and base64 expansion in
        # the request limit; a raw attachment budget alone is insufficient.
        payload = {"message": message, "saveToSentItems": bool(self.save_to_sent_items)}
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_MESSAGE_BYTES:
            msg = (
                "The message exceeds Microsoft Graph's 4 MiB inline request limit. Send a smaller body or attachments."
            )
            raise ValueError(msg)
        return message

    async def send_mail(self) -> Data:
        """Send the message and return the request echo plus the Graph status."""
        message = await asyncio.to_thread(self._message)
        lease = self.lease()
        async with self.action(lease) as client:
            response = await client.request(
                "POST",
                "/me/sendMail",
                json_body={"message": message, "saveToSentItems": bool(self.save_to_sent_items)},
            )
        # sendMail answers 202 Accepted with an empty body, so the output
        # carries the accepted request rather than a provider resource.
        result = Data(
            data={
                "accepted": response.status_code == HTTP_ACCEPTED,
                "status_code": response.status_code,
                "subject": self.subject,
                "to": as_list(self.to),
                "cc": as_list(self.cc),
                "bcc": as_list(self.bcc),
                "attachment_count": len(message.get("attachments", [])),
                "saved_to_sent_items": bool(self.save_to_sent_items),
            }
        )
        self.status = result.data
        return result
