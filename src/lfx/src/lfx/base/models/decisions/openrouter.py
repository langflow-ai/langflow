"""OpenRouter is authoritative for its decision model IDs, including newly added models."""

from copy import deepcopy
from threading import RLock

import httpx
from cachetools import TTLCache, cached

from lfx.base.models.decisions.schema import DecisionConfigurationError
from lfx.base.models.model_metadata import create_model_metadata
from lfx.utils.ssrf_httpx import ssrf_safe_httpx_get
from lfx.utils.ssrf_protection import SSRFProtectionError


def model_metadata(name: str, *, default: bool = False) -> dict:
    """Describe the request types exposed by the gateway, not a per-model guarantee."""
    return {
        **create_model_metadata(
            provider="OpenRouter", name=name, icon="OpenRouter", model_type="decision", default=default
        ),
        "capabilities": ["choice", "boolean", "score"],
    }


@cached(cache=TTLCache(maxsize=1, ttl=120), lock=RLock())
def _catalog() -> list[dict]:
    # The catalog is public: never resolve or send a user's credential to discover models.
    try:
        response = ssrf_safe_httpx_get(
            "https://openrouter.ai/api/v1/models?output_modalities=decisions", timeout=10, follow_redirects=False
        )
        response.raise_for_status()
        body = response.json()
        rows = body.get("data") if isinstance(body, dict) else None
        if not isinstance(rows, list):
            raise TypeError
        models = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
                raise ValueError
            modalities = (row.get("architecture") or {}).get("output_modalities", [])
            if "decisions" not in modalities:
                continue
            models[row["id"]] = model_metadata(row["id"], default=True)
        return [models[name] for name in sorted(models)]
    except (httpx.HTTPError, SSRFProtectionError, ValueError, TypeError, AttributeError):
        msg = "Could not load OpenRouter decision models. Try refreshing the model list again."
        raise DecisionConfigurationError(msg) from None


def get_models() -> list[dict]:
    """Cache successful public reads briefly, without exposing mutable cached rows."""
    return deepcopy(_catalog())
