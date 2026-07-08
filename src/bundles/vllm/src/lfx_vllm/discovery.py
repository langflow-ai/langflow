"""Live model discovery and credential validation for the vLLM provider.

vLLM exposes an OpenAI-compatible HTTP API, so models are discovered from the
server's ``/v1/models`` endpoint and credentials are validated with a probe
request. Both callables are referenced by dotted path from the bundle's
``extension.json`` provider spec and invoked lazily by lfx's provider registry,
so importing this module is cheap and only happens when vLLM is actually used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests
from lfx.base.models.model_metadata import create_model_metadata
from lfx.base.models.model_utils import MIN_DEFAULT_MODELS, get_provider_variable_value
from lfx.log.logger import logger
from lfx.utils.ssrf_protection import validate_url_for_ssrf

if TYPE_CHECKING:
    from uuid import UUID

_TIMEOUT_SECONDS = 5
_PROVIDER = "vLLM"


def _models_url(base_url: str) -> str:
    """Return the ``/v1/models`` URL, tolerating a base that already ends in /v1."""
    base_url = base_url.rstrip("/")
    return f"{base_url}/models" if base_url.endswith("/v1") else f"{base_url}/v1/models"


def _parse_model_names(data: object) -> list[str]:
    """Parse model ids from an OpenAI-compatible ``{"data": [...]}`` or a plain list."""
    if isinstance(data, list):
        return sorted(str(m) for m in data if m)
    if isinstance(data, dict) and "data" in data:
        return sorted(m.get("id", "") for m in data["data"] if m.get("id"))
    return []


def fetch_live_vllm_models(user_id: UUID | str | None, model_type: str = "llm") -> list[dict]:
    """Return models served by the user's vLLM endpoint, tagged with ``model_type``.

    vLLM's API does not distinguish chat from embedding models, so every served
    model is returned and tagged with the requested ``model_type``; the unified
    catalog fetches once per type, so a model is offered in both the Language
    Model and Embedding Model pickers. Returns an empty list (never raises) when
    the endpoint is unset or unreachable, so a missing or broken vLLM server
    simply contributes no models.
    """
    base_url = get_provider_variable_value(user_id, "VLLM_API_BASE")
    if not base_url:
        return []
    try:
        api_key = get_provider_variable_value(user_id, "VLLM_API_KEY")
    except Exception:  # noqa: BLE001 - API key is optional for vLLM; never block discovery on it
        api_key = None

    try:
        models_url = _models_url(base_url)
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        validate_url_for_ssrf(models_url)
        response = requests.get(models_url, headers=headers, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
        model_names = _parse_model_names(response.json())
        return [
            create_model_metadata(
                provider=_PROVIDER,
                name=name,
                icon="vLLM",
                model_type=model_type,
                tool_calling=model_type == "llm",
                default=i < MIN_DEFAULT_MODELS,
            )
            for i, name in enumerate(model_names)
        ]
    except Exception:  # noqa: BLE001 - degrade to "no live models" on any transport/parse error
        logger.debug(f"Could not fetch live vLLM {model_type} models from {base_url}")
        return []


def validate_vllm_credentials(provider: str, variables: dict[str, str], model_name: str | None = None) -> None:  # noqa: ARG001
    """Validate the configured vLLM endpoint by probing ``/v1/models``.

    Raises ``ValueError`` with an actionable message on a missing URL,
    authentication failure, connection error, or timeout. ``provider`` and
    ``model_name`` are part of the registry validator contract but unused here.
    """
    base_url = variables.get("VLLM_API_BASE")
    if not base_url:
        msg = "Invalid vLLM API base URL"
        logger.error(msg)
        raise ValueError(msg)

    models_url = _models_url(base_url)
    headers: dict[str, str] = {}
    api_key = variables.get("VLLM_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        validate_url_for_ssrf(models_url)
        response = requests.get(models_url, headers=headers, timeout=_TIMEOUT_SECONDS)
        if response.status_code in (401, 403):
            msg = "Authentication failed for vLLM server. Check VLLM_API_KEY."
            logger.error(msg)
            raise ValueError(msg)
        response.raise_for_status()
    except requests.ConnectionError as e:
        msg = (
            f"Could not connect to vLLM server at {base_url.rstrip('/')}. "
            "Please check that the server is running and the URL is correct."
        )
        logger.error(msg)
        raise ValueError(msg) from e
    except requests.Timeout as e:
        msg = f"Connection to vLLM server at {base_url.rstrip('/')} timed out."
        logger.error(msg)
        raise ValueError(msg) from e
