"""HTTP client primitives for Locust performance-suite protocol drivers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urljoin

from tests.locust.langflow_runtime.config.naming import metric_name

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


class HttpClient(Protocol):
    def request(self, method: str, url: str, **kwargs: Any) -> Any: ...


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


def wrap_response(response: Any, *, expect_json: bool = False) -> ParsedResponse:
    status_code = _response_status(response)
    headers = _header_map(response)
    text = _response_text(response)
    json_data = None
    if expect_json and text:
        json_data = parse_json_body(text)
    return ParsedResponse(status_code=status_code, headers=headers, text=text, json_data=json_data)


def _supports_locust_catch_response(http: Any) -> bool:
    """Return True only for Locust HttpSession-like clients (not httpx)."""
    module = type(http).__module__
    if module == "httpx" or module.startswith("httpx."):
        return False
    name = type(http).__name__
    if name in {"HttpSession", "FastHttpSession"}:
        return True
    # Locust sessions typically expose cookiejar; plain mocks usually do not.
    return hasattr(http, "cookiejar") and hasattr(http, "request")


class ApiClient:
    """Thin wrapper over Locust HttpSession-like clients or ``httpx.Client``."""

    def __init__(
        self,
        http: HttpClient,
        *,
        base_url: str,
        api_key: str | None = None,
        bearer_token: str | None = None,
        connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S,
        read_timeout_s: float = DEFAULT_READ_TIMEOUT_S,
    ) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.bearer_token = bearer_token
        self.connect_timeout_s = connect_timeout_s
        self.read_timeout_s = read_timeout_s

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
        url = self.url(path)
        req_headers = self._merge_headers(headers)
        req_timeout = self._timeout(timeout)
        method_lower = method.lower()
        request_fn = getattr(self.http, method_lower, None)

        request_kwargs: dict[str, Any] = {
            "headers": req_headers,
            "timeout": req_timeout,
            **kwargs,
        }
        if stream:
            request_kwargs["stream"] = True

        try:
            if name is not None and _supports_locust_catch_response(self.http) and request_fn is not None:
                with request_fn(url, catch_response=True, name=name, **request_kwargs) as response:
                    return response
            if request_fn is not None:
                return request_fn(url, **request_kwargs)
            return self.http.request(method, url, **request_kwargs)
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
