import asyncio
import time
from typing import Any
from urllib.parse import urljoin
from uuid import UUID

import httpx
import requests

from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS, create_model_metadata
from lfx.base.models.watsonx_constants import (
    IBM_WATSONX_URLS,
)
from lfx.base.models.watsonx_constants import (
    WATSONX_DEFAULT_EMBEDDING_MODELS as WATSONX_EMBEDDING_METADATA,
)
from lfx.base.models.watsonx_constants import (
    WATSONX_DEFAULT_LLM_MODELS as WATSONX_LLM_METADATA,
)
from lfx.log.logger import logger
from lfx.services.deps import get_variable_service, session_scope
from lfx.utils.async_helpers import run_until_complete
from lfx.utils.secrets import unwrap_secret_value
from lfx.utils.util import transform_localhost_url

HTTP_STATUS_OK = 200
MIN_DEFAULT_MODELS = 5

# Ollama model lists are cached in-process for a short window so that:
# (1) overlapping ``/api/v1/models`` requests don't all serialize through
#     Ollama's tags + per-model show endpoints, and
# (2) downstream callers (UI, Agent picker, embed picker) that all fan out
#     to the same catalog within a few seconds share one upstream round-trip.
# Cache key is (base_url, capability) so different bases / capability filters
# stay isolated. TTL is short enough that newly-pulled models surface
# promptly; the previous 10s frontend poll became unnecessary once this cache
# landed.
_OLLAMA_MODEL_LIST_TTL_SECONDS = 30.0
_ollama_model_list_cache: dict[tuple[str, str], tuple[float, list[str]]] = {}


def _ollama_cache_get(key: tuple[str, str], *, now: float | None = None) -> list[str] | None:
    """Return the cached model list for *key* if still fresh; else None."""
    entry = _ollama_model_list_cache.get(key)
    if entry is None:
        return None
    timestamp, value = entry
    current = now if now is not None else time.monotonic()
    if (current - timestamp) >= _OLLAMA_MODEL_LIST_TTL_SECONDS:
        return None
    # Return a copy so caller mutations don't leak into the cache.
    return list(value)


def _ollama_cache_set(key: tuple[str, str], value: list[str], *, now: float | None = None) -> None:
    current = now if now is not None else time.monotonic()
    _ollama_model_list_cache[key] = (current, list(value))


def _ollama_cache_clear() -> None:
    """Drop every cached entry. Exposed for tests; not called in production."""
    _ollama_model_list_cache.clear()


# Extract model names from metadata for fallback defaults
WATSONX_DEFAULT_LLM_MODEL_NAMES = [m["name"] for m in WATSONX_LLM_METADATA]
WATSONX_DEFAULT_EMBEDDING_MODEL_NAMES = [m["name"] for m in WATSONX_EMBEDDING_METADATA]


def _to_str(value: Any) -> str | None:
    """Safely coerce Message/Data or other values to string for URL/string params."""
    value = unwrap_secret_value(value)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "text"):
        return value.text or None
    return str(value) or None


def get_model_name(llm, display_name: str | None = "Custom"):
    attributes_to_check = ["model_name", "model", "model_id", "deployment_name"]

    # Skip attributes whose value is None/empty so providers like AzureChatOpenAI
    # (model_name=None, deployment_name=<actual>) and ChatWatsonx (model=None,
    # model_id=<actual>) resolve correctly instead of falling back to display_name.
    for attr in attributes_to_check:
        value = getattr(llm, attr, None)
        if value:
            return value
    return display_name


async def is_valid_ollama_url(url: str) -> bool:
    """Check if the provided URL is a valid Ollama API endpoint."""
    try:
        url = transform_localhost_url(url)
        if not url:
            return False
        # Strip /v1 suffix if present, as Ollama API endpoints are at root level
        url = url.rstrip("/").removesuffix("/v1")
        if not url.endswith("/"):
            url = url + "/"
        async with httpx.AsyncClient() as client:
            return (await client.get(url=urljoin(url, "api/tags"))).status_code == HTTP_STATUS_OK
    except httpx.RequestError:
        logger.debug(f"Invalid Ollama URL: {url}")
        return False


