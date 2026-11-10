"""Bounded HTTP reads. Account usage and source selection stay with the caller."""

import json

import httpx

MIN_QUERY_LENGTH = 2


class ArcmiraResponseError(RuntimeError):
    """The server response does not match the endpoint schema."""


class ArcmiraReadError(RuntimeError):
    def __init__(self, status, body, headers):
        self.status = status
        self.body = body
        self.headers = headers
        super().__init__(f"Arcmira HTTP {status}: {json.dumps(body, ensure_ascii=False)}")


def _redact(value, secret):
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]")
    if isinstance(value, list):
        return [_redact(item, secret) for item in value]
    if isinstance(value, dict):
        return {_redact(key, secret): _redact(item, secret) for key, item in value.items()}
    return value


async def read(api_key, path, parameters):
    if hasattr(api_key, "get_secret_value"):
        api_key = api_key.get_secret_value()
    if not isinstance(api_key, str) or not api_key.strip():
        msg = "An Arcmira API key is required. See https://arcmira.com/docs/authentication."
        raise ValueError(msg)
    if path not in ("search", "entities/resolve"):
        msg = "Unsupported read operation"
        raise ValueError(msg)
    if not isinstance(parameters.get("q"), str) or len(parameters["q"].strip()) < MIN_QUERY_LENGTH:
        msg = "Query must contain at least two characters"
        raise ValueError(msg)
    limit = parameters.get("limit", 5)
    maximum = 20 if path == "search" else 15
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
        msg = f"Limit must be an integer from 1 to {maximum}"
        raise ValueError(msg)
    params = {k: v for k, v in parameters.items() if v is not None and v != ""}
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            response = await client.get(
                "https://api.arcmira.com/v1/" + path,
                params=params,
                headers={"Authorization": "Bearer " + api_key, "Accept": "application/json"},
            )
    except httpx.RequestError:
        msg = "Arcmira request failed before a response; no automatic retry was made."
        raise RuntimeError(msg) from None
    try:
        body = response.json()
    except ValueError:
        msg = f"Arcmira returned a non-JSON response (HTTP {response.status_code})."
        raise RuntimeError(msg) from None
    if not response.is_success:
        safe_body = _redact(body, api_key)
        headers = {
            k: response.headers[k].replace(api_key, "[REDACTED]")
            for k in ("retry-after", "x-request-id")
            if k in response.headers
        }
        raise ArcmiraReadError(response.status_code, safe_body, headers)
    expected = "chunks" if path == "search" else "candidates"
    if not isinstance(body, dict) or not isinstance(body.get(expected), list):
        msg = "Arcmira returned an unexpected response shape"
        raise ArcmiraResponseError(msg)
    return body
