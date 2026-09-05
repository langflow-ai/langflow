"""Fetch one driveItem's metadata and content from OneDrive or SharePoint."""

from __future__ import annotations

import base64
from typing import Any

from lfx_microsoft.base import Data, IntInput, MessageTextInput, MicrosoftGraphComponent, Output
from lfx_microsoft.graph import drive_item_path, drive_root
from lfx_microsoft.manifest import connection_input

DEFAULT_MAX_BYTES = 10 * 1024 * 1024

# driveItem properties worth keeping; @microsoft.graph.downloadUrl is
# deliberately absent -- it is a preauthenticated credential with a lifetime of
# minutes and must never reach a flow payload or a log.
_METADATA_FIELDS = (
    "id",
    "name",
    "size",
    "webUrl",
    "eTag",
    "cTag",
    "createdDateTime",
    "lastModifiedDateTime",
    "parentReference",
    "file",
    "folder",
)


class SharePointFetchComponent(MicrosoftGraphComponent):
    """Download one file from OneDrive or a SharePoint document library."""

    display_name = "SharePoint/OneDrive: Fetch Item"
    description = "Fetch a file's metadata and content from OneDrive or SharePoint."
    documentation = "https://learn.microsoft.com/en-us/graph/api/driveitem-get-content"
    name = "SharePointFetchItem"
    capability_id = "microsoft.files.fetch"

    inputs = [
        connection_input(capability_id),
        MessageTextInput(name="item_id", display_name="Item ID", info="The driveItem id to fetch."),
        MessageTextInput(
            name="path",
            display_name="Item Path",
            info="File path relative to the drive root, used when no item id is given.",
        ),
        MessageTextInput(
            name="drive_id",
            display_name="Drive ID",
            info="Another user's or a shared drive. Requires Files.Read.All.",
        ),
        MessageTextInput(
            name="site_id",
            display_name="Site ID",
            info="A SharePoint site's default document library. Requires Sites.Read.All.",
        ),
        MessageTextInput(
            name="range",
            display_name="Byte Range",
            info="Optional HTTP Range value, for example bytes=0-1023.",
            advanced=True,
        ),
        IntInput(
            name="max_bytes",
            display_name="Max Bytes",
            info="Truncate the download at this many bytes.",
            value=DEFAULT_MAX_BYTES,
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="File", name="file", method="fetch_item")]

    def _scope_inputs(self) -> dict[str, str]:
        """Inputs the conditional-scope pre-flight predicates read."""
        scope: dict[str, str] = {}
        if drive_id := (self.drive_id or "").strip():
            scope["drive_id"] = drive_id
        if site_id := (self.site_id or "").strip():
            scope["site_id"] = site_id
        return scope

    async def fetch_item(self) -> Data:
        """Return the item's metadata plus its (optionally truncated) content."""
        scope = self._scope_inputs()
        root = drive_root(scope.get("drive_id", ""), scope.get("site_id", ""))
        item_id = (self.item_id or "").strip()
        path = (self.path or "").strip()
        if not item_id and not path:
            msg = "Provide either an item id or a path to fetch."
            raise ValueError(msg)
        metadata_path = drive_item_path(root, item_id, path)
        content_path = drive_item_path(root, item_id, path, suffix="/content")
        headers = {"Range": self.range.strip()} if (self.range or "").strip() else None
        max_bytes = int(self.max_bytes or DEFAULT_MAX_BYTES)

        lease = self.lease()
        async with self.action(lease, scope) as client:
            metadata = await client.get_json(metadata_path)
            content = await client.download(content_path, headers=headers, max_bytes=max_bytes)

        payload: dict[str, Any] = {field: metadata[field] for field in _METADATA_FIELDS if field in metadata}
        payload["content_bytes"] = len(content)
        payload["truncated"] = len(content) >= max_bytes
        payload["content_base64"] = base64.b64encode(content).decode("ascii")
        try:
            payload["text"] = content.decode("utf-8")
        except UnicodeDecodeError:
            payload["text"] = None
        result = Data(data=payload)
        self.status = f"{payload.get('name', 'item')} ({payload['content_bytes']} bytes)"
        return result
