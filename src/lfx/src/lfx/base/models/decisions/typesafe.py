"""Authenticated TypeSafe model discovery; cache entries never cross credentials."""

import hashlib
from copy import deepcopy
from threading import RLock

import httpx
from cachetools import TTLCache, cached

from lfx.base.models.decision_constants import decision_model_metadata
from lfx.base.models.decisions.schema import DecisionConfigurationError
from lfx.base.models.provider_ssrf import provider_httpx_client_kwargs
from lfx.utils.ssrf_protection import SSRFProtectionError


@cached(cache=TTLCache(maxsize=128, ttl=120), key=lambda key: hashlib.sha256(key.encode()).hexdigest(), lock=RLock())
def _catalog(api_key: str) -> list[dict]:
    url = "https://api.typesafe.ai/v1/models"
    try:
        kwargs, _ = provider_httpx_client_kwargs(url)
        with httpx.Client(**kwargs) as client:
            response = client.get(
                url, headers={"Authorization": f"Bearer {api_key}"}, timeout=10, follow_redirects=False
            )
        response.raise_for_status()
        body = response.json()
        rows = body.get("models") if isinstance(body, dict) else None
        if not isinstance(rows, list):
            raise TypeError
        models = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"].strip():
                raise ValueError
            models[row["name"]] = decision_model_metadata("TypeSafe", row["name"], "Bot", default=True)
        return list(models.values())
    except (httpx.HTTPError, SSRFProtectionError, ValueError, TypeError):
        msg = "Could not load TypeSafe decision models. Check the TypeSafe API key and try refreshing again."
        raise DecisionConfigurationError(msg) from None


def get_models(api_key: str) -> list[dict]:
    if not api_key or not (api_key.isascii() and api_key.isprintable()):
        msg = "Enter a valid TypeSafe API key to load decision models."
        raise DecisionConfigurationError(msg)
    return deepcopy(_catalog(api_key))
