"""OneDrive ingestion source via Microsoft Graph.

Walks a OneDrive folder (personal or work/school) and fetches every
readable file. Uses the refresh-token OAuth flow from
``MicrosoftGraphSource``.

``source_config`` shape::

    {
        "folder_path": "/Documents/Research",  # optional — root if omitted
        "recursive": True,
        "extensions": ["pdf", "docx"],
        "max_file_size_bytes": 10_000_000,
        "client_id_variable": "MICROSOFT_OAUTH_CLIENT_ID",
        "client_secret_variable": "MICROSOFT_OAUTH_CLIENT_SECRET",  # pragma: allowlist secret
        "refresh_token_variable": "MICROSOFT_OAUTH_REFRESH_TOKEN",  # pragma: allowlist secret
        "tenant_id_variable": "MICROSOFT_OAUTH_TENANT_ID",
        "scope": "offline_access Files.Read.All",
    }
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


class OneDriveSource(MicrosoftGraphSource):
    source_type = SourceType.ONEDRIVE
    display_name = "OneDrive"
    description = "Ingest files from a Microsoft OneDrive folder via OAuth refresh token."
    icon = "cloud"

    async def validate_config(self) -> None:
        await super().validate_config()
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

    def _children_path(self, folder_path: str | None) -> str:
        """Resolve the Graph path for a folder's ``/children`` call.

        Graph's path-addressing is ``/me/drive/root:{path}:/children``
        when a path is given and ``/me/drive/root/children`` for the
        drive root. URL-quoting keeps folder names with spaces +
        unicode safe.
        """
        if not folder_path:
            return "/me/drive/root/children"
        normalized = folder_path.strip("/")
        return f"/me/drive/root:/{quote(normalized, safe='/')}:/children"

    async def list_items(self) -> AsyncIterator[IngestionItem]:
        import httpx

        starting_path = self.source_config.get("folder_path")
        recursive = bool(self.source_config.get("recursive", True))
        extensions = self._normalized_extensions()
        max_size = self._max_size()

        # Queue of ``(folder_path_or_None, graph_endpoint)`` tuples.
        to_visit: list[tuple[str | None, str]] = [(starting_path, self._children_path(starting_path))]
        client_ctx = await self.authed_client()
        async with client_ctx as client:
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
                                "onedrive_id": item_id,
                                "parent_path": parent_path,
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

        file_id = item.item_id
        async with await self.authed_client() as client:
            url = f"/me/drive/items/{quote(file_id, safe='')}/content"
            try:
                response = await client.get(url)
            except httpx.HTTPError as exc:
                msg = f"OneDrive download of {item.display_name} failed: {exc}"
                raise ValueError(msg) from exc

            if response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
                msg = f"OneDrive download of {item.display_name} returned {response.status_code}: {response.text[:200]}"
                raise ValueError(msg)

        return IngestionItemContent(raw_bytes=bytes(response.content), file_name=item.display_name)

    def describe(self) -> dict[str, Any]:
        base = super().describe()
        base["config"].update(
            {
                "folder_path": self.source_config.get("folder_path"),
                "recursive": self.source_config.get("recursive", True),
                "extensions": list(self._normalized_extensions() or []) or None,
                "max_file_size_bytes": self._max_size(),
            }
        )
        return base