async def get_ollama_models(
    base_url_value: str, desired_capability: str, json_models_key: str, json_name_key: str, json_capabilities_key: str
) -> list[str]:
    """Fetch available completion models from the Ollama API.

    Filters out embedding models and only returns models with completion capability.

    Args:
        base_url_value (str): The base URL of the Ollama API.
        desired_capability (str): The desired capability of the model.
        json_models_key (str): The key in the JSON response that contains the models.
        json_name_key (str): The key in the JSON response that contains the model names.
        json_capabilities_key (str): The key in the JSON response that contains the model capabilities.

    Returns:
        list[str]: A sorted list of model names that support completion.

    Raises:
        ValueError: If there is an issue with the API request or response.
    """
    cache_key = (base_url_value, desired_capability)
    cached = _ollama_cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        # Strip /v1 suffix if present, as Ollama API endpoints are at root level
        base_url = base_url_value.rstrip("/").removesuffix("/v1")
        if not base_url.endswith("/"):
            base_url = base_url + "/"
        base_url = transform_localhost_url(base_url)

        # Ollama REST API to return models
        tags_url = urljoin(base_url, "api/tags")

        # Ollama REST API to return model capabilities
        show_url = urljoin(base_url, "api/show")

        async with httpx.AsyncClient() as client:
            # Fetch available models
            tags_response = await client.get(url=tags_url)
            tags_response.raise_for_status()
            models = tags_response.json()
            if asyncio.iscoroutine(models):
                models = await models
            await logger.adebug(f"Available models: {models}")

            candidates = [
                model.get(json_name_key) for model in models.get(json_models_key, []) if model.get(json_name_key)
            ]

            async def _has_capability(model_name: str) -> str | None:
                """Probe one model's capabilities. Returns its name on match, else None.

                Per-model failures are absorbed (logged at debug) so a single
                bad model does not poison the whole catalog response.
                """
                try:
                    show_response = await client.post(url=show_url, json={"model": model_name})
                    show_response.raise_for_status()
                    json_data = show_response.json()
                    if asyncio.iscoroutine(json_data):
                        json_data = await json_data
                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    await logger.adebug(f"Ollama /api/show failed for {model_name}: {e}")
                    return None
                capabilities = json_data.get(json_capabilities_key) or []
                if desired_capability in capabilities:
                    return model_name
                return None

            # Parallel fan-out: one POST /api/show per candidate, awaited
            # together so latency is bounded by the slowest single request
            # instead of N * avg-request-latency.
            results = await asyncio.gather(*(_has_capability(n) for n in candidates))
            model_ids = sorted(name for name in results if name)

    except (httpx.RequestError, ValueError) as e:
        msg = "Could not get model names from Ollama."
        await logger.aexception(msg)
        raise ValueError(msg) from e
    else:
        _ollama_cache_set(cache_key, model_ids)
        return model_ids


# ============================================================================
# Ollama Convenience Functions
# ============================================================================


async def get_ollama_llm_models(base_url: str) -> list[str]:
    """Fetch Ollama models with completion (LLM) capability.

    Args:
        base_url: The base URL of the Ollama API (e.g., "http://localhost:11434").

    Returns:
        A sorted list of model names that support text completion/chat.

    Raises:
        ValueError: If there is an issue with the API request or response.
    """
    return await get_ollama_models(
        base_url_value=base_url,
        desired_capability="completion",
        json_models_key="models",
        json_name_key="name",
        json_capabilities_key="capabilities",
    )


async def get_ollama_embedding_models(base_url: str) -> list[str]:
    """Fetch Ollama models with embedding capability.

    Args:
        base_url: The base URL of the Ollama API (e.g., "http://localhost:11434").

    Returns:
        A sorted list of model names that support embeddings.

    Raises:
        ValueError: If there is an issue with the API request or response.
    """
    return await get_ollama_models(
        base_url_value=base_url,
        desired_capability="embedding",
        json_models_key="models",
        json_name_key="name",
        json_capabilities_key="capabilities",
    )


# ============================================================================
# WatsonX Model Fetching Functions
# ============================================================================


