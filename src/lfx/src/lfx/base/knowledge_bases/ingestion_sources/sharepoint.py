"""SharePoint ingestion source via Microsoft Graph.

Walks a SharePoint document library under a specific site + drive
and fetches every readable file. Reuses all of
``MicrosoftGraphSource``'s OAuth plumbing — only the list / fetch
URLs differ from OneDrive.

``source_config`` shape::

    {
        "site_id": "contoso.sharepoint.com,<site-guid>,<web-guid>",
        "drive_id": "<drive-id>",  # optional — default drive if omitted
        "folder_path": "General",  # optional — root if omitted
        "recursive": True,
        "extensions": ["pdf", "docx"],
        "max_file_size_bytes": 10_000_000,
        ...MS Graph OAuth variable references (see MicrosoftGraphSource)
    }

Acquiring ``site_id``: call ``GET /sites/{hostname}:/{site-path}``
against Graph with an interactive token once, capture the returned
``id``. That triple is stable across sessions.
"""

from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
    SourceType,
)
from lfx.base.knowledge_bases.ingestion_sources.connector_base import HTTP_STATUS_CLIENT_ERROR_FLOOR
from lfx.base.knowledge_bases.ingestion_sources.microsoft_graph import MicrosoftGraphSource

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

DEFAULT_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024


class SharePointSource(MicrosoftGraphSource):
    source_type = SourceType.SHAREPOINT
    display_name = "SharePoint"
    description = "Ingest files from a SharePoint document library via OAuth refresh token."
    icon = "cloud"

    async def validate_config(self) -> None:
        await super().validate_config()

        if not self.source_config.get("site_id"):
            msg = (
                "SharePointSource requires a 'site_id' in source_config. "
                "Obtain it by calling GET /sites/{hostname}:/{site-path} "
                "against Microsoft Graph once."
            )
            raise ValueError(msg)

        max_size = self.source_config.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES)
        if not isinstance(max_size, int) or max_size <= 0:
            msg = "max_file_size_bytes must be a positive integer."
            raise ValueError(msg)

    def _max_size(self) -> int:
        return int(self.source_config.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES))

    def _normalized_extensions(self) -> tuple[str, ...] | None:
        raw = self.source_config.get("extensions")
        if raw is None:
            return None
        normalized = tuple(ext.lower().lstrip(".") for ext in raw if ext)
        return normalized or None

    def _drive_prefix(self) -> str:
        """Graph endpoint prefix for the configured site + drive.

        When ``drive_id`` is omitted, falls back to the site's default
        document library.
        """
        site_id = self.source_config["site_id"]
        drive_id = self.source_config.get("drive_id")
        if drive_id:
            return f"/drives/{quote(drive_id, safe='')}"
        return f"/sites/{quote(site_id, safe='')}/drive"

    def _children_path(self, folder_path: str | None) -> str:
        prefix = self._drive_prefix()
        if not folder_path:
            return f"{prefix}/root/children"
        normalized = folder_path.strip("/")
        return f"{prefix}/root:/{quote(normalized, safe='/')}:/children"

    async def list_items(self) -> AsyncIterator[IngestionItem]:
        import httpx

        starting_path = self.source_config.get("folder_path")
        recursive = bool(self.source_config.get("recursive", True))
        extensions = self._normalized_extensions()
        max_size = self._max_size()

        to_visit: list[tuple[str | None, str]] = [(starting_path, self._children_path(starting_path))]
        async with await self.authed_client() as client:
            while to_visit:
                parent_path, endpoint = to_visit.pop(0)

                next_link: str | None = None
                while True:
                    try:
                        response = await client.get(next_link) if next_link else await client.get(endpoint)
                    except httpx.HTTPError as exc:
                        msg = f"Graph {endpoint} failed: {exc}"
                        raise ValueError(msg) from exc

                    if response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
                        msg = f"Graph listing for {endpoint} returned {response.status_code}: {response.text[:200]}"
                        raise ValueError(msg)

                    payload = response.json()
                    for drive_item in payload.get("value") or []:
                        name = drive_item.get("name") or drive_item.get("id")
                        item_id = drive_item.get("id")
                        size = int(drive_item.get("size") or 0)
                        child_path = f"{parent_path}/{name}" if parent_path else f"/{name}"

                        if drive_item.get("folder"):
                            if recursive:
                                to_visit.append((child_path, self._children_path(child_path)))
                            continue

                        if size > max_size:
                            continue

                        if extensions is not None and "." in name:
                            ext = name.rsplit(".", 1)[-1].lower()
                            if ext not in extensions:
                                continue

                        yield IngestionItem(
                            item_id=str(item_id),
                            display_name=name,
                            mime_type=(drive_item.get("file") or {}).get("mimeType") or mimetypes.guess_type(name)[0],
                            source_url=drive_item.get("webUrl"),
                            source_metadata={
                                "sharepoint_id": item_id,
                                "parent_path": parent_path,
                                "site_id": self.source_config["site_id"],
                                "drive_id": self.source_config.get("drive_id"),
                                "etag": drive_item.get("eTag"),
                                "last_modified": drive_item.get("lastModifiedDateTime"),
                            },
                            size_bytes=size or None,
                        )

                    next_link = payload.get("@odata.nextLink")
                    if not next_link:
                        break

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        import httpx

        drive_prefix = self._drive_prefix()
        url = f"{drive_prefix}/items/{quote(item.item_id, safe='')}/content"
        async with await self.authed_client() as client:
            try:
                response = await client.get(url)
            except httpx.HTTPError as exc:
                msg = f"SharePoint download of {item.display_name} failed: {exc}"
                raise ValueError(msg) from exc

            if response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
                msg = (
                    f"SharePoint download of {item.display_name} returned {response.status_code}: {response.text[:200]}"
                )
                raise ValueError(msg)

        return IngestionItemContent(raw_bytes=bytes(response.content), file_name=item.display_name)

    def describe(self) -> dict[str, Any]:
        base = super().describe()
        base["config"].update(
            {
                "site_id": self.source_config.get("site_id"),
                "drive_id": self.source_config.get("drive_id"),
                "folder_path": self.source_config.get("folder_path"),
                "recursive": self.source_config.get("recursive", True),
                "extensions": list(self._normalized_extensions() or []) or None,
                "max_file_size_bytes": self._max_size(),
            }
        )
        return base
