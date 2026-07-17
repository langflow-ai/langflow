"""Live model discovery and credential validation for the OpenAI Compatible provider.

The provider targets any endpoint that speaks the OpenAI HTTP API shape
(OpenRouter, Together, Groq, self-hosted vLLM/TGI/LM Studio, ...), so models
are discovered from the endpoint's ``/v1/models`` route and credentials are
validated with a probe request. Both callables are referenced by dotted path
from the bundle's ``extension.json`` provider spec and invoked lazily by lfx's
provider registry, so importing this module is cheap and only happens when the
provider is actually used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests
from lfx.base.models.model_metadata import create_model_metadata
from lfx.base.models.model_utils import MIN_DEFAULT_MODELS, get_provider_variable_value
from lfx.log.logger import logger
from lfx.utils.ssrf_protection import validate_connector_url_for_ssrf

if TYPE_CHECKING:
    from uuid import UUID

_TIMEOUT_SECONDS = 5
_PROVIDER = "OpenAI Compatible"
_ICON = "Plug"


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


def fetch_live_openai_compatible_models(user_id: UUID | str | None, model_type: str = "llm") -> list[dict]:
    """Return models served by the user's OpenAI-compatible endpoint, tagged with ``model_type``.

    The ``/v1/models`` route does not distinguish chat from embedding models, so
    every served model is returned and tagged with the requested ``model_type``;
    the unified catalog fetches once per type, so a model is offered in both the
    Language Model and Embedding Model pickers. Returns an empty list (never
    raises) when the endpoint is unset or unreachable, so a missing or broken
    endpoint simply contributes no models.
    """
    base_url = get_provider_variable_value(user_id, "OPENAI_COMPATIBLE_BASE_URL")
    if not base_url:
        return []
    try:
        api_key = get_provider_variable_value(user_id, "OPENAI_COMPATIBLE_API_KEY")
    except Exception:  # noqa: BLE001 - API key is optional for local servers; never block discovery on it
        api_key = None

    try:
        models_url = _models_url(base_url)
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        validate_connector_url_for_ssrf(models_url)
        response = requests.get(models_url, headers=headers, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
        model_names = _parse_model_names(response.json())
        return [
            create_model_metadata(
                provider=_PROVIDER,
                name=name,
                icon=_ICON,
                model_type=model_type,
                tool_calling=model_type == "llm",
                default=i < MIN_DEFAULT_MODELS,
            )
            for i, name in enumerate(model_names)
        ]
    except Exception:  # noqa: BLE001 - degrade to "no live models" on any transport/parse error
        logger.debug(f"Could not fetch live OpenAI-compatible {model_type} models from {base_url}")
        return []


def validate_openai_compatible_credentials(
    provider: str,  # noqa: ARG001 - registry validator contract
    variables: dict[str, str],
    model_name: str | None = None,  # noqa: ARG001 - registry validator contract
) -> None:
    """Validate the configured endpoint by probing ``/v1/models``.

    Raises ``ValueError`` with an actionable message on a missing URL,
    authentication failure, connection error, timeout, or any other HTTP or
    transport failure. ``provider`` and ``model_name`` are part of the registry
    validator contract but unused here.
    """
    base_url = variables.get("OPENAI_COMPATIBLE_BASE_URL")
    if not base_url:
        msg = "Invalid OpenAI-compatible base URL"
        logger.error(msg)
        raise ValueError(msg)

    models_url = _models_url(base_url)
    headers: dict[str, str] = {}
    api_key = variables.get("OPENAI_COMPATIBLE_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        validate_connector_url_for_ssrf(models_url)
        response = requests.get(models_url, headers=headers, timeout=_TIMEOUT_SECONDS)
        if response.status_code in (401, 403):
            msg = "Authentication failed for the OpenAI-compatible endpoint. Check OPENAI_COMPATIBLE_API_KEY."
            logger.error(msg)
            raise ValueError(msg)
        response.raise_for_status()
    except requests.ConnectionError as e:
        msg = (
            f"Could not connect to the OpenAI-compatible endpoint at {base_url.rstrip('/')}. "
            "Please check that the server is running and the URL is correct."
        )
        logger.error(msg)
        raise ValueError(msg) from e
    except requests.Timeout as e:
        msg = f"Connection to the OpenAI-compatible endpoint at {base_url.rstrip('/')} timed out."
        logger.error(msg)
        raise ValueError(msg) from e
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        msg = (
            f"The OpenAI-compatible endpoint at {base_url.rstrip('/')} returned HTTP {status} for {models_url}. "
            "Check that the base URL points to an OpenAI-compatible API."
        )
        logger.error(msg)
        raise ValueError(msg) from e
    except requests.RequestException as e:
        msg = f"Could not validate the OpenAI-compatible endpoint at {base_url.rstrip('/')}: {e}"
        logger.error(msg)
        raise ValueError(msg) from e
