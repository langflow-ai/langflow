"""Fixed-origin Confluence requests with credential checks and bounded responses."""

from __future__ import annotations

import json
import math
import re
from typing import TYPE_CHECKING

import httpx
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationNetworkError,
    ProviderUnavailableError,
    RateLimitedError,
    ResourceNotFoundError,
    ScopeMissingError,
)
from lfx.utils.ssrf_httpx import ssrf_protected_strict_httpx_client_kwargs_for_url
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx.utils.url_redaction import suppress_sensitive_http_logs

from lfx_confluence.schema import API_ORIGIN, READ, cloud_id, invalid

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease

_PATH = re.compile(r"/wiki/api/v2/pages(?:/[1-9][0-9]{0,18})?\Z")
MAX_REQUEST_BYTES = 1048576
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def http_client(transport=None) -> httpx.AsyncClient:
    try:
        kwargs = (
            ssrf_protected_strict_httpx_client_kwargs_for_url(API_ORIGIN)[1]
            if transport is None
            else {"transport": transport}
        )
    except SSRFProtectionError:
        raise IntegrationNetworkError(provider="confluence", reason="connection", host="api.atlassian.com") from None
    kwargs["follow_redirects"] = False
    return httpx.AsyncClient(timeout=20, trust_env=False, **kwargs)


async def send(http: httpx.AsyncClient, method: str, path: str, token: str, *, body=None, params=None):
    if not path.startswith("/") or "?" in path or "#" in path or ".." in path or "\\" in path or "%" in path:
        msg = "Unsupported Confluence API resource."
        raise invalid(msg)
    content = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    if content is not None and len(content) > MAX_REQUEST_BYTES:
        msg = "The Confluence request exceeds 1 MiB."
        raise invalid(msg)
    try:
        async with (
            suppress_sensitive_http_logs(),
            http.stream(
                method,
                API_ORIGIN + path,
                content=content,
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            ) as response,
        ):
            raw = bytearray()
            async for part in response.aiter_bytes():
                raw.extend(part)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ProviderUnavailableError(provider="confluence")
            status = response.status_code
            if status == httpx.codes.UNAUTHORIZED:
                raise AuthExpiredError(provider="confluence")
            if status == httpx.codes.FORBIDDEN:
                raise ConnectionNotAuthorizedError(provider="confluence", reason="provider")
            if status == httpx.codes.NOT_FOUND:
                raise ResourceNotFoundError(provider="confluence")
            if status == httpx.codes.TOO_MANY_REQUESTS:
                try:
                    delay = float(response.headers.get("Retry-After", "60"))
                except (ValueError, OverflowError):
                    delay = 60.0
                raise RateLimitedError(
                    provider="confluence", retry_after=max(0, min(delay, 86400)) if math.isfinite(delay) else 60.0
                )
            if (
                status >= httpx.codes.INTERNAL_SERVER_ERROR
                or httpx.codes.MULTIPLE_CHOICES <= status < httpx.codes.BAD_REQUEST
            ):
                raise ProviderUnavailableError(provider="confluence", http_status=status)
            if status >= httpx.codes.BAD_REQUEST:
                msg = "Confluence rejected this operation. Check the page fields and account permissions."
                raise invalid(msg)
            if status not in {200, 201, 204}:
                raise ProviderUnavailableError(provider="confluence")
            if not raw and status == httpx.codes.NO_CONTENT:
                return {}
            try:
                value = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise ProviderUnavailableError(provider="confluence") from None
            if not isinstance(value, (dict, list)):
                raise ProviderUnavailableError(provider="confluence")
            return value
    except httpx.RequestError:
        raise IntegrationNetworkError(provider="confluence", reason="connection", host="api.atlassian.com") from None


class ConfluenceClient:
    def __init__(self, lease: CredentialLease, *, transport=None):
        self.lease = lease
        self.site = cloud_id()
        self.http = http_client(transport)

    async def aclose(self):
        await self.http.aclose()

    async def _check(self, scopes):
        credential = await self.lease.get_credential()
        if (
            credential.provider != "confluence"
            or credential.identity != "user_delegated"
            or credential.account is None
            or credential.account.tenant_id != self.site
        ):
            raise ConnectionNotAuthorizedError(provider="confluence", reason="provider")
        if not credential.scopes_verified or not scopes <= credential.granted_scopes:
            raise ScopeMissingError(
                frozenset(scopes), provider="confluence", scopes_verified=credential.scopes_verified
            )

    async def request(self, method, path, *, body=None, params=None, scopes=frozenset({READ})):
        if not _PATH.fullmatch(path):
            msg = "Unsupported Confluence API resource."
            raise invalid(msg)
        await self._check(scopes)
        token = await self.lease.get_token()
        for attempt in range(2):
            try:
                return await send(
                    self.http, method, f"/ex/confluence/{self.site}" + path, token, body=body, params=params
                )
            except AuthExpiredError:
                if attempt:
                    raise
                token = await self.lease.get_token_after_auth_error(
                    AuthExpiredError(provider="confluence"), rejected_token=token
                )
                await self._check(scopes)
        raise AuthExpiredError(provider="confluence")