def get_watsonx_llm_models(
    base_url: str,
    default_models: list[str] | None = None,
) -> list[str]:
    """Fetch WatsonX LLM models with chat capability.

    Args:
        base_url: The WatsonX API endpoint URL (e.g., "https://us-south.ml.cloud.ibm.com").
        default_models: Fallback models to return if API fetch fails.

    Returns:
        A sorted list of model IDs that support text chat.
    """
    if default_models is None:
        default_models = WATSONX_DEFAULT_LLM_MODEL_NAMES

    try:
        endpoint = f"{base_url}/ml/v1/foundation_model_specs"
        params = {
            "version": "2024-09-16",
            "filters": "function_text_chat,!lifecycle_withdrawn",
        }
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [model["model_id"] for model in data.get("resources", [])]
        return sorted(models)
    except Exception:  # noqa: BLE001
        logger.exception("Error fetching WatsonX LLM models. Using default models.")
        return default_models


def get_watsonx_embedding_models(
    base_url: str,
    default_models: list[str] | None = None,
) -> list[str]:
    """Fetch WatsonX embedding models.

    Args:
        base_url: The WatsonX API endpoint URL (e.g., "https://us-south.ml.cloud.ibm.com").
        default_models: Fallback models to return if API fetch fails.

    Returns:
        A sorted list of model IDs that support embeddings.
    """
    if default_models is None:
        default_models = WATSONX_DEFAULT_EMBEDDING_MODEL_NAMES

    try:
        endpoint = f"{base_url}/ml/v1/foundation_model_specs"
        params = {
            "version": "2024-09-16",
            "filters": "function_embedding,!lifecycle_withdrawn:and",
        }
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [model["model_id"] for model in data.get("resources", [])]
        return sorted(models)
    except Exception:  # noqa: BLE001
        logger.exception("Error fetching WatsonX embedding models. Using default models.")
        return default_models


def get_provider_variable_value(user_id: UUID | str | None, variable_key: str) -> str | None:
    """Get a variable value from global variables for a provider.

    Args:
        user_id: The user ID to look up global variables for
        variable_key: The variable key to look up (e.g., "OLLAMA_BASE_URL", "WATSONX_URL")

    Returns:
        The variable value if found, None otherwise. ``variable_service``
        raises ``ValueError`` when a variable is missing — for live-model
        probes (``fetch_live_ollama_models`` / ``fetch_live_watsonx_models``)
        a missing variable is not an error, it just means "no live models
        available for this provider," so we swallow the lookup error and
        return ``None`` to keep callers on their existing ``if not value:``
        guard. Without this, every embedding-model-options call from a
        non-Ollama user crashed retrieval (Knowledge component BUG-01).
    """
    if user_id is None or (isinstance(user_id, str) and user_id == "None"):
        return None

    async def _get_variable():
        async with session_scope() as session:
            variable_service = get_variable_service()
            if variable_service is None:
                return None
            try:
                return await variable_service.get_variable(
                    user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                    name=variable_key,
                    field="",
                    session=session,
                )
            except ValueError:
                # ``get_variable_object`` raises ValueError on missing var;
                # treat absence as "no value" rather than propagating.
                return None

    return _to_str(run_until_complete(_get_variable()))


def fetch_live_ollama_models(user_id: UUID | str | None, model_type: str = "llm") -> list[dict]:
    """Fetch live Ollama models from the configured Ollama instance.

    Args:
        user_id: The user ID to look up the Ollama base URL
        model_type: "llm" or "embeddings"

    Returns:
        List of model metadata dicts, or empty list if unable to fetch
    """
    # Get the configured Ollama base URL
    base_url = get_provider_variable_value(user_id, "OLLAMA_BASE_URL")
    if not base_url:
        return []

    try:
        if model_type == "llm":
            model_names = run_until_complete(get_ollama_llm_models(base_url))
        else:
            model_names = run_until_complete(get_ollama_embedding_models(base_url))

        # Convert to model metadata format
        return [
            create_model_metadata(
                provider="Ollama",
                name=name,
                icon="Ollama",
                model_type=model_type if model_type == "llm" else "embeddings",
                tool_calling=model_type == "llm",
                default=i < MIN_DEFAULT_MODELS,  # Mark first 5 as default
            )
            for i, name in enumerate(model_names)
        ]
    except Exception:  # noqa: BLE001
        logger.debug(f"Could not fetch live Ollama {model_type} models from {base_url}")
        return []


OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_FETCH_TIMEOUT = 10.0


