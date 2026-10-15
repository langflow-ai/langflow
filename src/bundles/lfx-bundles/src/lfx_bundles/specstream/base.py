"""Shared HTTP plumbing for the SpecStream components.

SpecStream turns a request written in plain words into a finished list: every row that matches, each
with the page it was read from. A list is priced per matching row, and the price ceiling is quoted
before anything runs. The calls are: read the request, quote it, approve the quote with the ceiling
the user set, poll the run, read the rows. The host is fixed (``api.specstream.ai``), so there is no
user-supplied URL to guard.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any
from urllib.parse import quote, urlencode

import httpx

BASE_URL = "https://api.specstream.ai"
DOCUMENTATION_URL = "https://specstream.ai/docs/api"
WORKSPACE_LIST_URL = "https://specstream.ai/workspace/collections/"
USER_AGENT = "langflow-specstream/1.0"
# A list runs for up to about five minutes, so the component waits a little longer than that by default.
DEFAULT_WAIT_SECONDS = 420
DEFAULT_POLL_SECONDS = 3.0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 60.0
FINISHED = frozenset({"completed", "partial"})
STOPPED = frozenset({"failed", "cancelled", "canceled", "expired"})
# Fields every row carries; a column with the same name is renamed so it cannot overwrite them.
RESERVED = frozenset({"list_id", "list_link", "position", "source_url", "checked_at"})
# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 500


class SpecStreamError(ValueError):
    """SpecStream refused a call, or answered with something this component cannot read."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        return str(value.get_secret_value() or "")
    return str(value or "")


def list_link(find_id: str) -> str:
    return f"{WORKSPACE_LIST_URL}{quote(find_id, safe='')}"


def _dollars(cents: int) -> str:
    return f"${cents / 100:.2f}"


