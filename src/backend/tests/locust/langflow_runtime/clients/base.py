"""HTTP client primitives for Locust performance-suite protocol drivers.

Protocol clients (MCP / Workflows / Webhooks) talk only to ``ApiClient``.
Transports are explicit:

- ``LocustTransport`` — Locust ``HttpSession`` / ``FastHttpSession`` (load runs)
- ``HttpxTransport`` — plain ``httpx.Client`` (provision / preflight / drain)

Construct via ``ApiClient.from_locust(...)`` or ``ApiClient.from_httpx(...)``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urljoin

from tests.locust.langflow_runtime.config.naming import metric_name

if TYPE_CHECKING:
    from collections.abc import Iterator

DEFAULT_CONNECT_TIMEOUT_S = 10.0
DEFAULT_READ_TIMEOUT_S = 60.0


class ClientError(Exception):
    """Base error for API client failures."""


class TransportError(ClientError):
    """Network, timeout, or unexpected transport-layer failure."""


class ApplicationError(ClientError):
    """Application-level HTTP/API failure."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class HttpTransport(Protocol):
    """Backend that issues HTTP requests and returns a response-like object."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: Any,
        stream: bool = False,
        name: str | None = None,
        **kwargs: Any,
    ) -> Any: ...


@dataclass(frozen=True)
class ParsedResponse:
    status_code: int
    headers: dict[str, str]
    text: str
    json_data: Any | None = None


def auth_headers(*, api_key: str | None = None, bearer_token: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    return headers


def parse_json_body(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ApplicationError(f"invalid JSON response: {exc}", body=text) from exc


def classify_http_error(status_code: int, *, body: Any = None) -> ApplicationError:
    return ApplicationError(f"unexpected HTTP {status_code}", status_code=status_code, body=body)


def _header_map(response: Any) -> dict[str, str]:
    headers = getattr(response, "headers", None) or {}
    if hasattr(headers, "items"):
        return {str(k).lower(): str(v) for k, v in headers.items()}
    return {str(k).lower(): str(v) for k, v in dict(headers).items()}


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text is not None:
        return text
    content = getattr(response, "content", b"")
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content)


def _response_status(response: Any) -> int:
    status = getattr(response, "status_code", None)
    if status is not None:
        return int(status)
    status = getattr(response, "status", None)
    if status is not None:
        return int(status)
    msg = "response has no status_code"
    raise TransportError(msg)


def iter_response_lines(response: Any, *, chunk_size: int = 1024) -> Iterator[str]:
    """Yield response lines across httpx/requests and Locust FastHttp clients."""
    iter_lines = getattr(response, "iter_lines", None)
    if callable(iter_lines):
        yield from iter_lines()
        return

    # FastHttp eagerly buffers non-streaming responses. Prefer that cache when
    # present because its underlying socket has already been consumed.
    cached = getattr(response, "_cached_content", None)
    if cached is not None:
        text = (
            bytes(cached).decode("utf-8", errors="replace")
            if isinstance(cached, (bytes, bytearray, memoryview))
            else str(cached)
        )
        yield from text.splitlines()
        return

    # geventhttpclient's read(length) waits until the requested byte count is
    # available. That stalls low-volume SSE streams when iter_content asks for
    # 1 KiB but the initial ``connected`` frame is much smaller. Its readline()
    # returns as soon as a frame line arrives and remains gevent-cooperative.
    raw_response = getattr(response, "_response", None)
    readline = getattr(raw_response, "readline", None)
    if callable(readline):
        while True:
            # geventhttpclient defaults to CRLF, while Starlette streams use LF.
            raw = readline(sep=b"\n")
            if not raw:
                return
            line = (
                bytes(raw).decode("utf-8", errors="replace")
                if isinstance(raw, (bytes, bytearray, memoryview))
                else str(raw)
            )
            yield line.rstrip("\r\n")

    # FastHttp streaming responses expose iter_content(), not iter_lines().
    iter_content = getattr(response, "iter_content", None)
    if not callable(iter_content):
        raise TransportError("stream response lacks iter_lines() and iter_content()")

    buffer = ""
    for chunk in iter_content(chunk_size=chunk_size, decode_content=True):
        text = (
            bytes(chunk).decode("utf-8", errors="replace")
            if isinstance(chunk, (bytes, bytearray, memoryview))
            else str(chunk)
        )
        buffer += text
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            yield line.rstrip("\r")
    if buffer:
        yield buffer.rstrip("\r")


def close_response(response: Any) -> None:
    """Close or release a response across supported transports."""
    close = getattr(response, "close", None)
    if callable(close):
        close()
        return
    release = getattr(response, "release", None)
    if callable(release):
        release()


def wrap_response(response: Any, *, expect_json: bool = False) -> ParsedResponse:
    status_code = _response_status(response)
    headers = _header_map(response)
    text = _response_text(response)
    json_data = None
    if expect_json and text:
        json_data = parse_json_body(text)
    return ParsedResponse(status_code=status_code, headers=headers, text=text, json_data=json_data)


class LocustTransport:
    """Locust ``HttpSession`` / ``FastHttpSession`` (and session-shaped test doubles).

    Uses ``stream=True`` on ``.get()``/``.post()`` and supplies the metric name so
    timings land in Locust stats during load runs.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: Any,
        stream: bool = False,
        name: str | None = None,
        **kwargs: Any,
    ) -> Any:
        method_lower = method.lower()
        request_fn = getattr(self.session, method_lower, None)
        request_kwargs: dict[str, Any] = {
            "headers": headers,
            "timeout": timeout,
            **kwargs,
        }
        if stream:
            request_kwargs["stream"] = True

        if request_fn is not None:
            if name is not None:
                request_kwargs["name"] = name
            return request_fn(url, **request_kwargs)
        if name is not None:
            request_kwargs["name"] = name
        return self.session.request(method, url, **request_kwargs)


