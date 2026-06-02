from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlparse

import httpx

DEFAULT_API_BASE_URL = "https://api.junglegrid.dev"
DEFAULT_TIMEOUT_SECONDS = 30.0

SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "callback_auth_token",
    "download_url",
    "signed_url",
    "temporary_url",
    "url",
}


class JungleGridError(ValueError):
    """Sanitized Jungle Grid component error."""


def normalize_base_url(api_base_url: str | None) -> str:
    base_url = (api_base_url or DEFAULT_API_BASE_URL).strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        msg = "Jungle Grid API base URL must be a valid HTTPS URL."
        raise JungleGridError(msg)
    return base_url


def require_text(value: Any, display_name: str) -> str:
    if value is None or str(value).strip() == "":
        msg = f"{display_name} is required."
        raise JungleGridError(msg)
    return str(value).strip()


def path_segment(value: Any, display_name: str) -> str:
    return quote(require_text(value, display_name), safe="")


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_json_field(value: Any, display_name: str, expected_type: type | tuple[type, ...]) -> Any | None:
    text = optional_text(value)
    if text is None:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        msg = f"{display_name} must be valid JSON."
        raise JungleGridError(msg) from exc
    if not isinstance(parsed, expected_type):
        type_name = getattr(expected_type, "__name__", "the expected type")
        msg = f"{display_name} must be JSON matching {type_name}."
        raise JungleGridError(msg)
    return parsed


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                sanitized[key] = "[redacted]"
            else:
                sanitized[key] = sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def sanitize_text(text: str, *secrets: str | None) -> str:
    sanitized = text
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[redacted]")
    return sanitized


class JungleGridClient:
    def __init__(self, api_key: str, api_base_url: str | None = None) -> None:
        self.api_key = require_text(api_key, "Jungle Grid API Key")
        self.api_base_url = normalize_base_url(api_base_url)

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.api_base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                response = await client.request(method, url, headers=headers, json=json_body, params=params)
        except httpx.TimeoutException as exc:
            msg = "Jungle Grid request timed out."
            raise JungleGridError(msg) from exc
        except httpx.RequestError as exc:
            safe_message = sanitize_text(str(exc), self.api_key)
            msg = f"Jungle Grid network error: {safe_message}"
            raise JungleGridError(msg) from exc

        if response.status_code >= 400:
            detail = self._safe_error_detail(response)
            msg = f"Jungle Grid API error {response.status_code}: {detail}"
            raise JungleGridError(msg)

        try:
            parsed = response.json()
        except ValueError as exc:
            msg = "Jungle Grid returned a non-JSON response."
            raise JungleGridError(msg) from exc
        if not isinstance(parsed, dict):
            msg = "Jungle Grid returned JSON that was not an object."
            raise JungleGridError(msg)
        return parsed

    def _safe_error_detail(self, response: httpx.Response) -> str:
        try:
            parsed = response.json()
        except ValueError:
            text = response.text.strip()
            return sanitize_text(text[:500] or "No error detail returned.", self.api_key)
        safe = sanitize(parsed)
        return sanitize_text(json.dumps(safe, sort_keys=True)[:1000], self.api_key)


def build_workload_payload(
    *,
    name: Any,
    image: Any,
    workload_type: Any,
    model_size_gb: Any,
    command: Any = None,
    args: Any = None,
    optimize_for: Any = None,
) -> dict[str, Any]:
    try:
        model_size = float(model_size_gb)
    except (TypeError, ValueError) as exc:
        msg = "Model Size GB must be a valid number."
        raise JungleGridError(msg) from exc
    payload: dict[str, Any] = {
        "name": require_text(name, "Name"),
        "image": require_text(image, "Image"),
        "workload_type": require_text(workload_type, "Workload Type"),
        "model_size_gb": model_size,
    }
    if command_value := optional_text(command):
        payload["command"] = command_value
    if args_value := parse_json_field(args, "Args", list):
        payload["args"] = args_value
    if optimize_for_value := optional_text(optimize_for):
        payload["optimize_for"] = optimize_for_value
    return payload


def build_query_params(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value not in (None, "")}
