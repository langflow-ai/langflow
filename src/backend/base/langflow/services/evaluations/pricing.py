"""Token cost from catalog prices only; an unknown price yields None, never a guess."""

from __future__ import annotations

from typing import Any

from lfx.base.models.models_dev_catalog import MODELS_DEV_PROVIDER_KEYS, get_active_snapshot

TOKENS_PER_MILLION = 1_000_000
_SLUG_BY_PROVIDER = {display: slug for slug, display in MODELS_DEV_PROVIDER_KEYS.items()}


def model_identity(selection: Any) -> dict[str, Any] | None:
    """The first model dict of a unified model selection (``[{name, provider, metadata}]``)."""
    if isinstance(selection, list) and selection and isinstance(selection[0], dict):
        return selection[0]
    if isinstance(selection, dict) and selection.get("name"):
        return selection
    return None


def _snapshot_prices(provider: str, name: str) -> tuple[float, float] | None:
    slug = _SLUG_BY_PROVIDER.get(provider)
    snapshot = get_active_snapshot()
    if slug is None or not isinstance(snapshot, dict):
        return None
    models = (snapshot.get(slug) or {}).get("models")
    entry = models.get(name) if isinstance(models, dict) else None
    cost = entry.get("cost") if isinstance(entry, dict) else None
    if not isinstance(cost, dict):
        return None
    price_in, price_out = cost.get("input"), cost.get("output")
    if isinstance(price_in, (int, float)) and isinstance(price_out, (int, float)):
        return float(price_in), float(price_out)
    return None


def prices_per_million(model: dict[str, Any]) -> tuple[float, float] | None:
    metadata = model.get("metadata") or {}
    price_in = metadata.get("cost_per_million_in")
    price_out = metadata.get("cost_per_million_out")
    if isinstance(price_in, (int, float)) and isinstance(price_out, (int, float)):
        return float(price_in), float(price_out)
    provider, name = model.get("provider"), model.get("name")
    if isinstance(provider, str) and isinstance(name, str):
        return _snapshot_prices(provider, name)
    return None


def cost_usd(model: dict[str, Any] | None, input_tokens: int, output_tokens: int) -> float | None:
    if model is None:
        return None
    prices = prices_per_million(model)
    if prices is None:
        return None
    price_in, price_out = prices
    return (input_tokens * price_in + output_tokens * price_out) / TOKENS_PER_MILLION
