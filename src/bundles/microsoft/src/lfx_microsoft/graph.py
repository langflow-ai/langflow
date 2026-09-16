"""Shared Microsoft Graph v1.0 REST client for the lfx-microsoft bundle.

This module is public on purpose. The Graph triggers fetch Outlook,
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

import asyncio
import json
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote, urljoin

import httpx
from lfx.integrations.errors import (
    ActionUnsupportedError,
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
    ScopeMissingError,
    register_error_normalizer,
)
from lfx.utils.ssrf_httpx import ssrf_protected_strict_httpx_client_kwargs_for_url
from lfx.utils.url_redaction import suppress_sensitive_http_logs

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
HTTP_SUCCESS = 200
HTTP_PARTIAL_CONTENT = 206
HTTP_REDIRECT = 300
MAX_DOWNLOAD_REDIRECTS = 5
MAX_ERROR_BYTES = 64 * 1024
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_REQUEST_TIMEOUT = 408
HTTP_TOO_MANY_REQUESTS = 429
HTTP_NOT_IMPLEMENTED = 501
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_SERVER_ERROR_FLOOR = 500

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
_SCOPE_ERROR_CODES = frozenset({"insufficient_scope", "invalid_scope"})

# Graph error code for a user whose mailbox Exchange Online cannot serve: no
# Exchange Online license, or a mailbox that is inactive or hosted on-premises.
_MAILBOX_UNAVAILABLE_CODE = "mailboxnotenabledforrestapi"

MAX_PAGE_SIZE = 999


def _graph_error_field(payload: Any, field: str) -> str:
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if not isinstance(error, dict):
        return ""
    value = error.get(field)
    return value.casefold() if isinstance(value, str) else ""


def graph_error_code(payload: Any) -> str:
    """Return the lowercased ``error.code`` carried by a Graph error body."""
    return _graph_error_field(payload, "code")


def _setup_error(status: int, code: str, message: str) -> InvalidRequestError | None:
    """Recognize rejections caused by the tenant's Microsoft 365 setup.

    Graph reports an unlicensed workload as a bare ``400 BadRequest`` whose
    only signal is the message (for example ``Tenant does not have a SPO
    license.``), so that one case is matched on text. The provider's wording
    is never forwarded: the error carries fixed, sanitized text.
    """
    if code == _MAILBOX_UNAVAILABLE_CODE:
        return InvalidRequestError(
            "Microsoft Graph cannot reach this user's mailbox.",
            hint=(
                "Assign the user a Microsoft 365 license that includes Exchange Online; "
                "mailboxes that are inactive or hosted on-premises are not supported."
            ),
            provider=PROVIDER_ID,
            http_status=status,
        )
    if status == HTTP_BAD_REQUEST and "license" in message:
        return InvalidRequestError(
            "The Microsoft 365 tenant or user has no license for this service.",
            hint=(
                "Assign a Microsoft 365 license that includes the workload this action uses "
                "(SharePoint Online and OneDrive, Exchange Online, or Teams). "
                "Reconnecting or retrying does not help."
            ),
            provider=PROVIDER_ID,
            http_status=status,
        )
    return None


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
    payload = _decode(response)
    code = graph_error_code(payload)
    if (setup_error := _setup_error(status, code, _graph_error_field(payload, "message"))) is not None:
        return setup_error
    if status == HTTP_UNAUTHORIZED or code in _AUTH_ERROR_CODES or code.startswith(_AUTH_ERROR_PREFIXES):
        return AuthExpiredError(provider=PROVIDER_ID, http_status=status)
    if code in _SCOPE_ERROR_CODES:
        return ScopeMissingError(provider=PROVIDER_ID)
    if status == HTTP_FORBIDDEN:
        return ConnectionNotAuthorizedError(provider=PROVIDER_ID, reason="provider")
    if status in {HTTP_TOO_MANY_REQUESTS, HTTP_SERVICE_UNAVAILABLE}:
        return RateLimitedError(
            provider=PROVIDER_ID,
            retry_after=_retry_after_seconds(response.headers),
            http_status=status,
        )
    if status in {HTTP_NOT_FOUND, HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_IMPLEMENTED}:
        return ActionUnsupportedError(provider=PROVIDER_ID, http_status=status)
    # Any other 4xx except a timeout is Graph refusing this request as sent;
    # retrying the same call cannot succeed, so it must not read as a transient
    # outage.
    if HTTP_BAD_REQUEST <= status < HTTP_SERVER_ERROR_FLOOR and status != HTTP_REQUEST_TIMEOUT:
        return InvalidRequestError(provider=PROVIDER_ID, http_status=status)
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
        self._transport = transport
        self._timeout = timeout

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
        """Close the authorized Graph transport."""
        await self._client.aclose()

    def _url(self, path_or_url: str) -> str:
        base = httpx.URL(self._base_url)
        try:
            target = httpx.URL(path_or_url)
            if not target.is_absolute_url:
                target = httpx.URL(f"{self._base_url}/{path_or_url.lstrip('/')}")
            if (
                (target.scheme, target.host, target.port) != (base.scheme, base.host, base.port)
                or target.userinfo
                or target.fragment
            ):
                raise ProviderUnavailableError(provider=PROVIDER_ID)
        except httpx.InvalidURL:
            raise ProviderUnavailableError(provider=PROVIDER_ID) from None
        return str(target)

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
        request_headers = httpx.Headers(headers)
        request_headers["Authorization"] = f"Bearer {token}"
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
        if HTTP_SUCCESS <= response.status_code < HTTP_REDIRECT:
            return response

        error = integration_error_for_response(response)
        if not isinstance(error, AuthExpiredError):
            raise error

        # Exactly one reactive re-resolve; the lease refuses a second.
        token = await self._lease.get_token_after_auth_error(error, rejected_token=token)
        try:
            response = await self._send(method, url, token=token, params=params, json_body=json_body, headers=headers)
        except httpx.TransportError as exc:
            raise ProviderUnavailableError(provider=PROVIDER_ID) from exc
        if response.status_code in _REDIRECT_STATUSES and allow_redirect:
            return response
        if not HTTP_SUCCESS <= response.status_code < HTTP_REDIRECT:
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
        """Follow complete pages until at least ``limit`` items are collected.

        The final page is retained in full, so the returned continuation does
        not skip its remaining rows. The result can exceed the requested budget.
        """
        if limit is not None and limit <= 0:
            msg = "The result budget must be positive."
            raise ValueError(msg)
        items: list[dict[str, Any]] = []
        next_link: str | None = None
        page_params: Mapping[str, Any] | None = params
        target = self._url(path)
        visited: set[str] = set()
        while True:
            if target in visited:
                raise ProviderUnavailableError(provider=PROVIDER_ID)
            visited.add(target)
            payload = await self.get_json(target, params=page_params, headers=headers)
            page = payload.get("value")
            if isinstance(page, list):
                items.extend(entry for entry in page if isinstance(entry, dict))
            next_link = payload.get("@odata.nextLink")
            if not isinstance(next_link, str) or not next_link:
                next_link = None
                break
            next_link = self._url(next_link)
            if limit is not None and len(items) >= limit:
                break
            target = next_link
            # The next link already carries every query parameter.
            page_params = None
        return items, next_link

    @suppress_sensitive_http_logs()
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
        if max_bytes is not None and max_bytes <= 0:
            msg = "max_bytes must be positive."
            raise ValueError(msg)
        url = self._url(path)
        request_headers = httpx.Headers(headers)
        token = await self._lease.get_token()
        try:
            for attempt in range(2):
                request_headers["Authorization"] = f"Bearer {token}"
                async with self._client.stream("GET", url, headers=request_headers) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("location", "")
                        break
                    if response.status_code in {HTTP_SUCCESS, HTTP_PARTIAL_CONTENT}:
                        return await self._read_capped(response, max_bytes)
                    error = await self._download_error(response)
                if attempt or not isinstance(error, AuthExpiredError):
                    raise error
                token = await self._lease.get_token_after_auth_error(error, rejected_token=token)
            return await self._stream_download(location, headers=headers, max_bytes=max_bytes)
        except httpx.TransportError:
            raise ProviderUnavailableError(provider=PROVIDER_ID) from None

    @staticmethod
    async def _read_capped(response: httpx.Response, max_bytes: int | None) -> bytes:
        chunks: list[bytes] = []
        remaining = max_bytes
        async for chunk in response.aiter_bytes():
            if remaining is None:
                chunks.append(chunk)
            else:
                chunks.append(chunk[:remaining])
                remaining -= len(chunk)
                if remaining <= 0:
                    break
        return b"".join(chunks)

    async def _download_error(self, response: httpx.Response) -> IntegrationError:
        content = await self._read_capped(response, MAX_ERROR_BYTES)
        return integration_error_for_response(
            httpx.Response(response.status_code, headers=response.headers, content=content)
        )

    async def _stream_download(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        max_bytes: int | None,
    ) -> bytes:
        """Follow bounded, credential-free HTTPS downloads with SSRF protection."""
        download_headers = httpx.Headers(headers)
        for name in ("Authorization", "Proxy-Authorization", "Cookie"):
            download_headers.pop(name, None)
        for _ in range(MAX_DOWNLOAD_REDIRECTS + 1):
            try:
                target = httpx.URL(url)
                if target.scheme != "https" or not target.host or target.userinfo:
                    raise ValueError
                _, kwargs = await asyncio.to_thread(ssrf_protected_strict_httpx_client_kwargs_for_url, url)
            except (ValueError, httpx.InvalidURL):
                raise ProviderUnavailableError(provider=PROVIDER_ID) from None
            if self._transport is not None:
                kwargs["transport"] = self._transport
            # A fresh client per hop carries no Graph cookies or bearer token.
            async with (
                httpx.AsyncClient(
                    **{**kwargs, "follow_redirects": False}, timeout=self._timeout, headers={"User-Agent": USER_AGENT}
                ) as client,
                client.stream("GET", url, headers=download_headers) as response,
            ):
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise ProviderUnavailableError(provider=PROVIDER_ID)
                    url = urljoin(url, location)
                    continue
                if response.status_code not in {HTTP_SUCCESS, HTTP_PARTIAL_CONTENT}:
                    raise await self._download_error(response)
                return await self._read_capped(response, max_bytes)
        raise ProviderUnavailableError(provider=PROVIDER_ID)


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
        return f"/drives/{quote(drive_id, safe='!,')}"
    if site_id:
        return f"/sites/{quote(site_id, safe='!,')}/drive"
    return "/me/drive"


def drive_children_path(root: str, item_id: str = "", path: str = "") -> str:
    """Return the ``children`` collection for an item id, a path, or the root."""
    if item_id:
        return f"{root}/items/{quote(item_id, safe='!,')}/children"
    if path:
        return f"{root}/root:/{quote(path.strip('/'), safe='/')}:/children"
    return f"{root}/root/children"


def drive_item_path(root: str, item_id: str = "", path: str = "", *, suffix: str = "") -> str:
    """Return one driveItem address, optionally with a ``/content`` suffix.

    Path-addressed items use Graph's ``root:/<path>:`` form, where the suffix
    follows the closing colon.
    """
    if item_id:
        return f"{root}/items/{quote(item_id, safe='!,')}{suffix}"
    if path:
        return f"{root}/root:/{quote(path.strip('/'), safe='/')}:{suffix}"
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
