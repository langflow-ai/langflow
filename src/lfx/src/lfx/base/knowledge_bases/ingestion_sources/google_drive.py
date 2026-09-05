"""Google Drive ingestion source, backed by a managed connection.

Reach
-----
This source runs on ``https://www.googleapis.com/auth/drive.file``, the
non-sensitive Drive scope, in line with
``design/dedicated-integrations/decisions/google-restricted-scopes.md``. It
therefore sees **only files this application created or the user explicitly
opened with it** — not the user's whole Drive. An empty listing is a normal
result for a correctly configured connection, not a failure. Reading arbitrary
Drive content needs a restricted scope and a Google security assessment, which
1.13 deliberately does not take on.

Identity
--------
Ingestion is a background job, so the source resolves its connection under a
non-interactive ``job_owner`` principal (see
``KBConnectorSource.execution_principal``). The portable deny floor refuses a
user-owned connection for such a principal unless the connection was created
with ``allow_non_interactive``, so a user has to opt in before a scheduled
ingestion can act on their behalf.

Registration
------------
This source is **not registered by default**. Nothing in langflow-base stamps an
execution principal on a background job until INT-6 lands, so every resolution
would fail closed with ``connection-not-authorized``. See
``ingestion_sources/__init__.py`` for the opt-in switch.

HTTP is deliberately plain ``httpx`` rather than ``google-api-python-client``:
lfx core must not take a Google SDK dependency, and Drive's REST surface for
list, download and export is three URLs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
    SourceType,
)
from lfx.base.knowledge_bases.ingestion_sources.connector_base import (
    HTTP_STATUS_CLIENT_ERROR_FLOOR,
    KBConnectorSource,
)
from lfx.integrations.errors import normalize_integration_error
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
PROVIDER_ID = "google"

FILES_URL = "https://www.googleapis.com/drive/v3/files"
LIST_FIELDS = "nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)"
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000
REQUEST_TIMEOUT_SECONDS = 60.0

GOOGLE_NATIVE_MIME_PREFIX = "application/vnd.google-apps."
# Export targets for the Google-native document types worth ingesting. Anything
# else Google-native (Forms, Sites, shortcuts, folders) has no useful text export
# and is skipped during listing rather than failing per item.
NATIVE_EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document": ("text/plain", ".txt"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.presentation": ("text/plain", ".txt"),
}
# Filename suffix appended to an exported native document so downstream text
# extraction, which dispatches on the extension, sees a usable one.
_DEFAULT_EXPORT_SUFFIX = ".txt"


class GoogleDriveSource(KBConnectorSource):
    """List and fetch Drive files visible to the app under ``drive.file``."""

    source_type = SourceType.GOOGLE_DRIVE
    display_name = "Google Drive"
    description = (
        "Ingests Google Drive files this application created or the user opened with it "
        "(the non-sensitive drive.file scope)."
    )
    icon = "google-drive"
    requires_credentials = True

    def __init__(self, user_id, source_config: dict[str, Any]) -> None:
        super().__init__(user_id=user_id, source_config=source_config)
        self._lease = None
        # Filled in during listing. This is a cache, NOT the source of truth:
        # `fetch_content` derives the export target from the item's own recorded
        # mime type, so a caller that fetches an item it did not list on this
        # instance (a resumed or batched ingestion) still exports correctly
        # instead of falling back to alt=media and getting fileNotDownloadable.
        self._export_targets: dict[str, str] = {}

    # -- configuration ----------------------------------------------------

    def _page_size(self) -> int:
        raw = self.source_config.get("page_size", DEFAULT_PAGE_SIZE)
        try:
            page_size = int(raw)
        except (TypeError, ValueError) as exc:
            msg = f"page_size must be an integer, got {raw!r}"
            raise ValueError(msg) from exc
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            msg = f"page_size must be between 1 and {MAX_PAGE_SIZE}, got {page_size}"
            raise ValueError(msg)
        return page_size

    def _query(self) -> str:
        """Build the Drive ``q`` filter from the configured folder/query."""
        clauses: list[str] = ["trashed = false"]
        folder_id = self.source_config.get("folder_id")
        if isinstance(folder_id, str) and folder_id and not folder_id.isspace():
            clauses.append(f"'{folder_id}' in parents")
        extra = self.source_config.get("query")
        if isinstance(extra, str) and extra and not extra.isspace():
            clauses.append(f"({extra})")
        return " and ".join(clauses)

    async def validate_config(self) -> None:
        """Fail before a job is spawned when the connection cannot be used."""
        if self.connection_handle() is None:
            msg = (
                "The Google Drive ingestion source requires a managed Google connection. "
                "Set source_config['connection'] to a handle such as 'google/work'."
            )
            raise ValueError(msg)
        self._page_size()
        # Resolving here surfaces connection-not-authorized, scope-missing and
        # auth-expired to the caller synchronously instead of inside the job.
        await self._token()

    # -- credential -------------------------------------------------------

    async def _token(self) -> str:
        if self._lease is None:
            self._lease = await self.resolve_connection_credential(frozenset({DRIVE_FILE_SCOPE}))
        return await self._lease.get_token()

    async def _request(self, client, url: str, *, params: dict[str, Any] | None = None):
        """One authorized Drive request, with the errors normalized."""
        import httpx

        headers = {"Authorization": f"Bearer {await self._token()}"}
        try:
            response = await client.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            raise normalize_integration_error(exc, provider=PROVIDER_ID) from exc
        if response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
            error = httpx.HTTPStatusError("Drive request failed", request=response.request, response=response)
            raise normalize_integration_error(error, provider=PROVIDER_ID)
        return response

    # -- listing ----------------------------------------------------------

    async def list_items(self) -> AsyncIterator[IngestionItem]:  # type: ignore[override]
        """Yield every app-visible Drive file, following pagination."""
        import httpx

        params = {
            "q": self._query(),
            "pageSize": self._page_size(),
            "fields": LIST_FIELDS,
        }
        if self.source_config.get("include_shared_drives"):
            params["includeItemsFromAllDrives"] = "true"
            params["supportsAllDrives"] = "true"

        async with httpx.AsyncClient() as client:
            page_token: str | None = None
            while True:
                page_params = dict(params)
                if page_token:
                    page_params["pageToken"] = page_token
                payload = (await self._request(client, FILES_URL, params=page_params)).json()
                for entry in payload.get("files", []):
                    item = self._to_item(entry)
                    if item is not None:
                        yield item
                page_token = payload.get("nextPageToken")
                if not page_token:
                    return

    def _to_item(self, entry: dict[str, Any]) -> IngestionItem | None:
        """Turn one Drive file resource into an item, or skip it."""
        mime_type = entry.get("mimeType") or ""
        if mime_type.startswith(GOOGLE_NATIVE_MIME_PREFIX):
            export = NATIVE_EXPORT_MIME_TYPES.get(mime_type)
            if export is None:
                # Folders, Forms, Sites, shortcuts: nothing to ingest.
                logger.debug("Skipping unsupported Google-native Drive type %s", mime_type)
                return None
            export_mime, _suffix = export
            self._export_targets[entry["id"]] = export_mime
        size = entry.get("size")
        return IngestionItem(
            item_id=entry["id"],
            display_name=entry.get("name") or entry["id"],
            mime_type=mime_type or None,
            source_url=entry.get("webViewLink"),
            source_metadata={
                "drive_file_id": entry["id"],
                "modified_time": entry.get("modifiedTime"),
                "mime_type": mime_type,
            },
            size_bytes=int(size) if isinstance(size, str) and size.isdigit() else None,
        )

    # -- content ----------------------------------------------------------

    def _file_name(self, item: IngestionItem, export_mime: str | None) -> str:
        """Return a filename whose extension text extraction can dispatch on."""
        name = item.display_name
        if export_mime is None:
            return name
        suffix = next(
            (suffix for mime, suffix in NATIVE_EXPORT_MIME_TYPES.values() if mime == export_mime),
            _DEFAULT_EXPORT_SUFFIX,
        )
        return name if name.endswith(suffix) else f"{name}{suffix}"

    def _export_target(self, item: IngestionItem) -> str | None:
        """Return the export MIME type for an item, or None to download it as-is.

        Derived from the mime type the item carries in its own metadata, so the
        answer does not depend on this instance having listed the item.
        """
        mime_type = (item.source_metadata or {}).get("mime_type") or item.mime_type or ""
        if isinstance(mime_type, str) and mime_type.startswith(GOOGLE_NATIVE_MIME_PREFIX):
            export = NATIVE_EXPORT_MIME_TYPES.get(mime_type)
            if export is not None:
                return export[0]
            msg = (
                f"Google Drive item {item.item_id} is a {mime_type}, which has no text export. "
                "Only Docs, Sheets and Slides can be ingested among the Google-native types."
            )
            raise ValueError(msg)
        return self._export_targets.get(item.item_id)

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        """Download a binary file, or export a Google-native document."""
        import httpx

        export_mime = self._export_target(item)
        file_id = quote(item.item_id, safe="")
        if export_mime is None:
            url = f"{FILES_URL}/{file_id}"
            params: dict[str, Any] = {"alt": "media"}
        else:
            url = f"{FILES_URL}/{file_id}/export"
            params = {"mimeType": export_mime}
        if self.source_config.get("include_shared_drives"):
            params["supportsAllDrives"] = "true"

        async with httpx.AsyncClient() as client:
            response = await self._request(client, url, params=params)

        return IngestionItemContent(
            raw_bytes=response.content,
            file_name=self._file_name(item, export_mime),
        )

    def describe(self) -> dict[str, Any]:
        """Config snapshot. The connection handle is a reference, not a secret."""
        base = super().describe()
        base["scope"] = DRIVE_FILE_SCOPE
        base["reach_note"] = (
            "Only files this application created or the user opened with it are visible under the drive.file scope."
        )
        return base
