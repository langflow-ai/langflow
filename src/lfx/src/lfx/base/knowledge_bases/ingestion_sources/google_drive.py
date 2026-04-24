"""Google Drive ingestion source (refresh-token based).

Lists and fetches files under a Google Drive folder (or across all
files the refresh-token-holder owns when no folder is specified).
Google-native formats (Docs, Sheets, Slides) are exported to their
OOXML equivalents so the existing text extractors handle them
unchanged.

Credentials layout:

* ``client_id_variable``     (default ``GOOGLE_OAUTH_CLIENT_ID``)
* ``client_secret_variable`` (default ``GOOGLE_OAUTH_CLIENT_SECRET``)
* ``refresh_token_variable`` (default ``GOOGLE_OAUTH_REFRESH_TOKEN``)

All three are resolved through the shared ``variable_service`` +
env fallback chain. See ``OAuthConnectorBase`` for the rationale
behind the refresh-token pattern.
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
from lfx.base.knowledge_bases.ingestion_sources.connector_base import (
    HTTP_STATUS_CLIENT_ERROR_FLOOR,
    OAuthConnectorBase,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # noqa: S105 — URL, not a secret
DRIVE_FILES_LIST_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_FILE_URL_TEMPLATE = "https://www.googleapis.com/drive/v3/files/{file_id}"
DRIVE_EXPORT_URL_TEMPLATE = "https://www.googleapis.com/drive/v3/files/{file_id}/export"

# Google-native MIME → export format (OOXML where possible so the
# existing text extractors pick them up without new dependencies).
GOOGLE_NATIVE_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pptx",
    ),
}

DEFAULT_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

# Google Drive Query Language fragments — see
# https://developers.google.com/drive/api/guides/search-files
_DRIVE_QUERY_NOT_TRASHED = "trashed=false"


class GoogleDriveSource(OAuthConnectorBase):
    """Walks a Google Drive folder and ingests every readable file.

    ``source_config`` shape::

        {
            "folder_id": "0B...",                  # optional — root if omitted
            "recursive": True,                     # default: True
            "extensions": ["pdf", "docx"],         # optional
            "max_file_size_bytes": 10_000_000,     # optional
            "include_shared_drives": False,        # default: False
            "client_id_variable": "GOOGLE_OAUTH_CLIENT_ID",
            "client_secret_variable": "GOOGLE_OAUTH_CLIENT_SECRET",  # pragma: allowlist secret
            "refresh_token_variable": "GOOGLE_OAUTH_REFRESH_TOKEN",  # pragma: allowlist secret
        }
    """

    source_type = SourceType.GOOGLE_DRIVE
    display_name = "Google Drive"
    description = "Ingest files from a Google Drive folder via OAuth refresh token."
    icon = "cloud"
    requires_credentials = True

    token_endpoint = GOOGLE_TOKEN_ENDPOINT
    default_client_id_variable = "GOOGLE_OAUTH_CLIENT_ID"
    default_client_secret_variable = "GOOGLE_OAUTH_CLIENT_SECRET"  # noqa: S105  # pragma: allowlist secret
    default_refresh_token_variable = "GOOGLE_OAUTH_REFRESH_TOKEN"  # noqa: S105  # pragma: allowlist secret

    async def validate_config(self) -> None:
        # Resolving all three up-front surfaces credential problems as
        # a 400 on the API route instead of a half-started ingestion.
        await self.resolve_required_secret(self._client_id_variable())
        await self.resolve_required_secret(self._client_secret_variable())
        await self.resolve_required_secret(self._refresh_token_variable())

        max_size = self.source_config.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES)
        if not isinstance(max_size, int) or max_size <= 0:
            msg = "max_file_size_bytes must be a positive integer."
            raise ValueError(msg)

    def _max_size(self) -> int:
        return int(self.source_config.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES))

    def _normalized_extensions(self) -> tuple[str, ...] | None:
        """Optional extension allow-list. ``None`` means "accept all"."""
        raw = self.source_config.get("extensions")
        if raw is None:
            return None
        normalized = tuple(ext.lower().lstrip(".") for ext in raw if ext)
        return normalized or None

    def _build_drive_query(self, parent_id: str | None) -> str:
        """Compose the ``q`` parameter for files.list."""
        parts = [_DRIVE_QUERY_NOT_TRASHED]
        if parent_id:
            parts.append(f"'{parent_id}' in parents")
        # Skip folders from the listing — we walk them recursively
        # ourselves to keep the traversal iterator-friendly.
        parts.append("mimeType != 'application/vnd.google-apps.folder'")
        return " and ".join(parts)

    async def _authed_client(self):
        """Return an httpx.AsyncClient with the Bearer header prebaked."""
        import httpx

        token = await self.get_access_token()
        return httpx.AsyncClient(
            timeout=60.0,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def list_items(self) -> AsyncIterator[IngestionItem]:
        import httpx

        folder_id = self.source_config.get("folder_id")
        recursive = bool(self.source_config.get("recursive", True))
        include_shared = bool(self.source_config.get("include_shared_drives", False))
        extensions = self._normalized_extensions()
        max_size = self._max_size()

        # BFS queue of folder ids to visit. ``None`` means "root".
        to_visit: list[str | None] = [folder_id]

        async with await self._authed_client() as client:
            while to_visit:
                parent = to_visit.pop(0)

                params: dict[str, Any] = {
                    "q": self._build_drive_query(parent),
                    "fields": "nextPageToken, files(id,name,mimeType,size,modifiedTime,webViewLink,parents)",
                    "pageSize": 200,
                }
                if include_shared:
                    params["supportsAllDrives"] = "true"
                    params["includeItemsFromAllDrives"] = "true"

                page_token: str | None = None
                while True:
                    if page_token:
                        params["pageToken"] = page_token
                    else:
                        params.pop("pageToken", None)

                    try:
                        response = await client.get(DRIVE_FILES_LIST_URL, params=params)
                    except httpx.HTTPError as exc:
                        msg = f"Drive files.list failed: {exc}"
                        raise ValueError(msg) from exc

                    if response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
                        msg = f"Drive files.list returned {response.status_code}: {response.text[:200]}"
                        raise ValueError(msg)

                    payload = response.json()
                    for drive_file in payload.get("files", []) or []:
                        file_id = drive_file.get("id")
                        name = drive_file.get("name") or file_id
                        mime = drive_file.get("mimeType") or ""
                        size = int(drive_file.get("size") or 0)
                        if size and size > max_size:
                            continue

                        # Decide the effective filename + apply the
                        # extension filter on the EXPECTED downloaded
                        # filename (post-export for Google-native).
                        effective_name = _effective_filename(name, mime)
                        if extensions is not None and "." in effective_name:
                            ext = effective_name.rsplit(".", 1)[-1].lower()
                            if ext not in extensions:
                                continue

                        yield IngestionItem(
                            item_id=str(file_id),
                            display_name=name,
                            mime_type=mime,
                            source_url=drive_file.get("webViewLink"),
                            source_metadata={
                                "google_drive_id": file_id,
                                "mime_type": mime,
                                "modified_time": drive_file.get("modifiedTime"),
                                "parents": drive_file.get("parents") or [],
                            },
                            size_bytes=size or None,
                        )

                    page_token = payload.get("nextPageToken")
                    if not page_token:
                        break

                # Recurse into subfolders if asked. Done as a separate
                # pass so the parent filter stays simple.
                if recursive:
                    folder_params: dict[str, Any] = {
                        "q": (
                            f"{_DRIVE_QUERY_NOT_TRASHED} and "
                            + (f"'{parent}' in parents and " if parent else "")
                            + "mimeType = 'application/vnd.google-apps.folder'"
                        ),
                        "fields": "nextPageToken, files(id)",
                        "pageSize": 200,
                    }
                    if include_shared:
                        folder_params["supportsAllDrives"] = "true"
                        folder_params["includeItemsFromAllDrives"] = "true"

                    folder_token: str | None = None
                    while True:
                        if folder_token:
                            folder_params["pageToken"] = folder_token
                        else:
                            folder_params.pop("pageToken", None)

                        folder_response = await client.get(DRIVE_FILES_LIST_URL, params=folder_params)
                        if folder_response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
                            break
                        folder_payload = folder_response.json()
                        for sub in folder_payload.get("files", []) or []:
                            sub_id = sub.get("id")
                            if sub_id:
                                to_visit.append(sub_id)
                        folder_token = folder_payload.get("nextPageToken")
                        if not folder_token:
                            break

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        import httpx

        file_id = item.item_id
        mime = (item.source_metadata or {}).get("mime_type") or ""
        export_spec = GOOGLE_NATIVE_EXPORT_MAP.get(mime)

        async with await self._authed_client() as client:
            if export_spec is not None:
                export_mime, export_ext = export_spec
                url = DRIVE_EXPORT_URL_TEMPLATE.format(file_id=quote(file_id, safe=""))
                params = {"mimeType": export_mime}
                response = await client.get(url, params=params)
                if response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
                    msg = f"Drive export of {item.display_name} failed ({response.status_code}): {response.text[:200]}"
                    raise ValueError(msg)
                file_name = f"{item.display_name}.{export_ext}"
                return IngestionItemContent(raw_bytes=bytes(response.content), file_name=file_name)

            url = DRIVE_FILE_URL_TEMPLATE.format(file_id=quote(file_id, safe=""))
            try:
                response = await client.get(url, params={"alt": "media"})
            except httpx.HTTPError as exc:
                msg = f"Drive download of {item.display_name} failed: {exc}"
                raise ValueError(msg) from exc

            if response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
                msg = f"Drive download of {item.display_name} returned {response.status_code}: {response.text[:200]}"
                raise ValueError(msg)

            return IngestionItemContent(raw_bytes=bytes(response.content), file_name=item.display_name)

    def describe(self) -> dict[str, Any]:
        base = super().describe()
        base["config"] = {
            "folder_id": self.source_config.get("folder_id"),
            "recursive": self.source_config.get("recursive", True),
            "extensions": list(self._normalized_extensions() or []) or None,
            "max_file_size_bytes": self._max_size(),
            "include_shared_drives": self.source_config.get("include_shared_drives", False),
            "client_id_variable": self._client_id_variable(),
            "client_secret_variable": self._client_secret_variable(),
            "refresh_token_variable": self._refresh_token_variable(),
        }
        return base


def _effective_filename(name: str, mime: str) -> str:
    """Return the filename the extractor will actually see post-download.

    For Google-native formats we append the export extension because
    the Drive API's ``name`` field omits it. Pure pass-through for
    regular binary files.
    """
    export_spec = GOOGLE_NATIVE_EXPORT_MAP.get(mime)
    if export_spec is not None:
        return f"{name}.{export_spec[1]}"
    if "." not in name and mime:
        guessed = mimetypes.guess_extension(mime)
        if guessed:
            return f"{name}{guessed}"
    return name
