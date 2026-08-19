"""Shared client construction and response handling for the MrScraper components.

The SDK is an optional dependency, and every one of its methods returns the same
HTTP envelope.  Both concerns live here so the eight components stay consistent
with each other rather than each re-deriving the convention.
"""

from __future__ import annotations

from typing import Any

MISSING_SDK_MSG = "Could not import mrscraper SDK. Please install it with `pip install mrscraper-sdk`."


def build_client(token: str) -> Any:
    """Return an SDK client, or raise an error naming the package to install."""
    try:
        from mrscraper import MrScraper
    except ImportError as e:
        raise ImportError(MISSING_SDK_MSG) from e
    return MrScraper(token=token)


def payload(response: Any, *, scalar_key: str = "result") -> dict[str, Any]:
    """Return what the API sent, without the SDK's transport envelope.

    ``MrScraper._parse`` wraps every response as ``{"status_code", "data",
    "headers"}``.  A flow wants the payload, not the transport metadata, and the
    SDK raises on any non-2xx status, so the status code carries no information
    by the time a component sees it.

    A non-dict payload (``fetch_html`` yields text when the response is not JSON)
    is boxed under ``scalar_key`` so the return value is always a mapping, which
    is what ``Data`` accepts.
    """
    unwrapped = response.get("data", response) if isinstance(response, dict) else response
    return unwrapped if isinstance(unwrapped, dict) else {scalar_key: unwrapped}


def result_rows(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the row list from a paginated payload, for tabular output.

    The results endpoint returns rows alongside pagination metadata.  The key
    holding the rows is picked by shape rather than by name so that a rename on
    the API side degrades to a single-row frame instead of raising.
    """
    for value in page.values():
        if isinstance(value, list) and all(isinstance(row, dict) for row in value):
            return value
    return [page]
