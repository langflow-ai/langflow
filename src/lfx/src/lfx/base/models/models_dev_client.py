"""Client for fetching live model data from models.dev API.

This module provides functionality to fetch, cache, and transform model data
from the models.dev API into the format used by the unified models system.
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from lfx.log.logger import logger

from .model_metadata import ModelCost, ModelLimits, ModelMetadata, ModelModalities

# API Configuration
MODELS_DEV_API_URL = "https://models.dev/api.json"
CACHE_TTL_SECONDS = 3600  # 1 hour cache TTL
CACHE_FILE_NAME = ".models_dev_cache.json"

# Maps provider_id to display name and icon (icon names match display names)
# Icon keys come from lazyIconImports.ts in frontend/src/icons/
PROVIDER_MAP = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "ollama": "Ollama",
    "ibm-watsonx": "WatsonxAI",
}


def _get_cache_path() -> Path:
    """Get the path for the cache file."""
    return Path.home() / ".cache" / "langflow" / CACHE_FILE_NAME


def _load_cache() -> dict[str, Any] | None:
    """Load cached data from disk if valid."""
    cache_path = _get_cache_path()
    if not cache_path.exists():
        return None

    try:
        with cache_path.open() as f:
            cache_data = json.load(f)

        # Check if cache is still valid
        cached_at = cache_data.get("cached_at", 0)
        if time.time() - cached_at > CACHE_TTL_SECONDS:
            return None

        return cache_data.get("data")
    except (OSError, json.JSONDecodeError) as e:
        logger.debug(f"Failed to load models.dev cache: {e}")
        return None


def _save_cache(data: dict[str, Any]) -> None:
    """Save data to disk cache."""
    cache_path = _get_cache_path()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w") as f:
            json.dump({"cached_at": time.time(), "data": data}, f)
    except OSError as e:
        logger.debug(f"Failed to save models.dev cache: {e}")


def fetch_models_dev_data(*, force_refresh: bool = False) -> dict[str, Any]:
    """Fetch model data from models.dev API.

    Args:
        force_refresh: If True, bypass cache and fetch fresh data.

    Returns:
        Dictionary containing all provider and model data from the API.
    """
    # Try cache first
    if not force_refresh:
        cached = _load_cache()
        if cached is not None:
            logger.debug("Using cached models.dev data")
            return cached

    # Fetch from API
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(MODELS_DEV_API_URL)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch models.dev data: {e}")
        # Try to return stale cache if available
        cached = _load_cache()
        if cached is not None:
            logger.info("Using stale cache due to API error")
            return cached
        return {}
    else:
        # Cache the result
        _save_cache(data)
        logger.info("Successfully fetched models.dev data")
        return data


def _is_embedding_model(model_data: dict[str, Any]) -> bool:
    """Determine if a model is an embedding model based on multiple signals.

    We require multiple signals to avoid false positives (e.g., user defaulting
    output cost to 0 without knowing actual cost).

    Embedding model characteristics (from data analysis):
    - Zero output cost (embeddings produce vectors, not text)
    - No tool_call support (embeddings never call tools)
    - Small output limit (embedding dimensions are typically <= 4096)
    - No temperature support (not always reliable)
    - Model ID contains "embed" or "bge" (known embedding patterns)
    """
    model_id = model_data.get("id", "").lower()
    # Check for known embedding model patterns in name
    has_embed_in_name = "embed" in model_id or "bge" in model_id

    cost = model_data.get("cost", {})
    has_zero_output_cost = cost.get("output", -1) == 0

    has_no_tool_call = model_data.get("tool_call") is False

    has_no_temperature = model_data.get("temperature") is False or "temperature" not in model_data

    # Output limit check - embedding dimensions are typically <= 4096
    # LLM output limits are typically 8192+
    # Skip this check for known embedding patterns (data may have incorrect limits)
    limit = model_data.get("limit", {})
    output_limit = limit.get("output", 0)
    has_small_output_limit = output_limit <= 4096

    # Known embedding pattern + at least one other signal (ignore output limit for these)
    if has_embed_in_name and (has_zero_output_cost or has_no_tool_call or has_no_temperature):
        return True
    # Zero output cost + no tool calling + reasonable output limit
    if has_zero_output_cost and has_no_tool_call and has_small_output_limit:
        return True
    return False


def _determine_model_type(model_data: dict[str, Any]) -> str:
    """Determine the model type based on modalities and cost structure."""
    modalities = model_data.get("modalities", {})
    output_types = modalities.get("output", ["text"])

    if "image" in output_types and "text" not in output_types:
        return "image"
    if "audio" in output_types and "text" not in output_types:
        return "audio"
    if "video" in output_types:
        return "video"
    if _is_embedding_model(model_data):
        return "embeddings"
    return "llm"


def _transform_cost(cost_data: dict[str, Any] | None) -> ModelCost | None:
    """Transform API cost data to ModelCost format."""
    if not cost_data:
        return None

    return ModelCost(
        input=cost_data.get("input", 0),
        output=cost_data.get("output", 0),
        reasoning=cost_data.get("reasoning"),
        cache_read=cost_data.get("cache_read"),
        cache_write=cost_data.get("cache_write"),
        input_audio=cost_data.get("input_audio"),
        output_audio=cost_data.get("output_audio"),
    )


def _transform_limits(limit_data: dict[str, Any] | None) -> ModelLimits | None:
    """Transform API limit data to ModelLimits format."""
    if not limit_data:
        return None

    return ModelLimits(
        context=limit_data.get("context", 0),
        output=limit_data.get("output", 0),
    )


def _transform_modalities(modalities_data: dict[str, Any] | None) -> ModelModalities | None:
    """Transform API modalities data to ModelModalities format."""
    if not modalities_data:
        return None

    return ModelModalities(
        input=modalities_data.get("input", ["text"]),
        output=modalities_data.get("output", ["text"]),
    )


def transform_api_model_to_metadata(
    provider_id: str,
    provider_data: dict[str, Any],
    model_id: str,
    model_data: dict[str, Any],
) -> ModelMetadata:
    """Transform API model data to ModelMetadata format.

    Args:
        provider_id: The provider ID from the API (e.g., "openai")
        provider_data: The provider data from the API
        model_id: The model ID from the API
        model_data: The model data from the API

    Returns:
        ModelMetadata object with transformed data
    """
    provider_name = PROVIDER_MAP.get(provider_id, provider_data.get("name", provider_id.title()))
    icon = PROVIDER_MAP.get(provider_id, "Bot")  # Default to "Bot" if no custom icon

    # Determine model type
    model_type = _determine_model_type(model_data)

    # Build metadata
    metadata = ModelMetadata(
        # Core identification
        provider=provider_name,
        provider_id=provider_id,
        name=model_id,
        display_name=model_data.get("name", model_id),
        icon=icon,
        # Capabilities
        tool_calling=model_data.get("tool_call", False),
        reasoning=model_data.get("reasoning", False),
        structured_output=model_data.get("structured_output", False),
        temperature=model_data.get("temperature", True),
        attachment=model_data.get("attachment", False),
        # Status flags
        preview="-preview" in model_id.lower() or "beta" in model_id.lower(),
        deprecated=False,
        default=False,
        open_weights=model_data.get("open_weights", False),
        # Model classification
        model_type=model_type,
    )

    # Add extended metadata
    cost = _transform_cost(model_data.get("cost"))
    if cost:
        metadata["cost"] = cost

    limits = _transform_limits(model_data.get("limit"))
    if limits:
        metadata["limits"] = limits

    modalities = _transform_modalities(model_data.get("modalities"))
    if modalities:
        metadata["modalities"] = modalities

    if model_data.get("knowledge"):
        metadata["knowledge_cutoff"] = model_data["knowledge"]
    if model_data.get("release_date"):
        metadata["release_date"] = model_data["release_date"]
    if model_data.get("last_updated"):
        metadata["last_updated"] = model_data["last_updated"]

    # Provider metadata (only api_base and env_vars at model level, documentation_url is at provider level)
    if provider_data.get("api"):
        metadata["api_base"] = provider_data["api"]
    if provider_data.get("env"):
        metadata["env_vars"] = provider_data["env"]

    return metadata


def get_live_models_detailed(
    *,
    providers: list[str] | None = None,
    model_types: list[str] | None = None,
    force_refresh: bool = False,
) -> list[ModelMetadata]:
    """Get live model metadata from models.dev API.

    Args:
        providers: Optional list of provider IDs to filter by
        model_types: Optional list of model types to filter by ("llm", "embeddings", etc.)
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        List of ModelMetadata objects for all matching models
    """
    api_data = fetch_models_dev_data(force_refresh=force_refresh)
    if not api_data:
        return []

    models: list[ModelMetadata] = []

    for provider_id, provider_data in api_data.items():
        # Skip if filtering by provider and this one isn't included
        if providers and provider_id not in providers:
            continue

        provider_models = provider_data.get("models", {})
        for model_id, model_data in provider_models.items():
            metadata = transform_api_model_to_metadata(provider_id, provider_data, model_id, model_data)

            # Filter by model type if specified
            if model_types and metadata.get("model_type") not in model_types:
                continue

            models.append(metadata)

    return models


@lru_cache(maxsize=1)
def get_provider_metadata_from_api() -> dict[str, dict[str, Any]]:
    """Get provider metadata from the API for all providers.

    Returns:
        Dictionary mapping provider names to their metadata
    """
    api_data = fetch_models_dev_data()
    if not api_data:
        return {}

    provider_metadata = {}
    for provider_id, provider_data in api_data.items():
        provider_name = PROVIDER_MAP.get(provider_id, provider_data.get("name", provider_id.title()))
        icon = PROVIDER_MAP.get(provider_id, "Bot")

        env_vars = provider_data.get("env", [])
        variable_name = env_vars[0] if env_vars else f"{provider_id.upper()}_API_KEY"

        provider_metadata[provider_name] = {
            "icon": icon,
            "variable_name": variable_name,
            "api_base": provider_data.get("api"),
            "documentation_url": provider_data.get("doc"),
            "provider_id": provider_id,
        }

    return provider_metadata


def clear_cache() -> None:
    """Clear the models.dev cache (both disk and in-memory)."""
    cache_path = _get_cache_path()
    try:
        if cache_path.exists():
            cache_path.unlink()
            logger.info("Cleared models.dev disk cache")
    except OSError as e:
        logger.warning(f"Failed to clear disk cache: {e}")

    # Also clear the in-memory lru_cache
    get_provider_metadata_from_api.cache_clear()
    logger.debug("Cleared models.dev in-memory cache")


def get_models_by_provider(provider_id: str, *, force_refresh: bool = False) -> list[ModelMetadata]:
    """Get all models for a specific provider.

    Args:
        provider_id: The provider ID (e.g., "openai", "anthropic")
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        List of ModelMetadata objects for the provider's models
    """
    return get_live_models_detailed(providers=[provider_id], force_refresh=force_refresh)


def search_models(
    query: str,
    *,
    providers: list[str] | None = None,
    model_types: list[str] | None = None,
    force_refresh: bool = False,
) -> list[ModelMetadata]:
    """Search for models by name or display name.

    Args:
        query: Search query string
        providers: Optional list of provider IDs to filter by
        model_types: Optional list of model types to filter by
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        List of matching ModelMetadata objects
    """
    all_models = get_live_models_detailed(
        providers=providers,
        model_types=model_types,
        force_refresh=force_refresh,
    )

    query_lower = query.lower()
    return [
        model
        for model in all_models
        if query_lower in model.get("name", "").lower() or query_lower in model.get("display_name", "").lower()
    ]
