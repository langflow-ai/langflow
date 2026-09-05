"""Shared Microsoft Graph v1.0 REST client for the lfx-microsoft bundle.

This module is public on purpose. The Graph triggers (TRG-6) fetch Outlook,
Calendar and OneDrive/SharePoint resources through the same delegated
connection, so ``request``/``paginate``/``download`` are a supported surface
rather than a private helper the trigger bundle would have to fork.

Design notes
------------
* Credentials never leave the :class:`~lfx.integrations.models.CredentialLease`.
  The bearer token is read per request and one -- and only one -- reactive
  re-resolve is attempted when Graph rejects the token.
* Failures are translated into the sanitized ``lfx.integrations.errors``
  vocabulary from the Graph error body, not from the status code alone,
  because Graph answers 403 both for a missing scope and for a denied
  resource.
* ``download`` follows the ``302`` to the preauthenticated
  ``@microsoft.graph.downloadUrl`` **without** the Authorization header and
  never returns, logs, or stores that URL.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal

import httpx
from lfx.integrations.errors import (
    ActionUnsupportedError,
    AuthExpiredError,
    IntegrationError,
    ProviderUnavailableError,
    RateLimitedError,
    ScopeMissingError,
    register_error_normalizer,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import TracebackType
    from typing import Self

    from lfx.integrations.models import CredentialLease

PROVIDER_ID = "microsoft"
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
DEFAULT_TIMEOUT_SECONDS = 30.0

# SharePoint and OneDrive throttling attributes traffic per application through
# this decoration; sending it keeps this bundle out of the anonymous bucket.
# See https://learn.microsoft.com/en-us/sharepoint/dev/general-development/
# how-to-avoid-getting-throttled-or-blocked-in-sharepoint-online
USER_AGENT = "NONISV|Langflow|lfx-microsoft/0.1.0"

HTTP_MOVED_PERMANENTLY = 301
HTTP_FOUND = 302
HTTP_SEE_OTHER = 303
HTTP_TEMPORARY_REDIRECT = 307
HTTP_PERMANENT_REDIRECT = 308
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_TOO_MANY_REQUESTS = 429
HTTP_NOT_IMPLEMENTED = 501
HTTP_SERVICE_UNAVAILABLE = 503

_REDIRECT_STATUSES = frozenset(
    {
        HTTP_MOVED_PERMANENTLY,
        HTTP_FOUND,
        HTTP_SEE_OTHER,
        HTTP_TEMPORARY_REDIRECT,
        HTTP_PERMANENT_REDIRECT,
    }
)

# Graph error codes that mean "this access token is no longer usable", as
# opposed to "this identity may not touch that resource".
_AUTH_ERROR_CODES = frozenset(
    {
        "invalidauthenticationtoken",
        "compacttoken parsing failed with error code: 80049217",
        "expiredauthenticationtoken",
        "tokenexpired",
        "unauthenticated",
    }
)
_AUTH_ERROR_PREFIXES = ("compacttoken", "invalidauthenticationtoken")

# Graph error codes that mean the caller is missing a permission rather than
# hitting a transient provider condition.
_SCOPE_ERROR_CODES = frozenset(
    {
        "accessdenied",
        "erroraccessdenied",
        "authorization_requestdenied",
        "authenticationerror",
        "forbidden",
        "notallowed",
    }
)

MAX_PAGE_SIZE = 999


def graph_error_code(payload: Any) -> str:
    """Return the lowercased ``error.code`` carried by a Graph error body."""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if not isinstance(error, dict):
        return ""
    code = error.get("code")
    return code.casefold() if isinstance(code, str) else ""


def _retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _decode(response: httpx.Response) -> Any:
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return None


def integration_error_for_response(response: httpx.Response) -> IntegrationError:
    """Map one Graph error response onto the sanitized error vocabulary."""
    status = response.status_code
    code = graph_error_code(_decode(response))
    if status == HTTP_UNAUTHORIZED or code in _AUTH_ERROR_CODES or code.startswith(_AUTH_ERROR_PREFIXES):
        return AuthExpiredError(provider=PROVIDER_ID, http_status=status)
    if status == HTTP_FORBIDDEN or code in _SCOPE_ERROR_CODES:
        return ScopeMissingError(provider=PROVIDER_ID)
    if status in {HTTP_TOO_MANY_REQUESTS, HTTP_SERVICE_UNAVAILABLE}:
        return RateLimitedError(
            provider=PROVIDER_ID,
            retry_after=_retry_after_seconds(response.headers),
            http_status=status,
        )
    if status in {HTTP_NOT_FOUND, HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_IMPLEMENTED}:
        return ActionUnsupportedError(provider=PROVIDER_ID, http_status=status)
    return ProviderUnavailableError(provider=PROVIDER_ID, http_status=status)


def normalize_graph_error(exc: BaseException) -> IntegrationError | None:
    """Bundle-owned normalizer registered for the ``microsoft`` provider."""
    if isinstance(exc, IntegrationError):
        return exc
    if isinstance(exc, httpx.HTTPStatusError):
        return integration_error_for_response(exc.response)
    if isinstance(exc, httpx.TransportError):
        return ProviderUnavailableError(provider=PROVIDER_ID)
    return None


register_error_normalizer(PROVIDER_ID, normalize_graph_error)


class GraphClient:
    """Delegated Microsoft Graph client bound to one credential lease."""

    def __init__(
        self,
        lease: CredentialLease,
        *,
        base_url: str = GRAPH_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._lease = lease
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        # A separate, credential-free client for preauthenticated download URLs.
        self._anonymous = httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close both underlying transports."""
        await self._client.aclose()
        await self._anonymous.aclose()

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith(("http://", "https://")):
            return path_or_url
        return f"{self._base_url}/{path_or_url.lstrip('/')}"

    async def _send(
        self,
        method: str,
        url: str,
        *,
        token: str,
        params: Mapping[str, Any] | None,
        json_body: Any,
        headers: Mapping[str, str] | None,
    ) -> httpx.Response:
        request_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            request_headers.update(headers)
        return await self._client.request(
            method,
            url,
            params=dict(params) if params else None,
            json=json_body,
            headers=request_headers,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
        allow_redirect: bool = False,
    ) -> httpx.Response:
        """Perform one authorized Graph call, re-authorizing at most once.

        ``allow_redirect`` returns the 3xx response untouched so a caller such
        as :meth:`download` can consume the preauthenticated location itself.
        """
        url = self._url(path)
        try:
            token = await self._lease.get_token()
            response = await self._send(method, url, token=token, params=params, json_body=json_body, headers=headers)
        except httpx.TransportError as exc:
            raise ProviderUnavailableError(provider=PROVIDER_ID) from exc

        if response.status_code in _REDIRECT_STATUSES and allow_redirect:
            return response
        if response.status_code < HTTP_BAD_REQUEST:
            return response

        error = integration_error_for_response(response)
        if not isinstance(error, AuthExpiredError):
            raise error

        # Exactly one reactive re-resolve; the lease refuses a second.
        token = await self._lease.get_token_after_auth_error(error)
        try:
            response = await self._send(method, url, token=token, params=params, json_body=json_body, headers=headers)
        except httpx.TransportError as exc:
            raise ProviderUnavailableError(provider=PROVIDER_ID) from exc
        if response.status_code in _REDIRECT_STATUSES and allow_redirect:
            return response
        if response.status_code >= HTTP_BAD_REQUEST:
            raise integration_error_for_response(response)
        return response

    async def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """GET one Graph resource and return its decoded JSON object."""
        response = await self.request("GET", path, params=params, headers=headers)
        payload = _decode(response)
        return payload if isinstance(payload, dict) else {}

    async def paginate(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Follow ``@odata.nextLink`` until ``limit`` items are collected.

        Returns the collected items and the next link that was *not* followed,
        so a caller can resume where the page budget ended.
        """
        items: list[dict[str, Any]] = []
        next_link: str | None = None
        page_params: Mapping[str, Any] | None = params
        target = self._url(path)
        while True:
            payload = await self.get_json(target, params=page_params, headers=headers)
            page = payload.get("value")
            if isinstance(page, list):
                items.extend(entry for entry in page if isinstance(entry, dict))
            next_link = payload.get("@odata.nextLink")
            if not isinstance(next_link, str) or not next_link:
                next_link = None
                break
            if limit is not None and len(items) >= limit:
                break
            target = next_link
            # The next link already carries every query parameter.
            page_params = None
        if limit is not None and len(items) > limit:
            items = items[:limit]
        return items, next_link

    async def download(
        self,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
    ) -> bytes:
        """Download driveItem content through its preauthenticated redirect.

        Graph answers ``/content`` with a ``302`` to a short-lived
        ``@microsoft.graph.downloadUrl``. That URL is itself a credential: it
        is fetched without the Authorization header, is never returned to the
        caller, and is never written to a log or a Data payload.

        ``max_bytes`` is a memory bound, not a post-hoc trim: the body is
        streamed and the connection is dropped as soon as the cap is
        reached, so a 2 GB driveItem never lands in the process.
        """
        response = await self.request("GET", path, headers=headers, allow_redirect=True)
        if response.status_code not in _REDIRECT_STATUSES:
            content = response.content
            if max_bytes is not None and len(content) > max_bytes:
                return content[:max_bytes]
            return content
        location = response.headers.get("location")
        # The redirect target is chosen by Graph, but it is still an
        # attacker-influenceable header on a response we then fetch, so it
        # must at least be an absolute TLS URL: no http:// downgrade, no
        # file:// or other scheme, no relative path resolved against a base
        # we did not choose.
        if not location or not location.startswith("https://"):
            raise ProviderUnavailableError(provider=PROVIDER_ID, http_status=response.status_code)
        return await self._stream_download(location, headers=headers, max_bytes=max_bytes)

    async def _stream_download(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        max_bytes: int | None,
    ) -> bytes:
        """Read a preauthenticated download URL, stopping at ``max_bytes``."""
        chunks: list[bytes] = []
        remaining = max_bytes
        try:
            async with self._anonymous.stream(
                "GET",
                url,
                headers=dict(headers) if headers else None,
            ) as download:
                if download.status_code >= HTTP_BAD_REQUEST:
                    await download.aread()
                    raise integration_error_for_response(download)
                async for chunk in download.aiter_bytes():
                    if remaining is None:
                        chunks.append(chunk)
                        continue
                    if remaining <= 0:
                        break
                    chunks.append(chunk[:remaining])
                    remaining -= len(chunk)
        except httpx.TransportError as exc:
            raise ProviderUnavailableError(provider=PROVIDER_ID) from exc
        return b"".join(chunks)


def odata_params(
    *,
    top: int | None = None,
    select: Sequence[str] | None = None,
    filter_expression: str | None = None,
    search: str | None = None,
    order_by: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the OData query string shared by the read actions."""
    params: dict[str, Any] = {}
    if top is not None:
        params["$top"] = max(1, min(int(top), MAX_PAGE_SIZE))
    if select:
        cleaned = [item for item in (entry.strip() for entry in select) if item]
        if cleaned:
            params["$select"] = ",".join(cleaned)
    if filter_expression:
        params["$filter"] = filter_expression
    if search:
        params["$search"] = f'"{search}"'
    if order_by:
        params["$orderby"] = order_by
    if extra:
        params.update({key: value for key, value in extra.items() if value is not None})
    return params


def drive_root(drive_id: str = "", site_id: str = "") -> str:
    """Return the Graph drive prefix for the requested files scope.

    A drive id wins over a site id: both name the same kind of resource and
    Graph offers no combined form.
    """
    if drive_id:
        return f"/drives/{drive_id}"
    if site_id:
        return f"/sites/{site_id}/drive"
    return "/me/drive"


def drive_children_path(root: str, item_id: str = "", path: str = "") -> str:
    """Return the ``children`` collection for an item id, a path, or the root."""
    if item_id:
        return f"{root}/items/{item_id}/children"
    if path:
        return f"{root}/root:/{path.strip('/')}:/children"
    return f"{root}/root/children"


def drive_item_path(root: str, item_id: str = "", path: str = "", *, suffix: str = "") -> str:
    """Return one driveItem address, optionally with a ``/content`` suffix.

    Path-addressed items use Graph's ``root:/<path>:`` form, where the suffix
    follows the closing colon.
    """
    if item_id:
        return f"{root}/items/{item_id}{suffix}"
    if path:
        return f"{root}/root:/{path.strip('/')}:{suffix}"
    return f"{root}/root{suffix}"


def prefer_header(time_zone: str | None, *, body_as_text: bool = False) -> dict[str, str]:
    """Build the Outlook ``Prefer`` header for timezone and body preferences."""
    preferences: list[str] = []
    if time_zone:
        preferences.append(f'outlook.timezone="{time_zone}"')
    if body_as_text:
        preferences.append("outlook.body-content-type=text")
    return {"Prefer": ", ".join(preferences)} if preferences else {}


ContentType = Literal["text", "html"]
