"""Bounded GitHub.com REST calls using a connection credential lease."""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from typing import TYPE_CHECKING, Any

import httpx
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationNetworkError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
    ResourceNotFoundError,
)
from lfx.utils.ssrf_httpx import ssrf_protected_strict_httpx_client_kwargs_for_url
from lfx.utils.url_redaction import suppress_sensitive_http_logs

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease

PROVIDER_ID = "github"
API_ORIGIN = "https://api.github.com"
API_VERSION = "2022-11-28"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REQUEST_BYTES = 64 * 1024
_REPOSITORY = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}\Z")
_PATH = re.compile(r"/(?:repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_/-]+)?|installation/repositories)\Z")


def repository_path(value: str) -> str:
    """Accept one repository name rather than a URL or arbitrary REST path."""
    if not isinstance(value, str) or not _REPOSITORY.fullmatch(value) or value.split("/")[1] in {".", ".."}:
        msg = "Use a GitHub.com repository in owner/repository form."
        raise InvalidRequestError(msg, provider=PROVIDER_ID)
    return f"/repos/{value}"


def positive_id(value: Any) -> int:
    """Validate provider issue, pull request, and webhook numbers."""
    if isinstance(value, bool):
        msg = "Use a positive integer number."
        raise InvalidRequestError(msg, provider=PROVIDER_ID)
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        msg = "Use a positive integer number."
        raise InvalidRequestError(msg, provider=PROVIDER_ID) from None
    if str(number) != str(value) or not 1 <= number <= 2**63 - 1:
        msg = "Use a positive integer number."
        raise InvalidRequestError(msg, provider=PROVIDER_ID)
    return number


def bounded_text(value: Any, *, required: bool = False, maximum: int = 60000) -> str:
    try:
        valid = (
            isinstance(value, str) and len(value.encode("utf-8")) <= maximum and (not required or bool(value.strip()))
        )
    except UnicodeEncodeError:
        valid = False
    if not valid:
        msg = "Provide text within this action's documented size limit."
        raise InvalidRequestError(msg, provider=PROVIDER_ID)
    return value


def _without_credentials(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_credentials(item)
            for key, item in value.items()
            if key not in {"temp_clone_token", "access_token", "refresh_token", "token", "client_secret"}
        }
    if isinstance(value, list):
        return [_without_credentials(item) for item in value]
    return value


def response_error(response: httpx.Response):
    """Return fixed error text without reflecting provider bodies or secrets."""
    status = response.status_code
    if status == httpx.codes.UNAUTHORIZED:
        return AuthExpiredError(provider=PROVIDER_ID)
    if status == httpx.codes.TOO_MANY_REQUESTS or (
        status == httpx.codes.FORBIDDEN
        and (response.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in response.headers)
    ):
        try:
            retry_after = max(0.0, float(response.headers["retry-after"]))
        except (KeyError, ValueError, OverflowError):
            try:
                retry_after = max(0.0, float(response.headers["x-ratelimit-reset"]) - time.time())
            except (KeyError, ValueError, OverflowError):
                retry_after = 60.0
        return RateLimitedError(
            provider=PROVIDER_ID, retry_after=retry_after if math.isfinite(retry_after) else 60.0, http_status=status
        )
    if status == httpx.codes.FORBIDDEN:
        return ConnectionNotAuthorizedError(provider=PROVIDER_ID, reason="provider")
    if status == httpx.codes.NOT_FOUND:
        return ResourceNotFoundError(provider=PROVIDER_ID)
    if httpx.codes.BAD_REQUEST <= status < httpx.codes.INTERNAL_SERVER_ERROR:
        return InvalidRequestError(provider=PROVIDER_ID, http_status=status)
    return ProviderUnavailableError(provider=PROVIDER_ID, http_status=status)


class GitHubClient:
    """Fixed-origin client with bounded bodies and one rejected-token refresh."""

    def __init__(self, lease: CredentialLease, *, transport: httpx.AsyncBaseTransport | None = None):
        self.lease = lease
        kwargs = (
            ssrf_protected_strict_httpx_client_kwargs_for_url(API_ORIGIN)[1]
            if transport is None
            else {"transport": transport}
        )
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=False, trust_env=False, **kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        await self._client.aclose()

    async def _request(self, method: str, path: str, *, body: dict | None = None, params: dict | None = None):
        if not _PATH.fullmatch(path) or "//" in path or any(part in {".", ".."} for part in path.split("/")):
            msg = "The GitHub REST path is invalid."
            raise InvalidRequestError(msg, provider=PROVIDER_ID)
        content = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        if content is not None and len(content) > MAX_REQUEST_BYTES:
            msg = "The GitHub request exceeds 64 KiB."
            raise InvalidRequestError(msg, provider=PROVIDER_ID)
        token = await self.lease.get_token()
        for attempt in range(2):
            try:
                async with (
                    suppress_sensitive_http_logs(),
                    self._client.stream(
                        method,
                        API_ORIGIN + path,
                        content=content,
                        params=params,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github+json",
                            "Content-Type": "application/json",
                            "X-GitHub-Api-Version": API_VERSION,
                        },
                    ) as response,
                ):
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > MAX_RESPONSE_BYTES:
                            msg = "The GitHub response exceeds 2 MiB."
                            raise InvalidRequestError(msg, provider=PROVIDER_ID)
                    if response.status_code == httpx.codes.UNAUTHORIZED and attempt == 0:
                        token = await self.lease.get_token_after_auth_error(
                            AuthExpiredError(provider=PROVIDER_ID), rejected_token=token
                        )
                        if path != "/installation/repositories":
                            await self._request("GET", "/installation/repositories", params={"per_page": 1})
                        continue
                    if not httpx.codes.OK <= response.status_code < httpx.codes.MULTIPLE_CHOICES:
                        raise response_error(response)
                    if not chunks:
                        return {}
                    try:
                        payload = json.loads(chunks)
                    except (ValueError, UnicodeDecodeError):
                        raise ProviderUnavailableError(provider=PROVIDER_ID) from None
                    if not isinstance(payload, (dict, list)):
                        raise ProviderUnavailableError(provider=PROVIDER_ID)
                    return payload
            except httpx.TimeoutException:
                raise IntegrationNetworkError(reason="timeout", provider=PROVIDER_ID, host="api.github.com") from None
            except httpx.TransportError:
                raise IntegrationNetworkError(
                    reason="connection", provider=PROVIDER_ID, host="api.github.com"
                ) from None
        raise AuthExpiredError(provider=PROVIDER_ID)

    async def request(self, method: str, path: str, *, body: dict | None = None, params: dict | None = None):
        credential = await self.lease.get_credential()
        if credential.identity not in {None, "service"}:
            raise ConnectionNotAuthorizedError(
                provider=PROVIDER_ID, hint="Choose a GitHub App installation connection."
            )
        try:
            # GitHub rejects personal access tokens on the installation endpoint.
            await asyncio.wait_for(
                self._request("GET", "/installation/repositories", params={"per_page": 1}), timeout=25
            )
            return await asyncio.wait_for(self._request(method, path, body=body, params=params), timeout=25)
        except asyncio.TimeoutError:
            raise IntegrationNetworkError(reason="timeout", provider=PROVIDER_ID, host="api.github.com") from None
