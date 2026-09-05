"""Microsoft Graph ingestion source backed by a Microsoft connection.

``OneDriveSource`` and ``SharePointSource`` both walk a Microsoft Graph
drive, so the walk lives here once. Credentials come from a dedicated
Microsoft connection (``source_config["connection"]``, e.g.
``microsoft/work``) resolved through the host's connection resolver: no
refresh token is stored in a Langflow variable and no token exchange
happens in this module.

Ingestion runs detached from the request that started it, so the
resolution is stamped with a non-interactive ``job_owner`` principal.
A connection that has not opted into non-interactive use is refused
with ``ConnectionNotAuthorizedError`` before any Graph call is made.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import quote

import httpx

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

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
# SharePoint and OneDrive attribute throttling per application through this
# decoration; sending it keeps ingestion out of the anonymous bucket.
USER_AGENT = "NONISV|Langflow|langflow-kb-ingestion/1.0"
DEFAULT_PAGE_SIZE = 200
MAX_ITEMS_DEFAULT = 5000
# Same ceiling and the same ``max_file_size_bytes`` config key FolderSource
# uses, so a KB operator tunes one number regardless of where the bytes come
# from. Oversized items are skipped during the walk (Graph reports driveItem
# ``size``) and the download is capped again on the way in, because the item
# may have grown between the listing and the fetch.
DEFAULT_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
HTTP_FOUND = 302
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class MicrosoftGraphSource(OAuthConnectorBase):
    """Walk one Microsoft Graph drive and fetch its files.

    Subclasses supply :meth:`drive_root`, the Graph path prefix that
    selects a personal OneDrive or a SharePoint document library.
    """

    display_name = "Microsoft Graph"
    description = "Ingest files from a Microsoft Graph drive."
    requires_credentials = True

    connection_provider: ClassVar[str] = "microsoft"
    connection_required_scopes: ClassVar[tuple[str, ...]] = ("Files.Read",)

    # Legacy variable names, kept so an existing bring-your-own-refresh-token
    # configuration keeps working while connections roll out.
    token_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/token"  # noqa: S105 - a URL, not a secret
    default_client_id_variable = "MICROSOFT_CLIENT_ID"
    default_client_secret_variable = "MICROSOFT_CLIENT_SECRET"  # noqa: S105  # pragma: allowlist secret
    default_refresh_token_variable = "MICROSOFT_REFRESH_TOKEN"  # noqa: S105 - a variable name, not a secret

    def drive_root(self) -> str:
        """Return the Graph path prefix for this source's drive."""
        raise NotImplementedError

    # --- configuration -------------------------------------------------

    @property
    def folder_path(self) -> str:
        value = self.source_config.get("folder_path") or ""
        return str(value).strip("/") if isinstance(value, str) else ""

    @property
    def item_id(self) -> str:
        value = self.source_config.get("item_id") or ""
        return str(value) if isinstance(value, str) else ""

    @property
    def recursive(self) -> bool:
        return bool(self.source_config.get("recursive", True))

    @property
    def max_items(self) -> int:
        value = self.source_config.get("max_items")
        return int(value) if isinstance(value, int) and value > 0 else MAX_ITEMS_DEFAULT

    @property
    def max_file_size_bytes(self) -> int:
        value = self.source_config.get("max_file_size_bytes")
        return int(value) if isinstance(value, int) and value > 0 else DEFAULT_MAX_FILE_SIZE_BYTES

    async def validate_config(self) -> None:
        """Fail before a background job is spawned when the config cannot work."""
        if self.connection_handle():
            # Parses the handle and checks its provider; resolution itself
            # happens on first use.
            self.connection_lease()
            return
        await self.resolve_required_secret(self._client_id_variable())
        await self.resolve_required_secret(self._client_secret_variable())
        await self.resolve_required_secret(self._refresh_token_variable())

    # --- Graph plumbing ------------------------------------------------

    def _children_path(self, item_id: str, path: str) -> str:
        root = self.drive_root()
        if item_id:
            return f"{root}/items/{item_id}/children"
        if path:
            return f"{root}/root:/{quote(path)}:/children"
        return f"{root}/root/children"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response, context: str) -> None:
        if response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
            msg = f"Microsoft Graph {context} failed with {response.status_code}: {response.text[:200]}"
            raise OSError(msg)

    async def _get_json(self, client: httpx.AsyncClient, url: str, token: str) -> dict[str, Any]:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        self._raise_for_status(response, "listing")
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    # --- KBIngestionSource ---------------------------------------------

    async def list_items(self) -> AsyncIterator[IngestionItem]:  # type: ignore[override]
        """Yield every file under the configured folder.

        Folders are descended into when ``recursive`` is set; only files
        are yielded, because a folder has no bytes to ingest.

        The token is re-read once per Graph request rather than once per
        walk: ``get_access_token`` is cached (and, for a connection handle,
        lease-backed), so this costs nothing on a short run but keeps a
        long ingestion from outliving the token it started with.
        """
        emitted = 0
        # (item_id, path) pairs still to enumerate; the first entry is the
        # configured starting point.
        pending: list[tuple[str, str]] = [(self.item_id, self.folder_path)]
        async with self._client() as client:
            while pending and emitted < self.max_items:
                current_id, current_path = pending.pop(0)
                url = f"{GRAPH_BASE_URL}{self._children_path(current_id, current_path)}?$top={DEFAULT_PAGE_SIZE}"
                while url and emitted < self.max_items:
                    payload = await self._get_json(client, url, await self.get_access_token())
                    for entry in payload.get("value") or []:
                        if not isinstance(entry, dict):
                            continue
                        if entry.get("folder") is not None:
                            child_id = str(entry.get("id") or "")
                            # Without an id there is nothing to descend
                            # into: queueing ("", "") would re-list the
                            # drive root and walk in a circle.
                            if self.recursive and child_id:
                                pending.append((child_id, ""))
                            continue
                        if entry.get("file") is None:
                            continue
                        size = entry.get("size")
                        if isinstance(size, int) and size > self.max_file_size_bytes:
                            # Skipped for the same reason FolderSource skips
                            # them: the bytes would blow the memory and
                            # embedding budgets for one item.
                            continue
                        emitted += 1
                        yield self._to_item(entry)
                        if emitted >= self.max_items:
                            break
                    next_link = payload.get("@odata.nextLink")
                    url = next_link if isinstance(next_link, str) else ""

    def _to_item(self, entry: dict[str, Any]) -> IngestionItem:
        file_info = entry.get("file") or {}
        parent = entry.get("parentReference") or {}
        return IngestionItem(
            item_id=str(entry.get("id") or ""),
            display_name=str(entry.get("name") or entry.get("id") or ""),
            mime_type=file_info.get("mimeType") if isinstance(file_info, dict) else None,
            source_url=entry.get("webUrl") if isinstance(entry.get("webUrl"), str) else None,
            size_bytes=entry.get("size") if isinstance(entry.get("size"), int) else None,
            source_metadata={
                "drive_id": parent.get("driveId") if isinstance(parent, dict) else None,
                "parent_id": parent.get("id") if isinstance(parent, dict) else None,
                "last_modified": entry.get("lastModifiedDateTime"),
                "source_type": getattr(self, "source_type", SourceType.ONEDRIVE).value,
            },
        )

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        """Download one driveItem's bytes.

        Graph answers ``/content`` with a redirect to a short-lived
        preauthenticated URL. That URL is itself a credential, so it is
        followed without the access token and is never stored, returned, or
        logged.
        """
        token = await self.get_access_token()
        url = f"{GRAPH_BASE_URL}{self.drive_root()}/items/{item.item_id}/content"
        async with self._client() as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            if response.status_code not in _REDIRECT_STATUSES:
                self._raise_for_status(response, "download")
                return IngestionItemContent(
                    raw_bytes=response.content[: self.max_file_size_bytes],
                    file_name=item.display_name,
                )
            location = response.headers.get("location")
            # Only an absolute TLS target is worth following: the location is
            # a header on a response, and this leg carries no bearer token to
            # protect.
            if not location or not location.startswith("https://"):
                msg = f"Microsoft Graph returned {response.status_code} without a usable download location."
                raise OSError(msg)
            raw_bytes = await self._stream_capped(client, location)
        return IngestionItemContent(raw_bytes=raw_bytes, file_name=item.display_name)

    async def _stream_capped(self, client: httpx.AsyncClient, url: str) -> bytes:
        """Read a preauthenticated download URL, stopping at the size cap.

        The cap is a memory bound, not a trim: the connection is dropped as
        soon as it is reached, so an item that grew past the size Graph
        reported during the walk cannot pull an unbounded body into the
        ingestion worker.
        """
        chunks: list[bytes] = []
        remaining = self.max_file_size_bytes
        async with client.stream("GET", url) as download:
            if download.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
                await download.aread()
                self._raise_for_status(download, "download")
            async for chunk in download.aiter_bytes():
                if remaining <= 0:
                    break
                chunks.append(chunk[:remaining])
                remaining -= len(chunk)
        return b"".join(chunks)

    def describe(self) -> dict[str, Any]:
        """Expose the connection handle, which is a reference and not a secret.

        The scopes reported are the *configured* ones -- a SharePoint site
        needs ``Sites.Read.All`` and an explicit drive id needs
        ``Files.Read.All`` -- so what is advertised here matches what
        resolution will actually demand.
        """
        base = super().describe()
        base.setdefault("config", {})
        handle = self.connection_handle()
        if handle:
            base["config"]["connection"] = handle
            base["config"]["required_scopes"] = list(self.required_connection_scopes())
        return base
