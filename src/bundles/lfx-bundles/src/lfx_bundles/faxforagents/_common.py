"""Shared HTTP layer for the Fax for Agents components (https://faxforagents.com/docs/api/).

Every refusal from the API is an ``error`` envelope with a stable ``code``. The components return it
as data with the remedy the hosted MCP server gives for the same code, so a flow sees what to do next.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.faxforagents.com"
ID_RE = re.compile(r"^[a-z]{2,8}_[0-9a-f]{32}$")
E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")
TERMINAL_STATES = frozenset({"delivered", "partial", "failed", "unknown"})
HTTP_ERROR_FLOOR = 400

REMEDIES = {
    "invalid_token": "The API key was rejected. Use an ffa_test_... or ffa_live_... key from app.faxforagents.com.",
    "scope_missing": "This key lacks the scope the call needs. Ask the key's owner for a key that has it.",
    "not_found": "No such id in your organization, or it was deleted.",
    "approval_required": (
        "No approval and no policy allows this send. A person approves the quote in the dashboard, "
        "then pass the approval id to the component."
    ),
    "approval_expired": "The approval expired with its quote. Quote again and ask for a new approval.",
    "approval_mismatch": "The approval was given for a different send.",
    "approval_consumed": "This approval was already used. One approval, one send.",
    "insufficient_balance": "The wallet does not cover this fax. A person tops it up in the dashboard.",
    "quote_expired": "The quote expired (10 minutes). Run the component again.",
    "rate_limited": "Rate limit reached. Run again in a few seconds; the idempotency key makes it safe.",
}


class FaxForAgentsError(Exception):
    """A refusal from the API, with the stable ``code`` and a remedy in the message."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{REMEDIES.get(code, message)} (error_code={code}, http {status})")
        self.status = status
        self.code = code


async def call_api(
    api_key: str,
    method: str,
    path: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """One authenticated call. ``None`` values are dropped from the body and the query string."""
    key = (api_key or "").strip()
    if not key:
        msg = "A Fax for Agents API key is required."
        raise FaxForAgentsError(401, "invalid_token", msg)
    all_headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "langflow-faxforagents-bundle/1.0",
        **(headers or {}),
    }
    body = {k: v for k, v in (json or {}).items() if v is not None} if json is not None else None
    query = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method, f"{base_url.rstrip('/')}{path}", json=body, params=query, headers=all_headers
        )
    if response.status_code >= HTTP_ERROR_FLOOR:
        code, message = "http_error", f"HTTP {response.status_code}"
        try:
            error = (response.json() or {}).get("error") or {}
            code = error.get("code") or code
            message = error.get("message") or message
        except ValueError:
            pass
        raise FaxForAgentsError(response.status_code, code, message)
    return response.json() if response.content else {}


def require_id(value: str, name: str) -> str:
    text = (value or "").strip()
    if not ID_RE.match(text):
        msg = f"{name} is not a Fax for Agents id (a prefix, an underscore and 32 hex characters)."
        raise ValueError(msg)
    return text


def agent_evidence(job: dict[str, Any]) -> dict[str, Any]:
    """The carrier's raw payload (the signed webhook body and its headers) stays on the REST receipt."""
    evidence = job.get("evidence")
    if isinstance(evidence, dict):
        return {**job, "evidence": {k: v for k, v in evidence.items() if k not in ("body", "headers")}}
    return job


def error_data(exc: Exception) -> dict[str, Any]:
    """The shape every component returns when a call fails: the flow keeps running and sees why."""
    if isinstance(exc, FaxForAgentsError):
        return {"error": str(exc), "error_code": exc.code, "http_status": exc.status}
    return {"error": str(exc)}
