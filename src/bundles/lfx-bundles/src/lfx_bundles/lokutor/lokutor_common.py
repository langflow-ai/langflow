"""Shared helpers for the Lokutor speech components."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from lfx.base.models.provider_ssrf import ensure_credential_endpoint_allowed
from lfx.utils.file_path_security import component_file_access_scopes, enforce_local_file_access

if TYPE_CHECKING:
    import httpx

DEFAULT_BASE_URL = "https://api.lokutor.com/v1"
DOCUMENTATION_URL = "https://docs.lokutor.com"

# The nine languages Lokutor speech models cover (ISO 639-1).
LANGUAGES = ["en", "es", "ca", "gl", "eu", "pt", "fr", "it", "de"]
AUTO_LANGUAGE = "auto"

# The ten voice slots; any ``clone_...`` id from a Lokutor account is also accepted.
VOICES = ["F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5"]

_MAX_ERROR_CHARS = 500


def secret_value(value: object) -> str:
    """Return a plain string from a ``SecretStr``, a string or ``None``."""
    if value is None:
        return ""
    get_secret_value = getattr(value, "get_secret_value", None)
    if callable(get_secret_value):
        return str(get_secret_value()).strip()
    return str(value).strip()


def api_url(base_url: object, path: str) -> str:
    """Validate the configured base URL and return ``<base>/<path>``."""
    base = str(base_url or "").strip().rstrip("/") or DEFAULT_BASE_URL
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"}:
        msg = "Lokutor Base URL must use http or https."
        raise ValueError(msg)
    if not parsed.hostname:
        msg = "Lokutor Base URL must contain a valid host."
        raise ValueError(msg)
    if parsed.username or parsed.password:
        msg = "Lokutor Base URL must not contain embedded credentials."
        raise ValueError(msg)
    if parsed.query or parsed.fragment:
        msg = "Lokutor Base URL must not contain a query string or fragment."
        raise ValueError(msg)
    return f"{base}/{path.lstrip('/')}"


def require_api_key(api_key: object, base_url: object) -> str:
    """Return the API key, refusing to send an environment-sourced key to a custom host."""
    key = secret_value(api_key)
    if not key:
        msg = "Lokutor API Key is required."
        raise ValueError(msg)
    base = str(base_url or "").strip().rstrip("/")
    ensure_credential_endpoint_allowed(key, base or None, default_url=DEFAULT_BASE_URL)
    return key


def read_scoped_file(path_value: str, *, component: Any) -> bytes:
    """Read an uploaded file after Langflow's per-user/flow storage-scope check."""
    requested_path = Path(path_value)
    scope_ids = component_file_access_scopes(component)
    allowed_path = enforce_local_file_access(requested_path, scope_ids=scope_ids)
    try:
        resolved_path = allowed_path.resolve(strict=True)
        enforce_local_file_access(resolved_path, scope_ids=scope_ids)
        with resolved_path.open("rb") as handle:
            opened_stat = os.fstat(handle.fileno())
            current_stat = resolved_path.stat()
            if not stat.S_ISREG(opened_stat.st_mode) or not os.path.samestat(opened_stat, current_stat):
                msg = "Audio file changed while it was being opened."
                raise ValueError(msg)
            return handle.read()
    except (OSError, RuntimeError, TypeError) as e:
        msg = f"Audio file is not accessible: {e}"
        raise ValueError(msg) from e


def error_message(response: httpx.Response) -> str:
    """Build a readable error from a non-2xx Lokutor response (never echoes request headers)."""
    detail = ""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        inner = payload.get("detail", payload.get("error", payload))
        if isinstance(inner, dict):
            status = inner.get("status") or inner.get("code")
            message = inner.get("message")
            detail = ": ".join(str(part) for part in (status, message) if part)
        elif inner:
            detail = str(inner)
    if not detail:
        detail = response.text
    return f"Lokutor request failed with HTTP {response.status_code}: {detail[:_MAX_ERROR_CHARS]}"