class HttpxTransport:
    """Plain ``httpx.Client`` for provision / preflight / drain (no Locust process).

    httpx 0.28+ removed ``stream=`` from ``.get()`` / ``.request()``; streaming uses
    ``build_request`` + ``send(..., stream=True)`` so callers still get ``iter_lines``.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    @staticmethod
    def _timeout(timeout: Any) -> Any:
        if isinstance(timeout, tuple) and len(timeout) == 2:
            connect_s, read_s = timeout
            import httpx

            return httpx.Timeout(read_s, connect=connect_s)
        return timeout

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: Any,
        stream: bool = False,
        name: str | None = None,  # noqa: ARG002 — Locust metric name; unused here
        **kwargs: Any,
    ) -> Any:
        req_timeout = self._timeout(timeout)
        request = self.client.build_request(method.upper(), url, headers=headers, timeout=req_timeout, **kwargs)
        return self.client.send(request, stream=stream)


class ApiClient:
    """Auth + URL helpers over an explicit ``HttpTransport``."""

    def __init__(
        self,
        transport: HttpTransport,
        *,
        base_url: str,
        api_key: str | None = None,
        bearer_token: str | None = None,
        connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S,
        read_timeout_s: float = DEFAULT_READ_TIMEOUT_S,
    ) -> None:
        self.transport = transport
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.bearer_token = bearer_token
        self.connect_timeout_s = connect_timeout_s
        self.read_timeout_s = read_timeout_s

    @classmethod
    def from_locust(
        cls,
        session: Any,
        *,
        base_url: str,
        api_key: str | None = None,
        bearer_token: str | None = None,
        connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S,
        read_timeout_s: float = DEFAULT_READ_TIMEOUT_S,
    ) -> ApiClient:
        return cls(
            LocustTransport(session),
            base_url=base_url,
            api_key=api_key,
            bearer_token=bearer_token,
            connect_timeout_s=connect_timeout_s,
            read_timeout_s=read_timeout_s,
        )

    @classmethod
    def from_httpx(
        cls,
        client: Any,
        *,
        base_url: str,
        api_key: str | None = None,
        bearer_token: str | None = None,
        connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S,
        read_timeout_s: float = DEFAULT_READ_TIMEOUT_S,
    ) -> ApiClient:
        return cls(
            HttpxTransport(client),
            base_url=base_url,
            api_key=api_key,
            bearer_token=bearer_token,
            connect_timeout_s=connect_timeout_s,
            read_timeout_s=read_timeout_s,
        )

    def url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return urljoin(f"{self.base_url}/", path.lstrip("/"))

    def _merge_headers(self, headers: dict[str, str] | None) -> dict[str, str]:
        merged = auth_headers(api_key=self.api_key, bearer_token=self.bearer_token)
        if headers:
            merged.update(headers)
        return merged

    def _timeout(self, timeout: Any | None) -> Any:
        if timeout is not None:
            return timeout
        return (self.connect_timeout_s, self.read_timeout_s)

    def request(
        self,
        method: str,
        path: str,
        *,
        name: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: Any | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        try:
            return self.transport.request(
                method,
                self.url(path),
                headers=self._merge_headers(headers),
                timeout=self._timeout(timeout),
                stream=stream,
                name=name,
                **kwargs,
            )
        except Exception as exc:
            if isinstance(exc, ClientError):
                raise
            raise TransportError(str(exc)) from exc

    def parsed_request(
        self,
        method: str,
        path: str,
        *,
        name: str | None = None,
        expect_json: bool = False,
        ok_statuses: set[int] | None = None,
        **kwargs: Any,
    ) -> ParsedResponse:
        response = self.request(method, path, name=name, **kwargs)
        parsed = wrap_response(response, expect_json=expect_json)
        if ok_statuses is not None and parsed.status_code not in ok_statuses:
            body = parsed.json_data if parsed.json_data is not None else parsed.text
            raise classify_http_error(parsed.status_code, body=body)
        return parsed

    @staticmethod
    def tx_name(protocol: str, operation: str, workload: str, flow_class: str) -> str:
        return metric_name(protocol, operation, workload, flow_class)
