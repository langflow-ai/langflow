"""Shared HTTP code for the cloro components.

cloro returns Google search results with the AI Overview, and the answers that
ChatGPT, Google AI Mode, Bing AI Mode and Gemini give to a prompt, with the sources
they cite.
All components call the fixed host ``https://api.cloro.dev`` and send the API key
as a bearer token.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx
from lfx.schema.data import Data

API_BASE_URL = "https://api.cloro.dev"
DOCUMENTATION_URL = "https://cloro.dev/docs?utm_source=langflow&utm_medium=byok"
API_KEY_INFO = (
    "Your cloro API key. Create one at https://dashboard.cloro.dev/api-keys?utm_source=langflow&utm_medium=byok"
)
COUNTRY_INFO = "ISO 3166-1 alpha-2 country code, such as US or DE."
DEFAULT_COUNTRY = "US"
# Sync AI answers can take more than a minute.
ANSWER_TIMEOUT_SECONDS = 180.0

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "cloro rejected the API key (401)",
    403: "cloro refused the request (403)",
    429: "cloro concurrency limit reached (429)",
}


class CloroAPIError(Exception):
    """A cloro request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def _redact(text: str, api_key: str) -> str:
    return text.replace(api_key, "***") if api_key else text


def _error_message(response: httpx.Response, api_key: str) -> str:
    detail = ""
    try:
        body = response.json()
    except ValueError:
        detail = response.text.strip()
    else:
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            detail = ": ".join(str(error[field]) for field in ("code", "message") if error.get(field))
        elif error:
            detail = str(error)
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"cloro API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def cloro_request(path: str, payload: dict[str, Any], *, api_key: Any, timeout: float) -> dict[str, Any]:
    """POST ``payload`` to a cloro endpoint and return the ``result`` object of the response.

    Raises:
        CloroAPIError: On a missing key, a transport error, a non-2xx status, or an unexpected body.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter a cloro API key."
        raise CloroAPIError(msg)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{API_BASE_URL}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
            )
    except httpx.TimeoutException as exc:
        msg = f"cloro request timed out after {timeout:g} seconds."
        raise CloroAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the cloro API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise CloroAPIError(msg) from exc
    if not response.is_success:
        raise CloroAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "cloro API returned a response that is not JSON."
        raise CloroAPIError(msg) from exc
    result = body.get("result") if isinstance(body, dict) else None
    if not isinstance(result, dict):
        msg = "cloro API returned an unexpected response shape."
        raise CloroAPIError(msg)
    return result


def usable_url(value: Any) -> str:
    """Return ``value`` if it is an http(s) URL that is not a Google redirect, else an empty string."""
    url = str(value or "").strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return ""
    if parts.path.startswith("/goto") and "google." in parts.hostname:
        return ""
    return url


def sources_list(items: Any) -> list[dict[str, Any]]:
    """Keep the label and URL of each source that has a usable URL."""
    if not isinstance(items, list):
        return []
    sources = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = usable_url(item.get("url"))
        if url:
            sources.append({"label": str(item.get("label") or ""), "url": url})
    return sources


def fetch_answer(engine: str, path: str, *, prompt: Any, country: Any, api_key: Any, timeout: float) -> Data:
    """Ask an AI engine through cloro and return the answer and its sources as one ``Data``.

    The ``Data`` text holds the answer in markdown followed by a numbered list of the sources,
    so an agent that reads only the text still sees the sources.
    """
    prompt_text = str(prompt or "").strip()
    if not prompt_text:
        msg = "Enter a prompt."
        raise CloroAPIError(msg)
    payload = {
        "prompt": prompt_text,
        "country": str(country or DEFAULT_COUNTRY).strip().upper(),
        "include": {"markdown": True},
    }
    result = cloro_request(path, payload, api_key=api_key, timeout=timeout)
    answer = str(result.get("markdown") or result.get("text") or "")
    sources = sources_list(result.get("sources"))
    text = answer
    if sources:
        lines = [
            f"{index}. {source['label'] or source['url']}: {source['url']}" for index, source in enumerate(sources, 1)
        ]
        text = f"{answer}\n\nSources:\n" + "\n".join(lines)
    return Data(
        text=text,
        data={"engine": engine, "answer": answer, "sources": sources, "model": result.get("model")},
    )
