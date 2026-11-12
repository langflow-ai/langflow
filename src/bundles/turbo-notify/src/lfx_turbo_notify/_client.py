"""HTTP transport for the Turbo Notify REST API.

Every component calls the API through ``TurboNotifyClient``. The client sends the
caller's own API key as a bearer token, never follows redirects (so the key cannot
be forwarded to another host), and turns every failure into a ``TurboNotifyError``
whose message starts with the API ``error`` code and continues with the description.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

DEFAULT_BASE_URL = "https://api.turbonotify.com"
DEFAULT_NUMBER_ALIAS = "main"
USER_AGENT = "langflow-turbo-notify-bundle"

READ_TIMEOUT_SECONDS = 30.0
WRITE_TIMEOUT_SECONDS = 60.0

_API_KEY_PATTERN = re.compile(r"[\x21-\x7e]+")
_MAX_ALIAS_LENGTH = 128
_HTTP_ERROR_STATUS = httpx.codes.BAD_REQUEST
_SERVER_ERROR_STATUS = httpx.codes.INTERNAL_SERVER_ERROR

_SEND_SERVER_HINT = (
    "The failure happened on the Turbo Notify side and the message may have gone out. "
    "Check Get Messages before sending it again."
)


class TurboNotifyError(ValueError):
    """A Turbo Notify call failed, or an input was refused before any call was made.

    ``str(error)`` is ``"<code>: <description>"``. For an API failure ``code`` is the
    API ``error`` value (for example ``insufficient_scope``); for a refused input it
    names the field (for example ``invalid_phone_number``). Langflow reports any
    exception raised by a component as a component build error, so this is a
    ``ValueError`` like the other bundles raise.
    """

    def __init__(
        self,
        description: str,
        code: str,
        *,
        status: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(f"{code}: {description}")
        self.code = code
        self.description = description
        self.status = status
        self.retry_after = retry_after


def normalize_base_url(raw: str | None) -> str:
    """Return the API origin without a trailing slash or ``/v1``, or refuse an unusable address."""
    text = (raw or "").strip() or DEFAULT_BASE_URL
    text = text.rstrip("/").removesuffix("/v1")
    parts = urlsplit(text)
    usable = (
        parts.scheme in {"http", "https"}
        and bool(parts.hostname)
        and not parts.username
        and not parts.password
        and not parts.query
        and not parts.fragment
    )
    if not usable:
        msg = (
            "Base URL must be a full web address such as https://api.turbonotify.com, "
            "without a login, query or fragment."
        )
        raise TurboNotifyError(msg, "invalid_base_url")
    return text


def require_api_key(raw: str | None) -> str:
    """Return the API key, or refuse a missing key or one that cannot be a header value."""
    key = (raw or "").strip()
    if not key:
        msg = "The Turbo Notify API key is required. Set the API Key input."
        raise TurboNotifyError(msg, "missing_api_key")
    if not _API_KEY_PATTERN.fullmatch(key):
        msg = "The API key has spaces or characters that an API key never contains. Paste it again."
        raise TurboNotifyError(msg, "invalid_api_key")
    return key


def require_number_alias(raw: str | None) -> str:
    """Return the number alias (``main``, an extra number alias or a ``num_`` id)."""
    alias = (raw or "").strip() or DEFAULT_NUMBER_ALIAS
    if len(alias) > _MAX_ALIAS_LENGTH:
        msg = "The Number alias is too long. Use main, the alias of an extra number or its num_ id."
        raise TurboNotifyError(msg, "invalid_number_alias")
    return alias


def make_http_client(timeout: float) -> httpx.AsyncClient:
    """Build the HTTP client. A single seam so tests can run the real code over a mock transport."""
    return httpx.AsyncClient(timeout=timeout, follow_redirects=False)


def _payload_of(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _validation_fields(payload: dict[str, Any]) -> str:
    details = payload.get("details")
    errors = details.get("errors") if isinstance(details, dict) else None
    if not isinstance(errors, list):
        return ""
    fields: list[str] = []
    for entry in errors:
        if not isinstance(entry, dict):
            continue
        loc = entry.get("loc")
        where = ".".join(str(part) for part in loc if part != "body") if isinstance(loc, list) else ""
        fields.append(f"{where}: {entry.get('msg', '')}".strip(": ").strip())
    return "; ".join(field for field in fields if field)


def _retry_after(response: httpx.Response) -> float | None:
    try:
        seconds = float(response.headers.get("retry-after", ""))
    except ValueError:
        return None
    return seconds if seconds > 0 else None


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def error_from_response(response: httpx.Response, *, is_send: bool) -> TurboNotifyError:
    """Build the error for a non-2xx response: API error code first, human description after."""
    status = response.status_code
    payload = _payload_of(response)
    body = payload if isinstance(payload, dict) else {}

    raw_code = body.get("error")
    if isinstance(raw_code, dict):
        code = _text(raw_code.get("code")) or f"http_{status}"
        description = _text(raw_code.get("message"))
    else:
        code = _text(raw_code) or f"http_{status}"
        description = ""
    description = description or _text(body.get("message"))
    hint = _text(body.get("hint"))
    if hint and hint not in description:
        description = f"{description} {hint}".strip()
    if code == "validation_error":
        description = _validation_fields(body) or description
    description = description or response.reason_phrase or "The request did not complete."

    retry_after = None
    if code == "insufficient_scope":
        scope = _text(body.get("required_scope"))
        needs = f"the '{scope}' scope" if scope else "a scope it does not have"
        description = f"{description} The API key needs {needs}."
    elif status == httpx.codes.TOO_MANY_REQUESTS:
        retry_after = _retry_after(response)
        wait = f"Retry after {retry_after:g} seconds." if retry_after else "Wait a moment and try again."
        description = f"{description} {wait}"
    elif status >= _SERVER_ERROR_STATUS and is_send:
        description = f"{description} {_SEND_SERVER_HINT}"
    return TurboNotifyError(description, code, status=status, retry_after=retry_after)


class TurboNotifyClient:
    """One authenticated connection to a Turbo Notify number."""

    def __init__(self, *, api_key: str | None, base_url: str | None, number_alias: str | None) -> None:
        self._api_key = require_api_key(api_key)
        self._base_url = normalize_base_url(base_url)
        self._number_alias = require_number_alias(number_alias)

    def number_path(self, suffix: str = "") -> str:
        """Return ``/numbers/{ref}`` plus ``suffix`` with the alias safely encoded."""
        return f"/numbers/{quote(self._number_alias, safe='')}{suffix}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call ``/v1{path}`` and return the decoded JSON object."""
        is_send = method != "GET"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        timeout = WRITE_TIMEOUT_SECONDS if is_send else READ_TIMEOUT_SECONDS
        try:
            async with make_http_client(timeout) as http:
                response = await http.request(
                    method, f"{self._base_url}/v1{path}", json=body, params=params, headers=headers
                )
        except httpx.TimeoutException:
            msg = f"Turbo Notify did not answer within {timeout:g} seconds."
            if is_send:
                msg = f"{msg} {_SEND_SERVER_HINT}"
            raise TurboNotifyError(msg, "timeout") from None
        except httpx.HTTPError:
            msg = "Could not reach Turbo Notify. Check the Base URL and the network of this Langflow server."
            raise TurboNotifyError(msg, "unreachable") from None

        if response.status_code >= _HTTP_ERROR_STATUS:
            raise error_from_response(response, is_send=is_send)
        payload = _payload_of(response)
        if not isinstance(payload, dict):
            msg = "Turbo Notify returned something other than a JSON object."
            raise TurboNotifyError(msg, "unexpected_response", status=response.status_code)
        return payload
