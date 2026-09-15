"""Shared Google Workspace SDK adapter for connection-backed components.

Every wave-1 Google action goes through this module so the five
components share one behaviour for four things the SDK does not give us:

* **Lazy credentials.** ``google-api-python-client`` wants a
  ``google.oauth2.credentials.Credentials``. The one built here carries only the
  access token minted by the connection lease: it has no refresh token and no
  client secret, so the SDK can never refresh behind Langflow's back. Expiry is
  handled proactively by :class:`~lfx.integrations.models.CredentialLease` and
  reactively by the single ``get_token_after_auth_error`` retry below.
* **Blocking I/O.** The Google client is synchronous. Both discovery-client
  construction and every ``.execute()`` run in ``asyncio.to_thread`` so an action
  never blocks the event loop.
* **Error vocabulary.** ``HttpError`` is normalized into the sanitized
  :mod:`lfx.integrations.errors` codes through a provider normalizer registered
  once at import time, so the client sees ``scope-missing`` rather than a Google
  payload that may echo request content.
* **Telemetry.** Actions run inside ``integration_action`` with the resolved
  credential's ``owner_kind``, which is why the credential is resolved before the
  span opens rather than lazily inside it.

Static discovery (``static_discovery=True``) is deliberate: it reads the
discovery document shipped inside ``googleapiclient`` instead of fetching it,
which keeps recorded-fixture tests offline and removes a network round trip from
every action.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from io import BytesIO
from typing import TYPE_CHECKING, Any

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from lfx.integrations import (
    ActionUnsupportedError,
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
    ResourceNotFoundError,
    ScopeMissingError,
    integration_action,
    normalize_integration_error,
    register_error_normalizer,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from lfx.custom.custom_component.component import Component
    from lfx.integrations.models import CredentialLease

PROVIDER_ID = "google"

_HTTP_BAD_REQUEST = 400
_HTTP_UNAUTHORIZED = 401
_HTTP_REQUEST_TIMEOUT = 408
_HTTP_FORBIDDEN = 403
_HTTP_NOT_FOUND = 404
_HTTP_METHOD_NOT_ALLOWED = 405
_HTTP_TOO_MANY_REQUESTS = 429
_HTTP_NOT_IMPLEMENTED = 501
_HTTP_SERVER_ERROR_FLOOR = 500

# Google returns 403 for both "you never asked for this scope" and "you are going
# too fast". Only the reason string tells them apart, and the two map to different
# error codes: one is permanent until reconnect, the other is retryable.
_RATE_LIMIT_REASONS = frozenset(
    {
        "ratelimitexceeded",
        "userratelimitexceeded",
        "quotaexceeded",
        "dailylimitexceeded",
        "rate_limit_exceeded",
    }
)
_SCOPE_REASONS = frozenset(
    {
        "insufficientpermissions",
        "access_token_scope_insufficient",
    }
)


def _error_reasons(exc: HttpError) -> set[str]:
    """Return every lowercase ``reason``/``status`` token Google put in the body."""
    try:
        payload = json.loads(exc.content.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return set()
    if not isinstance(payload, dict):
        return set()
    error = payload.get("error")
    if not isinstance(error, dict):
        return set()
    reasons: set[str] = set()
    status = error.get("status")
    if isinstance(status, str):
        reasons.add(status.casefold())
    for entry in error.get("errors") or []:
        if isinstance(entry, dict) and isinstance(entry.get("reason"), str):
            reasons.add(entry["reason"].casefold())
    for detail in error.get("details") or []:
        if isinstance(detail, dict) and isinstance(detail.get("reason"), str):
            reasons.add(detail["reason"].casefold())
    return reasons


def _retry_after_seconds(exc: HttpError) -> float | None:
    # httplib2.Response is itself the header mapping; it has no .headers attribute.
    headers = exc.resp
    try:
        raw = headers.get("retry-after")
    except AttributeError:
        return None
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def normalize_google_error(exc: BaseException) -> IntegrationError | None:
    """Map Google SDK failures onto the sanitized integration error vocabulary."""
    if isinstance(exc, IntegrationError):
        return exc
    if isinstance(exc, RefreshError):
        # The lease owns refresh; a RefreshError means the token we were handed is
        # dead, which is exactly the reactive-refresh signal.
        return AuthExpiredError(provider=PROVIDER_ID)
    if not isinstance(exc, HttpError):
        return None

    status = exc.status_code
    reasons = _error_reasons(exc)
    if status == _HTTP_UNAUTHORIZED:
        return AuthExpiredError(provider=PROVIDER_ID, http_status=status)
    if status == _HTTP_FORBIDDEN:
        if reasons & _RATE_LIMIT_REASONS:
            return RateLimitedError(provider=PROVIDER_ID, retry_after=_retry_after_seconds(exc), http_status=status)
        if reasons & _SCOPE_REASONS:
            return ScopeMissingError(provider=PROVIDER_ID)
        if "filenotdownloadable" in reasons:
            return InvalidRequestError(
                "This Google Workspace file cannot be downloaded as binary content.",
                hint="Set Export MIME Type to a supported format for this document.",
                provider=PROVIDER_ID,
                http_status=status,
            )
        if "exportsizelimitexceeded" in reasons:
            return InvalidRequestError(
                "The document exceeds Google's export size limit.",
                hint="Export a smaller document or choose another export format.",
                provider=PROVIDER_ID,
                http_status=status,
            )
        return ConnectionNotAuthorizedError(provider=PROVIDER_ID, reason="provider")
    if status == _HTTP_TOO_MANY_REQUESTS:
        return RateLimitedError(provider=PROVIDER_ID, retry_after=_retry_after_seconds(exc), http_status=status)
    if status == _HTTP_NOT_FOUND:
        return ResourceNotFoundError(provider=PROVIDER_ID)
    if status in {_HTTP_METHOD_NOT_ALLOWED, _HTTP_NOT_IMPLEMENTED}:
        return ActionUnsupportedError(provider=PROVIDER_ID, http_status=status)
    if status == _HTTP_REQUEST_TIMEOUT or (status is not None and status >= _HTTP_SERVER_ERROR_FLOOR):
        return ProviderUnavailableError(provider=PROVIDER_ID, http_status=status)
    if status is not None and _HTTP_BAD_REQUEST <= status < _HTTP_SERVER_ERROR_FLOOR:
        return InvalidRequestError(provider=PROVIDER_ID, http_status=status)
    return ProviderUnavailableError(provider=PROVIDER_ID, http_status=status)


register_error_normalizer(PROVIDER_ID, normalize_google_error)


def _build_service(api: str, version: str, token: str, http: Any | None) -> Any:
    """Build one discovery client. Called only inside ``asyncio.to_thread``.

    ``http`` is the recorded-fixture test seam. ``build`` refuses ``http=``
    together with ``credentials=``, so the transport is wrapped in the same
    ``AuthorizedHttp`` the credentialed path builds internally. That keeps the
    token-attachment behaviour under test instead of bypassing it.
    """
    credentials = Credentials(token=token)
    if http is not None:
        from google_auth_httplib2 import AuthorizedHttp

        authorized = AuthorizedHttp(credentials, http=http)
        return build(api, version, http=authorized, static_discovery=True, cache_discovery=False)
    return build(api, version, credentials=credentials, static_discovery=True, cache_discovery=False)


def _download_limit_error() -> InvalidRequestError:
    return InvalidRequestError(
        "The file exceeds the Drive Fetch File content limit.",
        hint="Fetch a smaller file (at most 25 MiB) or use a file ingestion source.",
        provider=PROVIDER_ID,
    )


class _BoundedBuffer(BytesIO):
    def __init__(self, max_bytes: int) -> None:
        super().__init__()
        self.max_bytes = max_bytes

    def write(self, content: bytes) -> int:
        if self.tell() + len(content) > self.max_bytes:
            raise _download_limit_error()
        return super().write(content)


class _MediaDownload:
    """Expose a chunked SDK download through the same execute/refresh boundary."""

    def __init__(self, request: Any, max_bytes: int) -> None:
        self.request = request
        self.max_bytes = max_bytes

    def execute(self) -> bytes:
        with _BoundedBuffer(self.max_bytes) as buffer:
            download = MediaIoBaseDownload(buffer, self.request, chunksize=min(1024 * 1024, self.max_bytes + 1))
            done = False
            while not done:
                previous_size = buffer.tell()
                progress, done = download.next_chunk(num_retries=0)
                if progress.total_size is not None and progress.total_size > self.max_bytes:
                    raise _download_limit_error()
                if not done and buffer.tell() == previous_size:
                    raise ProviderUnavailableError(provider=PROVIDER_ID)
            return buffer.getvalue()


class WorkspaceService:
    """One Google API client bound to a connection lease, with a single retry.

    ``execute`` takes a *factory* rather than a built request because the retry
    path has to rebuild the request against a freshly authorized client; a
    pre-built ``HttpRequest`` still carries the rejected token.
    """

    def __init__(self, lease: CredentialLease, api: str, version: str, *, http: Any | None = None) -> None:
        self._lease = lease
        self._api = api
        self._version = version
        self._http = http
        self._service: Any | None = None
        self._token: str | None = None

    async def _ensure_service(self) -> Any:
        token = await self._lease.get_token()
        if self._service is None or token != self._token:
            await self._replace_service(token)
        return self._service

    async def _replace_service(self, token: str) -> None:
        await self.aclose()
        self._service = await asyncio.to_thread(_build_service, self._api, self._version, token, self._http)
        self._token = token

    async def aclose(self) -> None:
        """Release the SDK's persistent HTTP connections."""
        service, self._service = self._service, None
        self._token = None
        if service is not None:
            await asyncio.to_thread(service.close)

    async def download(self, request_factory: Callable[[Any], Any], *, max_bytes: int) -> bytes:
        """Bound accumulated content and keep chunk I/O off the event loop."""
        return await self.execute(lambda client: _MediaDownload(request_factory(client), max_bytes))

    async def execute(self, request_factory: Callable[[Any], Any]) -> Any:
        """Run one Google request, retrying exactly once after an auth rejection."""
        service = await self._ensure_service()
        try:
            return await asyncio.to_thread(lambda: request_factory(service).execute())
        except Exception as exc:  # every failure leaves this method as an IntegrationError
            normalized = normalize_integration_error(exc, provider=PROVIDER_ID)
            if not isinstance(normalized, AuthExpiredError):
                raise normalized from exc
            # One reactive refresh; the lease itself refuses a second one.
            token = await self._lease.get_token_after_auth_error(normalized)
            await self._replace_service(token)
            retry_service = self._service
            try:
                return await asyncio.to_thread(lambda: request_factory(retry_service).execute())
            except Exception as retry_exc:  # same normalization on the retry
                raise normalize_integration_error(retry_exc, provider=PROVIDER_ID) from retry_exc


@asynccontextmanager
async def workspace_action(
    component: Component,
    *,
    capability: str,
    api: str,
    version: str,
    field: str = "connection",
) -> AsyncIterator[WorkspaceService]:
    """Resolve the component's connection and yield a telemetry-wrapped client.

    The credential is resolved *before* the telemetry span opens because the span
    records ``owner_kind``, which only exists once the resolver has answered.
    """
    lease = component.resolve_connection(field)
    credential = await lease.get_credential()
    async with integration_action(
        component,
        provider=PROVIDER_ID,
        capability=capability,
        owner_kind=credential.owner_kind,
    ):
        service = WorkspaceService(lease, api, version, http=getattr(component, "_workspace_http", None))
        try:
            yield service
        finally:
            await service.aclose()
