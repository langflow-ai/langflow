"""Shared HTTP plumbing for the Datacircle components.

Datacircle benchmarks the GTM APIs (email finders, enrichment, scraping and more)
and ranks every plan of each. Its API at the fixed host
``https://api.datacircle.dev/v1`` is open: no key and no account, at most 60
calls a minute from one address. Every call is a GET that answers JSON.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

API_BASE_URL = "https://api.datacircle.dev/v1"
DOCUMENTATION_URL = "https://datacircle.dev/api"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_LIMIT = 50
SORT_OPTIONS = ["score", "price", "provider"]

# The fields of a plan a table shows by default; "All Fields" keeps every one.
PLAN_FIELDS = (
    "rank",
    "provider",
    "plan",
    "api",
    "call",
    "score",
    "perThousand",
    "pay",
    "currency",
    "billing",
    "units",
    "unit",
    "strengths",
    "website",
    "pricingPage",
    "page",
)

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    404: "Datacircle found nothing for this (404)",
    429: "Datacircle rate limit exceeded (429): at most 60 calls a minute from one address",
}


class DatacircleAPIError(Exception):
    """A Datacircle request failed; the message is safe to show in the component output."""


def path_segment(value: Any) -> str:
    """Quote one URL path segment, so a slug can never change the path it is put in."""
    return quote(str(value or "").strip(), safe="")


def clamp_limit(value: Any, default: int = 10) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, 1), MAX_LIMIT)


def plan_row(plan: dict[str, Any], *, all_fields: bool = False) -> dict[str, Any]:
    """A plan as a table row: the main fields, or every field when asked."""
    if all_fields:
        return dict(plan)
    return {field: plan.get(field) for field in PLAN_FIELDS if field in plan}


def _error_message(response: httpx.Response) -> str:
    detail = ""
    try:
        body = response.json()
    except ValueError:
        detail = response.text.strip()
    else:
        if isinstance(body, dict):
            detail = str(body.get("error") or body.get("message") or "")
            slugs = body.get("slugs")
            if isinstance(slugs, list) and slugs:
                detail = f"{detail}. Known slugs: {', '.join(str(slug) for slug in slugs)}"
    detail = detail[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"Datacircle API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def datacircle_get(path: str, *, timeout: float, params: dict[str, Any] | None = None) -> Any:
    """GET ``API_BASE_URL + path`` and return the JSON body.

    Raises:
        DatacircleAPIError: On a transport error, a non-2xx status, or a body that is not JSON.
    """
    url = f"{API_BASE_URL}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, params=params, headers={"Accept": "application/json"})
    except httpx.TimeoutException as exc:
        msg = f"Datacircle request timed out after {timeout:g} seconds."
        raise DatacircleAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the Datacircle API: {type(exc).__name__}: {exc}"
        raise DatacircleAPIError(msg) from exc
    if not response.is_success:
        raise DatacircleAPIError(_error_message(response))
    try:
        return response.json()
    except ValueError as exc:
        msg = "Datacircle API returned a response that is not JSON."
        raise DatacircleAPIError(msg) from exc
