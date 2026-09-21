"""Unauthenticated, bounded reads from Agent Guild's fixed public service."""

from __future__ import annotations

import asyncio
import ipaddress
import json
from urllib.parse import parse_qsl, urlsplit

import httpx

SERVICE_ORIGIN = "https://agent-guild-5d5r.onrender.com"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_URL_LENGTH = 4096
MAX_TIMEOUT_SECONDS = 60
_FIRST_PRINTABLE_ASCII = 32
_DELETE_ASCII = 127
_CREDENTIAL_KEYS = frozenset(
    {
        "apikey",
        "accesstoken",
        "authorization",
        "password",
        "passwd",
        "token",
        "secret",
        "signature",
        "xapikey",
        "key",
        "auth",
        "bearer",
        "clientsecret",
        "idtoken",
        "sig",
        "xamzcredential",
        "xamzsignature",
        "xamzsecuritytoken",
        "xgoogcredential",
        "xgoogsignature",
    }
)


def public_endpoint(value: str) -> str:
    """Reject malformed, local, or credential-bearing targets before transmission."""
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_URL_LENGTH:
        msg = "Provide a public HTTP(S) endpoint URL of at most 4096 characters."
        raise ValueError(msg)
    value = value.strip()
    if any(ord(char) < _FIRST_PRINTABLE_ASCII or ord(char) == _DELETE_ASCII for char in value):
        msg = "Endpoint URLs must not contain control characters."
        raise ValueError(msg)
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        msg = "Provide a valid public HTTP(S) endpoint URL."
        raise ValueError(msg) from exc
    if parsed.scheme not in {"https", "http"} or not hostname or port == 0:
        msg = "Provide a valid public HTTP(S) endpoint URL."
        raise ValueError(msg)
    query_keys = {key.lower().replace("-", "").replace("_", "") for key, _ in parse_qsl(parsed.query)}
    if parsed.username is not None or parsed.password is not None or parsed.fragment or query_keys & _CREDENTIAL_KEYS:
        msg = "Endpoint URLs must not contain credentials, credential query parameters, or fragments."
        raise ValueError(msg)
    hostname = hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        msg = "Preflight requires a public endpoint, not a local address."
        raise ValueError(msg)
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        msg = "Preflight requires a public endpoint, not a private or reserved IP address."
        raise ValueError(msg)
    return value


def _reject_nonfinite(_value: str) -> None:
    msg = "Agent Guild returned non-finite JSON numbers."
    raise ValueError(msg)


async def _read_bytes(path: str, timeout: int, params: dict[str, str] | None) -> bytearray:
    async with (
        httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client,
        client.stream(
            "GET", f"{SERVICE_ORIGIN}{path}", params=params, headers={"Accept": "application/json"}
        ) as response,
    ):
        response.raise_for_status()
        body = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=65536):
            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                msg = "Agent Guild response exceeded the 4 MiB limit."
                raise ValueError(msg)
            body.extend(chunk)
        return body


async def read_json(path: str, *, timeout: int, params: dict[str, str] | None = None) -> dict:
    """Read only the two free routes, refusing redirects and oversized responses."""
    if path not in {"/preflight", "/.well-known/agent-guild.json"}:
        msg = "Unsupported Agent Guild discovery route."
        raise ValueError(msg)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        msg = "Timeout must be an integer from 1 to 60 seconds."
        raise ValueError(msg)
    try:
        body = await asyncio.wait_for(_read_bytes(path, timeout, params), timeout=timeout)
    except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
        msg = "Agent Guild request timed out."
        raise ValueError(msg) from exc
    except httpx.HTTPStatusError as exc:
        msg = f"Agent Guild returned HTTP {exc.response.status_code}; no payment or redirect was attempted."
        raise ValueError(msg) from exc
    except httpx.RequestError as exc:
        msg = "Unable to reach Agent Guild."
        raise ValueError(msg) from exc
    try:
        result = json.loads(body, parse_constant=_reject_nonfinite)
    except (ValueError, UnicodeDecodeError) as exc:
        msg = "Agent Guild returned invalid JSON."
        raise ValueError(msg) from exc
    if not isinstance(result, dict):
        msg = "Agent Guild returned an unexpected response shape."
        raise TypeError(msg)
    return result
