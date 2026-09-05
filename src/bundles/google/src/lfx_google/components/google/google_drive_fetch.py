"""Drive: Fetch File (app files) — wave-1 action (INT-10, google.drive.fetch).

Like the listing action this runs on ``drive.file`` only, so it can fetch a file
the app created or the user opened with it and nothing else.

Google-native documents (Docs, Sheets, Slides) hold no bytes of their own and
have to be exported, so an ``export_mime_type`` switches the content call from
``files.get_media`` to ``files.export_media``.
"""

from __future__ import annotations

import base64
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._workspace_client import workspace_action
from ._workspace_inputs import DRIVE_FILE_SCOPE, google_connection_input

CAPABILITY = "google.drive.fetch"

METADATA_FIELDS = "id, name, mimeType, size, modifiedTime, webViewLink"
# Text-ish content is decoded for the flow; everything else is handed over
# base64-encoded so binary bytes survive the JSON boundary intact.
_TEXT_MIME_PREFIXES = ("text/",)
_TEXT_MIME_TYPES = frozenset(
    {
        "application/json",
        "application/xml",
        "application/rtf",
        "application/x-ndjson",
        "image/svg+xml",
    }
)


def _is_text(mime_type: str | None) -> bool:
    if not mime_type:
        return False
    base = mime_type.split(";", 1)[0].strip().casefold()
    return base.startswith(_TEXT_MIME_PREFIXES) or base in _TEXT_MIME_TYPES


class GoogleDriveFetchComponent(Component):
    """Fetch one Drive file's metadata and content under ``drive.file``."""

    display_name = "Drive: Fetch File (app files)"
    description = (
        "Fetches one Google Drive file this app created or the user opened with it. "
        "Google-native documents are exported to the requested MIME type."
    )
    documentation: str = "https://docs.langflow.org/bundles-google"
    icon = "GoogleDrive"
    name = "GoogleDriveFetchComponent"

    inputs = [
        google_connection_input(required_scopes=[DRIVE_FILE_SCOPE], capabilities=[CAPABILITY]),
        MessageTextInput(name="file_id", display_name="File ID", required=True),
        MessageTextInput(
            name="export_mime_type",
            display_name="Export MIME Type",
            info="Set for Docs, Sheets and Slides, for example 'text/plain' or 'application/pdf'.",
        ),
        BoolInput(
            name="acknowledge_abuse",
            display_name="Acknowledge Abuse",
            info="Download a file Google flagged as potentially malicious.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="supports_all_drives",
            display_name="Supports All Drives",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="File", name="file", method="fetch_file")]

    async def fetch_file(self) -> Data:
        """Return the file's metadata plus its content or exported bytes."""
        if not self.file_id:
            msg = "file_id is required."
            raise ValueError(msg)
        file_id = self.file_id
        export_mime_type = (self.export_mime_type or "").strip()
        supports_all_drives = bool(self.supports_all_drives)

        metadata_params: dict[str, Any] = {"fileId": file_id, "fields": METADATA_FIELDS}
        media_params: dict[str, Any] = {"fileId": file_id}
        if supports_all_drives:
            metadata_params["supportsAllDrives"] = True
            media_params["supportsAllDrives"] = True
        if not export_mime_type and self.acknowledge_abuse:
            media_params["acknowledgeAbuse"] = True

        async with workspace_action(self, capability=CAPABILITY, api="drive", version="v3") as service:
            metadata = await service.execute(lambda client: client.files().get(**metadata_params))
            if export_mime_type:
                content_bytes = await service.execute(
                    lambda client: client.files().export_media(fileId=file_id, mimeType=export_mime_type)
                )
            else:
                content_bytes = await service.execute(lambda client: client.files().get_media(**media_params))

        content_mime = export_mime_type or metadata.get("mimeType")
        record: dict[str, Any] = dict(metadata)
        if _is_text(content_mime):
            record["content"] = bytes(content_bytes).decode("utf-8", errors="replace")
            record["content_encoding"] = "utf-8"
        else:
            record["content"] = base64.b64encode(bytes(content_bytes)).decode("ascii")
            record["content_encoding"] = "base64"
        record["content_mime_type"] = content_mime
        record["exported"] = bool(export_mime_type)

        data = Data(data=record)
        self.status = data
        return data
