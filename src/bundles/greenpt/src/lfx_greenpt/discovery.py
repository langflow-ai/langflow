"""Live model discovery and credential validation for GreenPT."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from lfx.base.models.model_metadata import create_model_metadata
from lfx.base.models.model_utils import MIN_DEFAULT_MODELS, get_provider_variable_value
from lfx.log.logger import logger
from lfx.utils.ssrf_httpx import ssrf_safe_httpx_get

from lfx_greenpt.models import GREENPT_BASE_URL

if TYPE_CHECKING:
    from uuid import UUID

MODELS_URL = f"{GREENPT_BASE_URL}/models"
_TIMEOUT_SECONDS = 5
_PROVIDER = "GreenPT"
_ICON = "GreenPT"
_FEATURED_MODELS = ("glm-5.2", "kimi-k2.7-code")


def _parse_model_names(payload: object) -> list[str]:
    """Return unique model ids with GreenPT's flagship models first."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return []
    names = {
        item["id"]
        for item in payload["data"]
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
    }
    return sorted(names, key=lambda name: (_FEATURED_MODELS.index(name) if name in _FEATURED_MODELS else 2, name))


def fetch_live_greenpt_models(user_id: UUID | str | None, model_type: str = "llm") -> list[dict]:
    """Return current GreenPT models tagged for Langflow's requested picker.

    The OpenAI-compatible models response has no reliable capability metadata,
    so every discovered model is offered for each requested model type.
    """
    try:
        api_key = get_provider_variable_value(user_id, "GREENPT_API_KEY")
    except Exception:  # noqa: BLE001 - unset credentials should not break the provider catalog
        return []
    if not api_key:
        return []

    try:
        response = ssrf_safe_httpx_get(
            MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
        response.raise_for_status()
        names = _parse_model_names(response.json())
        return [
            create_model_metadata(
                provider=_PROVIDER,
                name=name,
                icon=_ICON,
                model_type=model_type,
                tool_calling=model_type == "llm",
                default=index < MIN_DEFAULT_MODELS,
            )
            for index, name in enumerate(names)
        ]
    except Exception:  # noqa: BLE001 - unavailable discovery should degrade to an empty live catalog
        logger.debug(f"Could not fetch live GreenPT {model_type} models")
        return []


def validate_greenpt_credentials(
    provider: str,  # noqa: ARG001 - registry validator contract
    variables: dict[str, str],
    model_name: str | None = None,  # noqa: ARG001 - registry validator contract
) -> None:
    """Validate a GreenPT API key against the models endpoint."""
    api_key = variables.get("GREENPT_API_KEY")
    if not api_key:
        msg = "A GreenPT API key is required."
        raise ValueError(msg)

    try:
        response = ssrf_safe_httpx_get(
            MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
        if response.status_code in (401, 403):
            msg = "GreenPT authentication failed. Check GREENPT_API_KEY."
            raise ValueError(msg)
        response.raise_for_status()
    except ValueError:
        raise
    except httpx.TimeoutException as e:
        msg = "GreenPT credential validation timed out."
        raise ValueError(msg) from e
    except httpx.RequestError as e:
        msg = "Could not connect to the GreenPT API."
        raise ValueError(msg) from e
    except httpx.HTTPStatusError as e:
        msg = f"GreenPT credential validation returned HTTP {e.response.status_code}."
        raise ValueError(msg) from e
