"""Bounded GitLab API requests using a trusted deployment origin."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

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
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx.utils.url_redaction import suppress_sensitive_http_logs

_PATH = re.compile(
    r"/(?:user|version|personal_access_tokens/self|projects/[1-9][0-9]*(?:/(?:hooks|issues|merge_requests)(?:/[1-9][0-9]*(?:/notes)?)?)?)\Z"
)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REQUEST_BYTES = 64 * 1024


def api_origin() -> str:
    """Read operator configuration rather than any flow or provider URL."""
    value = os.environ.get("LANGFLOW_GITLAB_ORIGIN", "https://gitlab.com")
    parts = urlsplit(value)
    host = parts.hostname or ""
    if (
        parts.scheme != "https"
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or parts.path not in {"", "/"}
        or parts.port not in {None, 443}
        or not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", host)
        or "." not in host
        or host.endswith((".localhost", ".local"))
    ):
        msg = "Configure one public HTTPS GitLab origin without a path or port."
        raise InvalidRequestError(msg, provider="gitlab")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        msg = "Configure a GitLab DNS hostname rather than an IP address."
        raise InvalidRequestError(msg, provider="gitlab")
    return "https://" + host.lower()


def positive_id(value) -> int:
    if isinstance(value, bool):
        msg = "Use a positive integer ID."
        raise InvalidRequestError(msg, provider="gitlab")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        msg = "Use a positive integer ID."
        raise InvalidRequestError(msg, provider="gitlab") from None
    if str(number) != str(value) or not 1 <= number <= 2**63 - 1:
        msg = "Use a positive integer ID."
        raise InvalidRequestError(msg, provider="gitlab")
    return number


def bounded_text(value, *, required: bool = False, maximum: int = 60000) -> str:
    try:
        valid = isinstance(value, str) and len(value.encode()) <= maximum and (not required or bool(value.strip()))
    except UnicodeEncodeError:
        valid = False
    if not valid:
        msg = "Provide text within the documented size limit."
        raise InvalidRequestError(msg, provider="gitlab")
    return value


def _safe_output(value):
    if isinstance(value, dict):
        return {
            key: _safe_output(item)
            for key, item in value.items()
            if not any(
                term in key.lower()
                for term in (
                    "token",
                    "secret",
                    "password",
                    "private_key",
                    "clone_url",
                    "http_url_to_repo",
                    "ssh_url_to_repo",
                )
            )
        }
    if isinstance(value, list):
        return [_safe_output(item) for item in value]
    return value


def response_error(response: httpx.Response):
    status = response.status_code
    if status == httpx.codes.UNAUTHORIZED:
        return AuthExpiredError(provider="gitlab")
    if status == httpx.codes.TOO_MANY_REQUESTS:
        try:
            delay = float(response.headers.get("retry-after", "60"))
        except (ValueError, OverflowError):
            delay = 60.0
        return RateLimitedError(provider="gitlab", retry_after=max(0, delay) if math.isfinite(delay) else 60.0)
    if status == httpx.codes.FORBIDDEN:
        return ConnectionNotAuthorizedError(provider="gitlab", reason="provider")
    if status == httpx.codes.NOT_FOUND:
        return ResourceNotFoundError(provider="gitlab")
    if httpx.codes.BAD_REQUEST <= status < httpx.codes.INTERNAL_SERVER_ERROR:
        return InvalidRequestError(provider="gitlab", http_status=status)
    return ProviderUnavailableError(provider="gitlab", http_status=status)


class GitLabClient:
    """Reject redirects and arbitrary paths before resolving credentials."""

    def __init__(self, lease, *, transport: httpx.AsyncBaseTransport | None = None):
        self.lease = lease
        self.origin = api_origin()
        try:
            kwargs = (
                ssrf_protected_strict_httpx_client_kwargs_for_url(self.origin)[1]
                if transport is None
                else {"transport": transport}
            )
        except SSRFProtectionError:
            raise IntegrationNetworkError(
                reason="connection", provider="gitlab", host=urlsplit(self.origin).hostname
            ) from None
        kwargs["follow_redirects"] = False
        self._client = httpx.AsyncClient(timeout=20, trust_env=False, **kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        await self._client.aclose()

    async def request(self, method, path, *, body=None, params=None):
        if method not in {"GET", "POST", "PUT", "DELETE"} or not _PATH.fullmatch(path):
            msg = "The GitLab REST request is invalid."
            raise InvalidRequestError(msg, provider="gitlab")
        content = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        if content is not None and len(content) > MAX_REQUEST_BYTES:
            msg = "The GitLab request exceeds 64 KiB."
            raise InvalidRequestError(msg, provider="gitlab")
        credential = await self.lease.get_credential()
        if (
            credential.provider != "gitlab"
            or credential.identity != "user_delegated"
            or credential.account is None
            or credential.account.tenant_id != self.origin
            or not credential.scopes_verified
            or "api" not in credential.granted_scopes
        ):
            raise ConnectionNotAuthorizedError(
                provider="gitlab", hint="Choose a verified GitLab personal access token connection for this deployment."
            )
        expiry = credential.expires_at
        if expiry is None or expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise AuthExpiredError(provider="gitlab")
        token = credential.access_token.get_secret_value()
        try:
            return await asyncio.wait_for(self._request(method, path, content, params, token), timeout=25)
        except (asyncio.TimeoutError, httpx.TimeoutException):
            raise IntegrationNetworkError(
                reason="timeout", provider="gitlab", host=urlsplit(self.origin).hostname
            ) from None
        except httpx.TransportError:
            raise IntegrationNetworkError(
                reason="connection", provider="gitlab", host=urlsplit(self.origin).hostname
            ) from None

    async def _request(self, method, path, content, params, token):
        async with (
            suppress_sensitive_http_logs(),
            self._client.stream(
                method,
                self.origin + "/api/v4" + path,
                content=content,
                params=params,
                headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json", "Accept": "application/json"},
            ) as response,
        ):
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > MAX_RESPONSE_BYTES:
                    msg = "The GitLab response exceeds 2 MiB."
                    raise InvalidRequestError(msg, provider="gitlab")
            if not httpx.codes.OK <= response.status_code < httpx.codes.MULTIPLE_CHOICES:
                raise response_error(response)
            if not chunks:
                return {}
            try:
                payload = json.loads(chunks)
            except (ValueError, UnicodeDecodeError):
                raise ProviderUnavailableError(provider="gitlab") from None
            if not isinstance(payload, (dict, list)):
                raise ProviderUnavailableError(provider="gitlab")
            return _safe_output(payload)
