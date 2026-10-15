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

import asyncio
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import quote, urljoin

import httpx

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
    SourceType,
)
from lfx.base.knowledge_bases.ingestion_sources.connector_base import OAuthConnectorBase
from lfx.integrations.errors import AuthExpiredError
from lfx.utils.ssrf_httpx import ssrf_protected_strict_httpx_client_kwargs_for_url
from lfx.utils.url_redaction import suppress_sensitive_http_logs

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
HTTP_UNAUTHORIZED = 401
HTTP_SUCCESS = 200
HTTP_PARTIAL_CONTENT = 206
HTTP_REDIRECT = 300
MAX_DOWNLOAD_REDIRECTS = 5
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
HTTP_BAD_REQUEST = 400


def _is_license_rejection(response: httpx.Response) -> bool:
    """Return whether Graph refused the call because the workload is unlicensed.

    Graph reports this as a bare ``400 BadRequest`` whose only signal is the
    message, for example ``Tenant does not have a SPO license.``
    """
    if response.status_code != HTTP_BAD_REQUEST:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    return isinstance(message, str) and "license" in message.casefold()


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
            return f"{root}/items/{quote(item_id, safe='!,')}/children"
        if path:
            return f"{root}/root:/{quote(path)}:/children"
        return f"{root}/root/children"

    def _client(self, **kwargs: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=60.0,
            **{**kwargs, "follow_redirects": False},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response, context: str) -> None:
        successful = HTTP_SUCCESS <= response.status_code < HTTP_REDIRECT
        if context == "download":
            successful = response.status_code in {HTTP_SUCCESS, HTTP_PARTIAL_CONTENT}
        if not successful:
            msg = f"Microsoft Graph {context} failed with {response.status_code}."
            # Downloads are streamed and their bodies are never read here; a
            # listing body is already in memory, so its error can name the one
            # setup failure Graph reports only in text.
            if context != "download" and _is_license_rejection(response):
                msg = (
                    f"Microsoft Graph {context} failed with {response.status_code}: the Microsoft 365 "
                    "tenant or user has no license for SharePoint Online and OneDrive. Assign a Microsoft 365 "
                    "license that includes them; retrying does not help."
                )
            raise OSError(msg)

    @staticmethod
    def _validate_graph_url(url: str) -> None:
        try:
            target = httpx.URL(url)
            base = httpx.URL(GRAPH_BASE_URL)
            if (
                (target.scheme, target.host, target.port) != (base.scheme, base.host, base.port)
                or target.userinfo
                or target.fragment
            ):
                raise ValueError
        except (ValueError, httpx.InvalidURL):
            msg = "Microsoft Graph returned an invalid listing URL."
            raise OSError(msg) from None

    async def _get_json(self, client: httpx.AsyncClient, url: str, token: str) -> dict[str, Any]:
        self._validate_graph_url(url)
        try:
            for attempt in range(2):
                response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
                if response.status_code == HTTP_UNAUTHORIZED and not attempt and self._lease is not None:
                    token = await self._lease.get_token_after_auth_error(
                        AuthExpiredError(provider="microsoft"), rejected_token=token
                    )
                    continue
                self._raise_for_status(response, "listing")
                payload = response.json()
                return payload if isinstance(payload, dict) else {}
        except httpx.TransportError:
            msg = "Microsoft Graph listing is temporarily unavailable."
            raise OSError(msg) from None
        return {}

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
        visited_folders: set[tuple[str, str]] = set()
        async with self._client() as client:
            while pending and emitted < self.max_items:
                current_id, current_path = pending.pop(0)
                if (current_id, current_path) in visited_folders:
                    continue
                visited_folders.add((current_id, current_path))
                url = f"{GRAPH_BASE_URL}{self._children_path(current_id, current_path)}?$top={DEFAULT_PAGE_SIZE}"
                visited_pages: set[str] = set()
                while url and emitted < self.max_items:
                    if url in visited_pages:
                        msg = "Microsoft Graph repeated a pagination URL."
                        raise OSError(msg)
                    visited_pages.add(url)
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

    @suppress_sensitive_http_logs()
    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        """Download one driveItem's bytes.

        Graph answers ``/content`` with a redirect to a short-lived
        preauthenticated URL. That URL is itself a credential, so it is
        followed without the access token and is never stored, returned, or
        logged.
        """
        token = await self.get_access_token()
        url = f"{GRAPH_BASE_URL}{self.drive_root()}/items/{quote(item.item_id, safe='!,')}/content"
        try:
            async with self._client() as client:
                for attempt in range(2):
                    async with client.stream("GET", url, headers={"Authorization": f"Bearer {token}"}) as response:
                        if response.status_code in _REDIRECT_STATUSES:
                            location = response.headers.get("location", "")
                            break
                        if response.status_code == HTTP_UNAUTHORIZED and not attempt and self._lease is not None:
                            token = await self._lease.get_token_after_auth_error(
                                AuthExpiredError(provider="microsoft"), rejected_token=token
                            )
                            continue
                        self._raise_for_status(response, "download")
                        raw_bytes = await self._read_capped(response)
                        return IngestionItemContent(raw_bytes=raw_bytes, file_name=item.display_name)
            raw_bytes = await self._stream_capped(location)
        except httpx.TransportError:
            msg = "Microsoft Graph download is temporarily unavailable."
            raise OSError(msg) from None
        return IngestionItemContent(raw_bytes=raw_bytes, file_name=item.display_name)

    async def _read_capped(self, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        remaining = self.max_file_size_bytes
        async for chunk in response.aiter_bytes():
            chunks.append(chunk[:remaining])
            remaining -= len(chunk)
            if remaining <= 0:
                break
        return b"".join(chunks)

    async def _stream_capped(self, url: str) -> bytes:
        """Read credential-free HTTPS redirects with a byte cap and SSRF protection."""
        for _ in range(MAX_DOWNLOAD_REDIRECTS + 1):
            try:
                target = httpx.URL(url)
                if target.scheme != "https" or not target.host or target.userinfo:
                    raise ValueError
                _, kwargs = await asyncio.to_thread(ssrf_protected_strict_httpx_client_kwargs_for_url, url)
            except (ValueError, httpx.InvalidURL):
                msg = "Microsoft Graph returned an unusable download location."
                raise OSError(msg) from None
            # Separate clients prevent cookies from leaking across redirect hops.
            async with self._client(**kwargs) as client, client.stream("GET", url) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        msg = "Microsoft Graph returned an unusable download location."
                        raise OSError(msg)
                    url = urljoin(url, location)
                    continue
                self._raise_for_status(response, "download")
                return await self._read_capped(response)
        msg = "Microsoft Graph exceeded the download redirect limit."
        raise OSError(msg)

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
