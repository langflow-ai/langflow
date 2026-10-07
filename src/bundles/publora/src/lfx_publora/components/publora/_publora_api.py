import httpx

API_BASE_URL = "https://api.publora.com/api/v1"
USER_AGENT = "langflow-publora-bundle"
TIMEOUT_SECONDS = 30


class PubloraAPIError(Exception):
    """A Publora API request failed; the message is safe to show to the user."""


def _error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx Publora response, keeping the API's own error message.

    Publora errors carry ``{"error": "..."}``.
    """
    response = error.response
    detail = None
    try:
        payload = response.json()
        if isinstance(payload, dict):
            body_error = payload.get("error")
            if isinstance(body_error, str):
                detail = body_error
            elif isinstance(body_error, dict):
                detail = body_error.get("message") or body_error.get("code")
    except ValueError:
        detail = None
    reason = detail or response.reason_phrase or "request failed"
    return f"Publora API error {response.status_code}: {reason}"


def publora_request(method: str, path: str, api_key: str, json: dict | None = None) -> dict:
    """Call the Publora REST API and return the decoded JSON object.

    Raises ``PubloraAPIError`` for a missing key, an HTTP error, a transport
    error, or a response that is not a JSON object.
    """
    if not api_key:
        msg = "Publora API key is required. Create one on the API page of your Publora dashboard."
        raise PubloraAPIError(msg)

    headers = {
        "x-publora-key": api_key,
        "Accept": "application/json",
        # Identify the integration to the API; keeps traffic attributable.
        "User-Agent": USER_AGENT,
    }
    if json is not None:
        headers["Content-Type"] = "application/json"

    try:
        response = httpx.request(method, f"{API_BASE_URL}{path}", headers=headers, json=json, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as e:
        raise PubloraAPIError(_error_message(e)) from e
    except httpx.HTTPError as e:
        msg = f"Publora API request failed: {e}"
        raise PubloraAPIError(msg) from e
    except ValueError as e:
        msg = "Publora API returned a response that is not JSON."
        raise PubloraAPIError(msg) from e

    if not isinstance(payload, dict):
        msg = "Publora API returned an unexpected response (expected a JSON object)."
        raise PubloraAPIError(msg)
    return payload
