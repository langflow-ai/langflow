"""Shared client construction and response handling for the MrScraper components.

The SDK is an optional dependency, and every one of its methods returns the same
HTTP envelope. Both concerns live here so the three components stay consistent
with each other rather than each re-deriving the convention.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, quote_plus

MISSING_SDK_MSG = "Could not import mrscraper SDK. Please install it with `pip install 'mrscraper-sdk>=0.6.0,<0.7.0'`."


def build_client(token: str) -> Any:
    """Return an SDK client, or raise an error naming the package to install."""
    if not isinstance(token, str) or not token.strip():
        msg = "MrScraper API token is required"
        raise ValueError(msg)
    try:
        from mrscraper import MrScraper
    except ImportError as e:
        raise ImportError(MISSING_SDK_MSG) from e
    return MrScraper(token=token.strip())


async def call_sdk(token: str, method: str, **kwargs: Any) -> Any:
    """Call the optional SDK without exposing configured credentials in errors."""
    client = build_client(token)
    from mrscraper import APIError, MrScraperError

    try:
        return await getattr(client, method)(**kwargs)
    except MrScraperError as exc:
        values = [token, token.strip(), *(kwargs.get(key) for key in ("proxy", "cookie_jar", "discard_token_secret"))]
        headers = kwargs.get("headers")
        if isinstance(headers, str):
            values.append(headers)
            try:
                headers = json.loads(headers)
            except (ValueError, TypeError):
                headers = None
        if isinstance(headers, dict):
            values.extend(headers.values())
            values.append(json.dumps(headers))
        variants = set()
        for value in values:
            if isinstance(value, str) and value:
                escaped_values = {value, json.dumps(value)[1:-1], json.dumps(value, ensure_ascii=False)[1:-1]}
                for escaped_value in escaped_values:
                    variants.update((escaped_value, quote(escaped_value, safe=""), quote_plus(escaped_value)))
        message = str(exc)
        for value in sorted(variants, key=len, reverse=True):
            message = message.replace(value, "[REDACTED]")
        if isinstance(exc, APIError):
            raise APIError(message, status_code=exc.status_code) from None
        raise type(exc)(message) from None


def payload(response: Any, *, scalar_key: str = "result") -> dict[str, Any]:
    """Return what the API sent, without the SDK's transport envelope.

    ``MrScraper._parse`` wraps every response as ``{"status_code", "data",
    "headers"}``.  A flow wants the payload, not the transport metadata, and the
    SDK raises on any non-2xx status, so the status code carries no information
    by the time a component sees it.

    A non-dict payload (``scraper_api`` yields text when the response is not JSON)
    is boxed under ``scalar_key`` so the return value is always a mapping, which
    is what ``Data`` accepts.
    """
    unwrapped = response.get("data", response) if isinstance(response, dict) else response
    return unwrapped if isinstance(unwrapped, dict) else {scalar_key: unwrapped}


def optional_integer(value: str, *, name: str) -> int | None:
    """Keep blank optional numeric fields unset, while preserving explicit zero."""
    if not value.strip():
        return None
    try:
        return int(value)
    except ValueError as exc:
        msg = f"{name} must be an integer"
        raise ValueError(msg) from exc
