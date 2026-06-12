from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote, urlparse

import httpx

DEFAULT_API_BASE_URL = "https://api.junglegrid.dev"
DEFAULT_TIMEOUT_SECONDS = 30.0
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500
WORKLOAD_TYPES = ("inference", "training", "fine_tuning", "batch")
ROUTING_MODES = ("cost", "speed", "balanced")
JOB_INPUT_KINDS = ("input", "script")

SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "callback_auth_token",
    "callback_secret",
    "download_url",
    "environment",
    "headers",
    "signed_url",
    "temporary_url",
    "token",
    "upload_url",
    "url",
}


class JungleGridError(ValueError):
    """Represent a sanitized validation, network, or Jungle Grid API error."""


def normalize_base_url(api_base_url: str | None) -> str:
    """Validate and normalize a Jungle Grid API origin.

    Args:
        api_base_url: Configured API origin, or None to use production.

    Returns:
        A normalized HTTPS origin without a trailing slash.

    Raises:
        JungleGridError: If the value is not a path-free HTTPS origin.
    """
    base_url = (api_base_url or DEFAULT_API_BASE_URL).strip().rstrip("/")
    parsed = urlparse(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.path not in ("", "/")
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        msg = "Jungle Grid API base URL must be a valid path-free HTTPS URL with a hostname."
        raise JungleGridError(msg)
    return base_url


def require_text(value: Any, display_name: str) -> str:
    """Return a trimmed required string."""
    if value is None or not isinstance(value, str) or not value.strip():
        msg = f"{display_name} is required."
        raise JungleGridError(msg)
    return value.strip()


def optional_text(value: Any) -> str | None:
    """Return a trimmed optional string without coercing structured values."""
    if value is None:
        return None
    if not isinstance(value, str):
        msg = "Expected a string value."
        raise JungleGridError(msg)
    text = value.strip()
    return text or None


def path_segment(value: Any, display_name: str) -> str:
    """Encode a required identifier for safe use as one URL path segment."""
    return quote(require_text(value, display_name), safe="")


def parse_json_field(value: Any, display_name: str, expected_type: type | tuple[type, ...]) -> Any | None:
    """Parse a JSON input while preserving already structured values and empty collections."""
    if value is None or value == "":
        return None
    if isinstance(value, expected_type):
        return value
    if not isinstance(value, str):
        msg = f"{display_name} must be valid JSON."
        raise JungleGridError(msg)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        msg = f"{display_name} must be valid JSON."
        raise JungleGridError(msg) from exc
    if not isinstance(parsed, expected_type):
        expected = "array" if expected_type is list else "object"
        msg = f"{display_name} must be a JSON {expected}."
        raise JungleGridError(msg)
    return parsed


def validate_string_array(value: Any, display_name: str, *, allow_empty: bool = True) -> list[str] | None:
    """Parse and validate an optional JSON array containing non-empty strings."""
    parsed = parse_json_field(value, display_name, list)
    if parsed is None:
        return None
    if not allow_empty and not parsed:
        msg = f"{display_name} must contain at least one string."
        raise JungleGridError(msg)
    if any(not isinstance(item, str) or not item.strip() for item in parsed):
        msg = f"{display_name} must contain only non-empty strings."
        raise JungleGridError(msg)
    return [item.strip() for item in parsed]


def validate_command(value: Any) -> list[str] | str | None:
    """Validate a preferred command array while retaining legacy string commands."""
    if value is None or value == "":
        return None
    if isinstance(value, list):
        return validate_string_array(value, "Command", allow_empty=False)
    if not isinstance(value, str):
        msg = "Command must be a JSON array of non-empty strings or a legacy command string."
        raise JungleGridError(msg)
    text = value.strip()
    if not text:
        return None
    if text.startswith("["):
        return validate_string_array(text, "Command", allow_empty=False)
    return text


def validate_environment(value: Any) -> dict[str, str] | None:
    """Validate an environment object without exposing any values in errors."""
    parsed = parse_json_field(value, "Environment", dict)
    if parsed is None:
        return None
    if any(not isinstance(key, str) or not key.strip() for key in parsed):
        msg = "Environment variable names must be non-empty strings."
        raise JungleGridError(msg)
    if any(not isinstance(item, str) for item in parsed.values()):
        msg = "Environment must be a JSON object with string values."
        raise JungleGridError(msg)
    return parsed


def validate_input_references(value: Any, display_name: str) -> list[dict[str, str]] | None:
    """Normalize uploaded input IDs into the API's object-reference format."""
    parsed = parse_json_field(value, display_name, list)
    if parsed is None:
        return None
    references: list[dict[str, str]] = []
    for item in parsed:
        if isinstance(item, str):
            input_id = item.strip()
        elif isinstance(item, dict):
            if any(key in item for key in ("path", "file_path", "filename")):
                msg = f"{display_name} accepts managed input IDs, not host filesystem paths."
                raise JungleGridError(msg)
            input_id_value = item.get("input_id")
            input_id = input_id_value.strip() if isinstance(input_id_value, str) else ""
        else:
            input_id = ""
        if not input_id:
            msg = f"{display_name} items must include a non-empty input_id."
            raise JungleGridError(msg)
        if "/" in input_id or "\\" in input_id:
            msg = f"{display_name} accepts managed input IDs, not host filesystem paths."
            raise JungleGridError(msg)
        references.append({"input_id": input_id})
    return references


def validate_expected_artifacts(value: Any) -> list[str] | None:
    """Validate managed output paths under /workspace/artifacts."""
    paths = validate_string_array(value, "Expected Artifacts")
    if paths is None:
        return None
    if any(not path.startswith("/workspace/artifacts/") for path in paths):
        msg = "Expected Artifacts paths must be under /workspace/artifacts/."
        raise JungleGridError(msg)
    return paths


def normalize_workload_type(value: Any) -> str:
    """Normalize canonical and legacy fine-tuning spellings for the REST API."""
    workload_type = require_text(value, "Workload Type")
    if workload_type == "fine-tuning":
        return workload_type
    if workload_type not in WORKLOAD_TYPES:
        msg = f"Workload Type must be one of: {', '.join(WORKLOAD_TYPES)}."
        raise JungleGridError(msg)
    return "fine-tuning" if workload_type == "fine_tuning" else workload_type


def sanitize(value: Any) -> Any:
    """Recursively redact credentials and temporary URLs from structured values."""
    if isinstance(value, dict):
        return {
            key: "[redacted]" if str(key).lower() in SENSITIVE_KEYS else sanitize(item) for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def sanitize_text(text: str, *secrets: str | None) -> str:
    """Remove known secrets, credentials, and temporary URLs from free-form text."""
    sanitized = text
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[redacted]")
    sanitized = re.sub(r"https?://[^\s\"'<>]+", "[redacted-url]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bBearer\s+\S+", "Bearer [redacted]", sanitized, flags=re.IGNORECASE)
    return re.sub(
        r"\b(token|api[_ -]?key|secret)=([^\s,;&]+)",
        r"\1=[redacted]",
        sanitized,
        flags=re.IGNORECASE,
    )


class JungleGridClient:
    """Small async REST client shared by all Jungle Grid components."""

    def __init__(self, api_key: str, api_base_url: str | None = None) -> None:
        """Initialize a client with a server-side Bearer credential."""
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
        """Send one API request and return an unwrapped JSON object."""
        if not path.startswith("/") or "://" in path:
            msg = "Jungle Grid request path must be an absolute API path."
            raise JungleGridError(msg)
        url = f"{self.api_base_url}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                response = await client.request(method, url, headers=headers, json=json_body, params=params)
        except httpx.TimeoutException as exc:
            msg = "Jungle Grid request timed out."
            raise JungleGridError(msg) from exc
        except httpx.RequestError as exc:
            msg = f"Jungle Grid network error: {sanitize_text(str(exc), self.api_key)}"
            raise JungleGridError(msg) from exc

        if response.status_code >= HTTP_BAD_REQUEST:
            code, detail = self._safe_error_detail(response)
            msg = f"Jungle Grid API error {response.status_code} ({code}): {detail}"
            raise JungleGridError(msg)
        if response.status_code == httpx.codes.NO_CONTENT:
            return {}

        try:
            parsed = response.json()
        except ValueError as exc:
            msg = "Jungle Grid returned a non-JSON response."
            raise JungleGridError(msg) from exc
        if not isinstance(parsed, dict):
            msg = "Jungle Grid returned JSON that was not an object."
            raise JungleGridError(msg)
        if parsed.get("ok") is True and "data" in parsed:
            data = parsed["data"]
            if not isinstance(data, dict):
                msg = "Jungle Grid returned an unexpected response envelope."
                raise JungleGridError(msg)
            return data
        return parsed

    def _safe_error_detail(self, response: httpx.Response) -> tuple[str, str]:
        """Extract only safe error codes and messages from API failures."""
        fallback_code = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            429: "RATE_LIMITED",
        }.get(
            response.status_code,
            "UPSTREAM_ERROR" if response.status_code >= HTTP_INTERNAL_SERVER_ERROR else "API_ERROR",
        )
        try:
            parsed = response.json()
        except ValueError:
            return fallback_code, "The Jungle Grid API request failed."
        if not isinstance(parsed, dict):
            return fallback_code, "The Jungle Grid API request failed."
        error = parsed.get("error")
        record = error if isinstance(error, dict) else parsed
        code = record.get("code")
        message = record.get("message")
        safe_code = code.strip() if isinstance(code, str) and code.strip() else fallback_code
        safe_message = (
            message.strip() if isinstance(message, str) and message.strip() else "The Jungle Grid API request failed."
        )
        return sanitize_text(safe_code, self.api_key), sanitize_text(safe_message, self.api_key)


def build_query_params(**values: Any) -> dict[str, Any]:
    """Omit undefined query values while preserving valid zero values."""
    return {key: value for key, value in values.items() if value is not None and value != ""}