def fetch_live_openrouter_models(user_id: UUID | str | None, model_type: str = "llm") -> list[dict]:
    """Fetch live OpenRouter models using the user's configured API key.

    Args:
        user_id: The user ID to look up the OpenRouter API key
        model_type: "llm" or "embeddings" (OpenRouter only supports llm)

    Returns:
        List of model metadata dicts, or empty list if unable to fetch.

    The ``tool_calling`` flag is derived per-model from OpenRouter's
    ``supported_parameters`` so Agent/LLM components that filter on it (for
    example ``get_language_model_options(tool_calling=True)``) show only the
    models that can actually run with tools. The ``default`` flag is set by
    intersecting the live catalog with the curated seed list in
    ``openrouter_constants`` so user-facing defaults stay sensible regardless
    of OpenRouter's id ordering — with a fallback to the first
    ``MIN_DEFAULT_MODELS`` ids when the seed list has gone stale.
    """
    from lfx.base.models.openrouter_constants import OPENROUTER_MODELS_DETAILED

    if model_type != "llm":
        return []

    api_key = get_provider_variable_value(user_id, "OPENROUTER_API_KEY")
    if not api_key:
        return []

    url = f"{OPENROUTER_API_BASE}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = httpx.get(url, headers=headers, timeout=OPENROUTER_FETCH_TIMEOUT)
        response.raise_for_status()
        raw_models = response.json().get("data", [])
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        # Surface as a warning (not debug) so a user who saved a key and sees
        # an empty model catalog has a server-side breadcrumb.
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        logger.warning("Could not fetch live OpenRouter models from %s (status=%s): %s", url, status_code, e)
        return []
    except (ValueError, TypeError) as e:
        # 200 with malformed JSON or an unexpected payload shape — degrade to
        # an empty catalog rather than crashing the caller.
        logger.warning("Malformed OpenRouter /models response from %s: %s", url, e)
        return []

    if not isinstance(raw_models, list):
        logger.warning("Unexpected OpenRouter /models payload (data is %s): %r", type(raw_models).__name__, raw_models)
        return []

    by_id: dict[str, dict] = {}
    for raw in raw_models:
        if not isinstance(raw, dict):
            continue
        mid = raw.get("id")
        if not mid:
            continue
        supported = raw.get("supported_parameters") or []
        is_list = isinstance(supported, list)
        created_raw = raw.get("created")
        # OpenRouter exposes ``created`` as a Unix epoch (seconds). Defensive
        # int-coercion handles the occasional string or null in the payload
        # without bringing the whole fetch down.
        try:
            created = int(created_raw) if created_raw is not None else 0
        except (TypeError, ValueError):
            created = 0
        by_id[mid] = {
            "tool_calling": is_list and "tools" in supported,
            # OpenRouter exposes "reasoning" (and "include_reasoning") in the
            # supported_parameters array for reasoning-capable models — same
            # signal shape as "tools". Drives the reasoning badge in the
            # picker and lets Agent/LLM components filter on it.
            "reasoning": is_list and "reasoning" in supported,
            "created": max(created, 0),
        }
    if not by_id:
        return []

    sorted_ids = sorted(by_id)
    seed_ids = {m["name"] for m in OPENROUTER_MODELS_DETAILED}
    intersected_defaults = seed_ids & by_id.keys()
    default_set = intersected_defaults or set(sorted_ids[:MIN_DEFAULT_MODELS])

    return [
        create_model_metadata(
            provider="OpenRouter",
            name=name,
            icon="OpenRouter",
            tool_calling=by_id[name]["tool_calling"],
            reasoning=by_id[name]["reasoning"],
            default=name in default_set,
            created=by_id[name]["created"],
        )
        for name in sorted_ids
    ]


