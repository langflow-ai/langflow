"""Gmail: Send Email — wave-1 connection-backed action (INT-10, google.gmail.send)."""

from __future__ import annotations

import base64
import io
import mimetypes
from email.message import EmailMessage
from pathlib import Path

from googleapiclient.http import MediaIoBaseUpload
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, FileInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx.utils.file_path_security import component_file_access_scopes, enforce_local_file_access

from ._workspace_client import workspace_action
from ._workspace_inputs import GMAIL_SEND_SCOPE, google_connection_input

CAPABILITY = "google.gmail.send"

# Gmail rejects a JSON `messages.send` body above 5 MB. With attachments the
# message goes through the /upload media variant instead, which accepts 35 MB.
SIMPLE_SEND_LIMIT_BYTES = 5 * 1024 * 1024
UPLOAD_SEND_LIMIT_BYTES = 35 * 1024 * 1024
RFC822_MIME_TYPE = "message/rfc822"


def _addresses(raw: object) -> list[str]:
    """Normalize a list, a comma-separated string, or nothing into addresses."""
    if raw is None or raw == "":
        return []
    values = raw if isinstance(raw, list) else str(raw).split(",")
    return [item.strip() for item in (str(value) for value in values) if item.strip()]


def _attachment_paths(raw: object) -> list[str]:
    if raw is None or raw == "":
        return []
    values = raw if isinstance(raw, list) else [raw]
    return [str(value) for value in values if value]


class GmailSendComponent(Component):
    """Send mail from the connected user's own mailbox on ``gmail.send`` only."""

    display_name = "Gmail: Send Email"
    description = "Sends an email from the connected Google account's mailbox."
    documentation: str = "https://docs.langflow.org/bundles-google"
    icon = "Gmail"
    name = "GmailSendComponent"

    inputs = [
        google_connection_input(required_scopes=[GMAIL_SEND_SCOPE], capabilities=[CAPABILITY]),
        MessageTextInput(
            name="to",
            display_name="To",
            info="Recipient addresses.",
            is_list=True,
            required=True,
        ),
        MessageTextInput(name="cc", display_name="Cc", info="Carbon-copy addresses.", is_list=True, advanced=True),
        MessageTextInput(
            name="bcc", display_name="Bcc", info="Blind carbon-copy addresses.", is_list=True, advanced=True
        ),
        MessageTextInput(name="subject", display_name="Subject", required=True),
        MessageTextInput(
            name="body",
            display_name="Body",
            info="Plain text or HTML body.",
            required=True,
        ),
        BoolInput(
            name="body_is_html",
            display_name="Body Is HTML",
            info="Send the body as text/html instead of text/plain.",
            value=False,
        ),
        FileInput(
            name="attachments",
            display_name="Attachments",
            info="Files to attach. With attachments the message is sent through the /upload variant (35 MB cap).",
            file_types=[],
            is_list=True,
            advanced=True,
        ),
        MessageTextInput(
            name="thread_id",
            display_name="Thread ID",
            info="Reply into an existing Gmail thread.",
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Message", name="message", method="send_message")]

    def _build_mime_message(self) -> EmailMessage:
        message = EmailMessage()
        to_addresses = _addresses(self.to)
        if not to_addresses:
            msg = "At least one recipient address is required."
            raise ValueError(msg)
        message["To"] = ", ".join(to_addresses)
        cc = _addresses(self.cc)
        if cc:
            message["Cc"] = ", ".join(cc)
        bcc = _addresses(self.bcc)
        if bcc:
            message["Bcc"] = ", ".join(bcc)
        message["Subject"] = self.subject or ""
        body = self.body or ""
        if self.body_is_html:
            message.set_content("This message requires an HTML-capable mail client.")
            message.add_alternative(body, subtype="html")
        else:
            message.set_content(body)

        for path_str in _attachment_paths(self.attachments):
            # An attachment path is a tenant-controlled input and the bytes leave the
            # deployment by email, so containment matters more here than for a component
            # that merely reads a file into the graph: without this an editor could mail
            # itself /etc/passwd, the SQLite DB, or another tenant's upload. No-op unless
            # LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS is on, matching every other file-reading
            # component (data_source/csv_to_data.py, base/data/base_file.py, ibm/db2_security.py).
            path = enforce_local_file_access(
                Path(self.resolve_path(path_str)),
                scope_ids=component_file_access_scopes(self),
            )
            payload = path.read_bytes()
            guessed, _ = mimetypes.guess_type(path.name)
            maintype, _, subtype = (guessed or "application/octet-stream").partition("/")
            message.add_attachment(payload, maintype=maintype, subtype=subtype or "octet-stream", filename=path.name)
        return message

    async def send_message(self) -> Data:
        """Send one message and return the ``users.messages.send`` response."""
        message = self._build_mime_message()
        raw_bytes = message.as_bytes()
        has_attachments = bool(_attachment_paths(self.attachments))
        limit = UPLOAD_SEND_LIMIT_BYTES if has_attachments else SIMPLE_SEND_LIMIT_BYTES
        if len(raw_bytes) > limit:
            msg = (
                f"The message is {len(raw_bytes)} bytes, above Gmail's {limit}-byte limit for this send mode. "
                "Send fewer or smaller attachments."
            )
            raise ValueError(msg)

        body: dict[str, object] = {}
        thread_id = (self.thread_id or "").strip() if self.thread_id else ""
        if thread_id:
            body["threadId"] = thread_id

        if has_attachments:
            # The /upload media variant: the RFC 2822 bytes travel as the media
            # body rather than base64 inside JSON, which is what lifts the size
            # ceiling. The upload object is rebuilt per attempt so a retry after
            # an auth refresh reads the stream from the start.
            def request(client, *, body=body, raw_bytes=raw_bytes):
                media = MediaIoBaseUpload(io.BytesIO(raw_bytes), mimetype=RFC822_MIME_TYPE, resumable=False)
                return client.users().messages().send(userId="me", body=body, media_body=media)
        else:
            json_body = dict(body)
            json_body["raw"] = base64.urlsafe_b64encode(raw_bytes).decode("ascii")

            def request(client, *, body=json_body):
                return client.users().messages().send(userId="me", body=body)

        async with workspace_action(self, capability=CAPABILITY, api="gmail", version="v1") as service:
            response = await service.execute(request)

        data = Data(data=dict(response))
        self.status = data
        return data
