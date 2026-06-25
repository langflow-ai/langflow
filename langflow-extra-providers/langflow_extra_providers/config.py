"""Provider specifications for langflow-extra-providers.

Each entry describes one OpenAI-compatible provider. The shape is intentionally
small because every provider here speaks the OpenAI wire format and is
instantiated through ``langchain_openai.ChatOpenAI`` with a baked-in
``base_url``.

Defaults ship DeepSeek and GLM (Z.ai). You can override or extend them WITHOUT
editing this file via the ``LANGFLOW_EXTRA_PROVIDERS`` environment variable
(inline JSON or a path to a ``.json`` file). Set
``LANGFLOW_EXTRA_PROVIDERS_DISABLE_DEFAULTS=1`` to drop the built-ins and use
only your own.

Spec schema (per provider, keyed by display name):
    {
        "base_url": "https://api.example.com/v1",   # required
        "api_key_var": "EXAMPLE_API_KEY",            # required (global-variable / env key)
        "api_docs_url": "https://...",               # optional
        "icon": "OpenAI",                            # optional, frontend icon name
        "description": "...",                        # optional, shown in settings
        "default_headers": {"X-Title": "Langflow"},  # optional, sent on every call
        "models": [
            {"name": "model-id", "tool_calling": true, "reasoning": false},
            ...
        ]
    }
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("langflow_extra_providers")

# ---------------------------------------------------------------------------
# Built-in defaults
# ---------------------------------------------------------------------------

DEFAULT_PROVIDERS: dict[str, dict[str, Any]] = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "api_key_var": "DEEPSEEK_API_KEY",
        "api_docs_url": "https://api-docs.deepseek.com",
        "icon": "OpenAI",
        "description": "DeepSeek (OpenAI-compatible API). Configure DEEPSEEK_API_KEY.",
        "models": [
            {"name": "deepseek-chat", "tool_calling": True},
            {"name": "deepseek-reasoner", "tool_calling": True, "reasoning": True},
        ],
    },
    # GLM / Zhipu. Defaults to the international Z.ai OpenAI-compatible endpoint.
    # For the China endpoint use base_url "https://open.bigmodel.cn/api/paas/v4"
    # via the LANGFLOW_EXTRA_PROVIDERS override.
    "GLM (Z.ai)": {
        "base_url": "https://api.z.ai/api/paas/v4",
        "api_key_var": "GLM_API_KEY",
        "api_docs_url": "https://docs.z.ai/guides/llm/glm-4.6",
        "icon": "OpenAI",
        "description": "GLM / Z.ai (OpenAI-compatible API). Configure GLM_API_KEY.",
        "models": [
            {"name": "glm-4.6", "tool_calling": True},
            {"name": "glm-4.5", "tool_calling": True},
            {"name": "glm-4.5-air", "tool_calling": True},
            {"name": "glm-4-flash", "tool_calling": True},
        ],
    },
}

_ENV_SPECS = "LANGFLOW_EXTRA_PROVIDERS"
_ENV_DISABLE_DEFAULTS = "LANGFLOW_EXTRA_PROVIDERS_DISABLE_DEFAULTS"

_REQUIRED_KEYS = ("base_url", "api_key_var")


def _load_override() -> dict[str, dict[str, Any]]:
    """Parse the ``LANGFLOW_EXTRA_PROVIDERS`` env var (inline JSON or file path)."""
    raw = os.environ.get(_ENV_SPECS)
    if not raw or not raw.strip():
        return {}
    raw = raw.strip()
    text = raw
    # Treat a value that points at an existing file as a path.
    if not raw.startswith("{"):
        path = Path(raw).expanduser()
        if path.is_file():
            text = path.read_text(encoding="utf-8")
        else:
            logger.warning(
                "%s does not look like JSON and is not an existing file: %r", _ENV_SPECS, raw
            )
            return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse %s as JSON: %s", _ENV_SPECS, exc)
        return {}
    if not isinstance(data, dict):
        logger.warning("%s must be a JSON object keyed by provider name.", _ENV_SPECS)
        return {}
    return data


def _is_truthy(value: str | None) -> bool:
    return bool(value) and value.strip().lower() in {"1", "true", "yes", "on"}


def load_provider_specs() -> dict[str, dict[str, Any]]:
    """Return the merged, validated provider specs (defaults + env override)."""
    specs: dict[str, dict[str, Any]] = {}
    if not _is_truthy(os.environ.get(_ENV_DISABLE_DEFAULTS)):
        # Deep-ish copy so callers can't mutate the module defaults.
        for name, spec in DEFAULT_PROVIDERS.items():
            specs[name] = json.loads(json.dumps(spec))

    for name, spec in _load_override().items():
        if not isinstance(spec, dict):
            logger.warning("Ignoring %r: provider spec must be an object.", name)
            continue
        specs[name] = {**specs.get(name, {}), **spec}

    # Validate
    valid: dict[str, dict[str, Any]] = {}
    for name, spec in specs.items():
        missing = [k for k in _REQUIRED_KEYS if not spec.get(k)]
        if missing:
            logger.warning("Ignoring provider %r: missing required field(s) %s", name, missing)
            continue
        spec.setdefault("icon", "OpenAI")
        spec.setdefault("models", [])
        valid[name] = spec
    return valid