def flatten_row(find_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """Return one row as flat fields: each column's label holds what the list shows, plus where it was read."""
    row: dict[str, Any] = {"list_id": find_id, "position": record.get("ordinal")}
    source: dict[str, Any] | None = None
    for cell in record.get("details") or record.get("cells") or []:
        label = str(cell.get("label") or cell.get("column_id") or "").strip()
        if not label:
            continue
        if label in RESERVED:
            label = f"{label} (column)"
        if cell.get("absence"):
            value: Any = ""
        elif cell.get("display") is not None:
            value = cell["display"]
        else:
            value = cell.get("value") if cell.get("value") is not None else ""
        row[label] = value
        provenance = cell.get("provenance") or {}
        if source is None and str(provenance.get("source_url") or "").startswith("http"):
            source = provenance
    row["source_url"] = source.get("source_url", "") if source else ""
    row["checked_at"] = source.get("observed_at", "") if source else ""
    row["list_link"] = list_link(find_id)
    return row


def _error_detail(response: httpx.Response) -> str:
    detail = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        detail = str(error.get("message") or "")
    elif isinstance(error, str):
        detail = error
    if not detail:
        detail = response.text
    detail = " ".join(detail.split())
    return detail[:_ERROR_DETAIL_LIMIT] + "..." if len(detail) > _ERROR_DETAIL_LIMIT else detail


class SpecStreamClient:
    """Minimal Bearer-token client for the SpecStream REST API."""

    def __init__(
        self,
        api_key: Any,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = secret_value(api_key).strip()
        if not self.api_key:
            msg = "SpecStream API key is required. Create one under Agents & API in your SpecStream workspace."
            raise SpecStreamError(msg)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client

    def request(
        self, method: str, path: str, body: dict[str, Any] | None = None, *, allow_404: bool = False
    ) -> dict[str, Any] | None:
        key = self.api_key
        headers = {
            "Authorization": key if key.lower().startswith("bearer ") else f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        try:
            if self._client is not None:
                response = self._client.request(method, self.base_url + path, json=body, headers=headers)
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.request(method, self.base_url + path, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            msg = f"SpecStream did not answer within {self.timeout:g} seconds."
            raise SpecStreamError(msg) from exc
        except httpx.HTTPError as exc:
            msg = f"Couldn't reach SpecStream: {exc}"
            raise SpecStreamError(msg) from exc
        if allow_404 and response.status_code == httpx.codes.NOT_FOUND:
            return None
        if response.is_error:
            detail = _error_detail(response)
            msg = f"SpecStream answered {response.status_code}" + (f": {detail}" if detail else "")
            raise SpecStreamError(msg)
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            msg = "SpecStream returned a response this component couldn't read."
            raise SpecStreamError(msg)
        return payload["data"]

    def results(self, find_id: str) -> dict[str, Any]:
        """Return every row found so far for a list, following the pages."""
        rows: list[dict[str, Any]] = []
        cursor: str | None = None
        status = "running"
        while True:
            query = {"limit": "100", **({"cursor": cursor} if cursor else {})}
            path = f"/v1/finds/{quote(find_id, safe='')}/rows?{urlencode(query)}"
            page = self.request("GET", path) or {}
            status = page.get("status") or status
            rows.extend(flatten_row(find_id, record) for record in page.get("rows") or [])
            cursor = page.get("next_cursor")
            if not cursor:
                break
        return {"list_id": find_id, "status": status, "list_link": list_link(find_id), "rows": rows}

    def find_list(
        self,
        request: str,
        *,
        max_results: int,
        max_price_usd: float,
        run_key: str = "",
        wait_seconds: float = DEFAULT_WAIT_SECONDS,
        poll_interval: float = DEFAULT_POLL_SECONDS,
        locale: str = "en-US",
    ) -> dict[str, Any]:
        """Read, quote, approve within the ceiling, wait, and return the rows.

        Raises:
            SpecStreamError: If nothing could be run: the request is unclear, the quote is above the
                ceiling, or SpecStream refused a call. In the first two cases nothing was bought.
        """
        q = (request or "").strip()
        if not q:
            msg = "Describe the list to find."
            raise SpecStreamError(msg)
        if max_results < 1:
            msg = "Number of results must be 1 or more."
            raise SpecStreamError(msg)
        max_cents = round(float(max_price_usd) * 100)
        if max_cents <= 0:
            msg = "Maximum price (USD) must be greater than 0."
            raise SpecStreamError(msg)

        now = time.time()
        user_key = (run_key or "").strip()
        if user_key:
            candidates = [f"langflow-{user_key}"]
        else:
            # The same request with the same limits gets the run it already started in this hour or the one
            # before, so a retried step never buys the list twice, even across the turn of the hour.
            def key_for(at: float) -> str:
                hour = time.strftime("%Y-%m-%dT%H", time.gmtime(at))
                digest = hashlib.sha256(f"{q}|{max_results}|{max_cents}|{hour}".encode()).hexdigest()[:32]
                return f"langflow-{digest}"

            candidates = [key_for(now), key_for(now - 3600)]

        existing: dict[str, Any] | None = None
        for candidate in candidates:
            existing = self.request("GET", f"/v1/capacity/requests/{quote(candidate, safe='')}", allow_404=True)
            if existing and existing.get("find_id"):
                break
        if existing and existing.get("find_id"):
            find_id = existing["find_id"]
            maximum_cents = int(existing.get("maximum_cents") or max_cents)
        else:
            reading = self.request("POST", "/v1/parse", {"q": q, "locale": locale}) or {}
            if reading.get("status") != "runnable":
                read_as = reading.get("canonical_sentence") or q
                msg = (
                    f'SpecStream needs a clearer request before it can price it. It read: "{read_as}". '
                    "Add the place or what every row must meet. Nothing ran."
                )
                raise SpecStreamError(msg)
            priced = (
                self.request(
                    "POST",
                    "/v1/capacity/quotes",
                    {"ast_hash": reading["ast_hash"], "operation": "find", "requested_units": max_results},
                )
                or {}
            )
            maximum_cents = int(priced.get("maximum_cents") or 0)
            if maximum_cents > max_cents:
                msg = (
                    f"Nothing ran: this list can cost up to {_dollars(maximum_cents)}, above the maximum of "
                    f"{_dollars(max_cents)}. Ask for fewer results or raise Maximum price (USD)."
                )
                raise SpecStreamError(msg)
            run = (
                self.request(
                    "POST",
                    "/v1/capacity/executions",
                    {
                        "quote_id": priced["quote_id"],
                        "quote_hash": priced["quote_hash"],
                        "confirm_max_cents": maximum_cents,
                        "idempotency_key": candidates[0],
                    },
                )
                or {}
            )
            find_id = run["find_id"]

        deadline = time.monotonic() + max(0.0, float(wait_seconds))
        while True:
            result = self.results(find_id)
            if result["status"] in FINISHED | STOPPED or time.monotonic() >= deadline:
                break
            time.sleep(poll_interval)
        result.update({"request": q, "maximum_price_usd": maximum_cents / 100})
        return result