def fetch_live_watsonx_models(user_id: UUID | str | None, model_type: str = "llm") -> list[dict]:
    """Fetch live WatsonX models from the configured WatsonX instance.

    Args:
        user_id: The user ID to look up the WatsonX URL
        model_type: "llm" or "embeddings"

    Returns:
        List of model metadata dicts, or empty list if unable to fetch
    """
    # Get the configured WatsonX URL
    watsonx_url = get_provider_variable_value(user_id, "WATSONX_URL")
    if not watsonx_url:
        # Try first default URL if none configured
        watsonx_url = IBM_WATSONX_URLS[0] if IBM_WATSONX_URLS else None
        if not watsonx_url:
            return []

    try:
        if model_type == "llm":
            model_names = get_watsonx_llm_models(watsonx_url)
        else:
            model_names = get_watsonx_embedding_models(watsonx_url)

        # Look up capability flags from the static catalog when known; otherwise
        # fall back to defaults. Without this, the live API path blanket-marks
        # every LLM as tool_calling=True, surfacing models like
        # ibm/granite-3b-code-instruct and ibm/granite-guardian-3-8b in the
        # Agent dropdown even though they don't support tool calling.
        static_metadata = WATSONX_LLM_METADATA if model_type == "llm" else WATSONX_EMBEDDING_METADATA
        known_by_name = {m["name"]: m for m in static_metadata}
        default_tool_calling = model_type == "llm"

        result: list[dict] = []
        for i, name in enumerate(model_names):
            known = known_by_name.get(name)
            result.append(
                create_model_metadata(
                    provider="IBM WatsonX",
                    name=name,
                    icon="IBM",
                    model_type=model_type if model_type == "llm" else "embeddings",
                    tool_calling=known.get("tool_calling", default_tool_calling) if known else default_tool_calling,
                    deprecated=bool(known.get("deprecated", False)) if known else False,
                    default=i < MIN_DEFAULT_MODELS,  # Mark first 5 as default
                )
            )
    except Exception:  # noqa: BLE001
        logger.debug(f"Could not fetch live WatsonX {model_type} models from {watsonx_url}")
        return []
    else:
        return result


def get_live_models_for_provider(
    user_id: UUID | str | None,
    provider: str,
    model_type: str = "llm",
) -> list[dict]:
    """Get live models for a provider if available.

    Args:
        user_id: The user ID to look up credentials
        provider: The provider name (e.g., "Ollama", "IBM WatsonX")
        model_type: "llm" or "embeddings"

    Returns:
        List of model metadata dicts, or empty list if live models not available
    """
    if provider == "Ollama":
        return fetch_live_ollama_models(user_id, model_type)
    if provider == "IBM WatsonX":
        return fetch_live_watsonx_models(user_id, model_type)
    if provider == "OpenRouter":
        return fetch_live_openrouter_models(user_id, model_type)
    return []


def _live_models_to_catalog_shape(live_models: list[dict]) -> list[dict]:
    """Convert raw live model dicts to the unified catalog shape."""
    return [
        {
            "model_name": m.get("name"),
            "metadata": {k: v for k, v in m.items() if k not in ("provider", "name")},
        }
        for m in live_models
    ]


def replace_with_live_models(
    provider_models: list[dict],
    user_id: UUID | str | None,
    enabled_providers: set[str] | list[str],
    model_type: str | None = None,
    provider_metadata: dict | None = None,
) -> list[dict]:
    """Replace static model entries with live models for providers in LIVE_MODEL_PROVIDERS.

    Iterates over LIVE_MODEL_PROVIDERS; for each that is in *enabled_providers*,
    fetches live models via get_live_models_for_provider and replaces (or appends)
    the provider entry in *provider_models*.

    Args:
        provider_models: List of provider dicts (same shape as get_unified_models_detailed output).
        user_id: Current user ID for credential lookup.
        enabled_providers: Set/list of provider names that are currently enabled/configured.
        model_type: ``"llm"``, ``"embeddings"``, or ``None`` (fetch both and concatenate).
        provider_metadata: Optional dict of extra provider metadata to merge into the entry.

    Returns:
        The (possibly modified) provider_models list.
    """
    if not user_id or not enabled_providers:
        return provider_models

    for provider in LIVE_MODEL_PROVIDERS:
        if provider not in enabled_providers:
            continue

        if model_type is None:
            live_llm = get_live_models_for_provider(user_id, provider, "llm")
            live_emb = get_live_models_for_provider(user_id, provider, "embeddings")
            live_models = live_llm + live_emb
        else:
            live_models = get_live_models_for_provider(user_id, provider, model_type)

        catalog_models = _live_models_to_catalog_shape(live_models) if live_models else []

        # Try to find and replace existing provider entry
        replaced = False
        for provider_dict in provider_models:
            if provider_dict.get("provider") == provider:
                provider_dict["models"] = catalog_models
                provider_dict["num_models"] = len(catalog_models)
                replaced = True
                break

        if not replaced and catalog_models:
            entry: dict = {
                "provider": provider,
                "models": catalog_models,
                "num_models": len(catalog_models),
            }
            if provider_metadata and provider in provider_metadata:
                entry.update(provider_metadata[provider])
            provider_models.append(entry)

    return provider_models
