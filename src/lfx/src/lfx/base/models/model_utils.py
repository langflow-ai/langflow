import asyncio
import hashlib
import re
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
from uuid import UUID

import httpx
import requests
from cachetools import TTLCache

from lfx.base.models.model_metadata import (
    CONDITIONAL_LIVE_MODEL_PROVIDERS,
    EXPLICIT_ENABLE_ONLY_PROVIDERS,
    LIVE_MODEL_PROVIDERS,
    create_model_metadata,
)
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
from lfx.utils.ssrf_httpx import ssrf_safe_httpx_get
from lfx.utils.ssrf_protection import SSRFProtectionError, validate_connector_url_for_ssrf
from lfx.utils.util import transform_localhost_url

HTTP_STATUS_OK = 200
HTTP_STATUS_MULTIPLE_CHOICES = 300
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_FORBIDDEN = 403
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

# Per-model capability cache, keyed by (base_url, model_name). A given
# Ollama ``model:tag``'s capabilities (completion / embedding / tools / …)
# are intrinsic to the model, so this lives longer than the model-*list*
# cache above. It exists to kill the ``/api/show`` fan-out that made Ollama
# Cloud's large public catalog crawl on every model toggle (issue #12399):
# without it each catalog read cost ``N + 1`` upstream calls (one
# ``/api/tags`` + one ``/api/show`` per model) and ``/enabled_models`` paid
# that twice (llm + embeddings) on every refetch. With it:
#   (1) the llm and embedding reads (``model_type=None``) share a single
#       probe set instead of each fanning out over the whole catalog, and
#   (2) a read after the short list-TTL expires re-probes only models we
#       have never seen, not the full catalog.
# TTL is bounded (not indefinite) because the key omits the model digest:
# re-pulling the same tag to a different capability class (e.g. a
# completion model swapped for an embedding one under ``:latest``) would
# otherwise mis-route the model in the picker until expiry. 10 minutes
# fully covers a toggle session — the #12399 symptom — while keeping any
# post-re-pull staleness short and self-healing.
_OLLAMA_CAPABILITY_TTL_SECONDS = 600.0
_ollama_capability_cache: dict[tuple[str, str], tuple[float, list[str]]] = {}


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


def _ollama_capability_get(key: tuple[str, str], *, now: float | None = None) -> list[str] | None:
    """Return the cached capability list for *key* if still fresh; else None.

    ``None`` means a genuine miss or expiry. Callers never store an empty
    list (see ``_capabilities_for``), so a fresh hit is always a populated
    capability list.
    """
    entry = _ollama_capability_cache.get(key)
    if entry is None:
        return None
    timestamp, value = entry
    current = now if now is not None else time.monotonic()
    if (current - timestamp) >= _OLLAMA_CAPABILITY_TTL_SECONDS:
        return None
    return list(value)


def _ollama_capability_set(key: tuple[str, str], value: list[str], *, now: float | None = None) -> None:
    current = now if now is not None else time.monotonic()
    _ollama_capability_cache[key] = (current, list(value))


def _ollama_capability_prune(base_url: str, keep: set[str]) -> None:
    """Drop capability entries for *base_url* whose model left the catalog.

    The capability cache expires on read but is otherwise never evicted, so
    without this it would retain one entry per distinct model ever seen for
    the process lifetime — relevant for Ollama Cloud's large, evolving public
    catalog. Pruning on each fresh catalog read bounds it to the live catalog
    instead. Entries for other base URLs are left untouched.
    """
    stale = [key for key in _ollama_capability_cache if key[0] == base_url and key[1] not in keep]
    for key in stale:
        del _ollama_capability_cache[key]


def _ollama_cache_clear() -> None:
    """Drop every cached entry. Exposed for tests; not called in production."""
    _ollama_model_list_cache.clear()
    _ollama_capability_cache.clear()


# Extract model names from metadata for fallback defaults. Deprecated seed
# entries are withdrawn from IBM's catalog, so the API-failure fallback must
# not offer them.
WATSONX_DEFAULT_LLM_MODEL_NAMES = [m["name"] for m in WATSONX_LLM_METADATA if not m.get("deprecated")]
WATSONX_DEFAULT_EMBEDDING_MODEL_NAMES = [m["name"] for m in WATSONX_EMBEDDING_METADATA if not m.get("deprecated")]


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
        tags_url = urljoin(url, "api/tags")
        # base_url is tenant-controlled and this runs during build-config edits: block SSRF
        # to internal/cloud-metadata hosts before issuing the request.
        validate_connector_url_for_ssrf(tags_url)
        async with httpx.AsyncClient() as client:
            return (await client.get(url=tags_url)).status_code == HTTP_STATUS_OK
    except SSRFProtectionError:
        logger.warning("Ollama URL blocked by SSRF protection: %s", url)
        return False
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

        # base_url is tenant-controlled: block SSRF to internal/cloud-metadata hosts. The
        # host is shared by both endpoints, so validating one covers the POST to show_url too.
        validate_connector_url_for_ssrf(tags_url)

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

            # Keep the capability cache aligned with the live catalog so it
            # can't accumulate entries for models that have dropped out.
            _ollama_capability_prune(base_url_value, set(candidates))

            async def _capabilities_for(model_name: str) -> list[str] | None:
                """Return one model's capability list, reusing the per-model cache.

                A cache hit skips the ``/api/show`` round-trip entirely — this
                is what stops the catalog read from fanning out over the whole
                catalog on every refetch. Two responses are deliberately left
                *uncached* and retried on the next read:

                  * a probe failure (``RequestError``/``HTTPStatusError``), so
                    one bad model never poisons or sticks in the catalog; and
                  * a 200 carrying no capabilities, so a transient empty
                    response (e.g. a model still warming up on Ollama Cloud)
                    can't hide a model from the picker for the full TTL. Real
                    Ollama always returns a populated array, so this never
                    re-probes a legitimately-capable model.
                """
                cap_key = (base_url_value, model_name)
                cached_caps = _ollama_capability_get(cap_key)
                if cached_caps is not None:
                    return cached_caps
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
                # Only cache a populated list; an empty one carries no signal
                # (it can never match a desired_capability) and may be
                # transient, so leave it uncached like the failure path above.
                if capabilities:
                    _ollama_capability_set(cap_key, capabilities)
                return capabilities

            # Parallel fan-out: one POST /api/show per *uncached* candidate,
            # awaited together so latency is bounded by the slowest single
            # request instead of N * avg-request-latency. Cached candidates
            # resolve without any upstream call.
            results = await asyncio.gather(*(_capabilities_for(n) for n in candidates))
            model_ids = sorted(
                name
                for name, capabilities in zip(candidates, results, strict=True)
                if capabilities is not None and desired_capability in capabilities
            )

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
        # base_url is tenant-controlled: block SSRF to internal/cloud-metadata hosts (the
        # except below returns default models if blocked). allow_redirects=False per OWASP.
        validate_connector_url_for_ssrf(endpoint)
        response = requests.get(endpoint, params=params, timeout=10, allow_redirects=False)
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
        # base_url is tenant-controlled: block SSRF to internal/cloud-metadata hosts (the
        # except below returns default models if blocked). allow_redirects=False per OWASP.
        validate_connector_url_for_ssrf(endpoint)
        response = requests.get(endpoint, params=params, timeout=10, allow_redirects=False)
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


OPENAI_COMPATIBLE_FETCH_TIMEOUT = 10.0

AZURE_AI_FOUNDRY_FETCH_TIMEOUT = 10.0
# Shared wall-clock bound for Foundry HTTP (discovery) and SDK (validate/get_llm).
AZURE_AI_FOUNDRY_REQUEST_TIMEOUT = AZURE_AI_FOUNDRY_FETCH_TIMEOUT


# Default api-version for the /models credential-validation probe. Per Microsoft's
# Azure AI Model Inference REST API reference, which uses this value in every example:
# https://learn.microsoft.com/en-us/rest/api/aifoundry/modelinference/
# Overridable per user via the AZURE_AI_FOUNDRY_API_VERSION variable.
AZURE_AI_FOUNDRY_MODELS_PROBE_API_VERSION = "2025-04-01"
_AZURE_AI_FOUNDRY_OPENAI_MODELS_API_VERSIONS = frozenset({"v1", "preview"})


def normalize_azure_ai_foundry_endpoint(endpoint: str) -> str:
    """Map a pasted Foundry *project* endpoint to the OpenAI-compatible endpoint.

    The Foundry portal most prominently shows the project endpoint
    (``https://<resource>.services.ai.azure.com/api/projects/<project>``), but this
    provider needs the OpenAI-compatible form
    (``https://<resource>.services.ai.azure.com/openai/v1``) — the project form
    returns HTTP 400 on ``/models``. Rewrite the former to the latter; every other
    endpoint passes through unchanged.
    """
    parsed = urlparse(endpoint)
    path = parsed.path.lower()
    if not parsed.netloc or not (path.startswith("/api/projects/") or path.rstrip("/") == "/api/projects"):
        return endpoint
    normalized = f"{parsed.scheme}://{parsed.netloc}/openai/v1"
    # Log neither URL: a pasted endpoint can carry user-info or query credentials.
    logger.info(
        "AZURE_AI_FOUNDRY_ENDPOINT looks like a Foundry project endpoint; "
        "replacing '/api/projects/...' with '/openai/v1' (the OpenAI-compatible form). "
        "Update the saved endpoint to silence this message."
    )
    return normalized


def _azure_ai_foundry_models_probe_url(endpoint: str, api_version: str | None = None) -> str:
    """Build the Foundry ``/models`` probe URL from any configured endpoint form.

    Foundry hands out several endpoint shapes (OpenAI-compatible ``…/openai/v1``,
    generic inference ``…/models``, project ``…/api/projects/<name>``), so this
    merges the ``/models`` segment with proper URL parsing — deduping when the
    endpoint already ends in one — instead of naive string concatenation.

    Generic Model Inference routes receive the configured dated API version (or
    the probe default). The OpenAI v1 route is already path-versioned and accepts
    only ``v1`` or ``preview`` query values, so dated versions are omitted there.
    """
    parsed = urlparse(endpoint.strip())
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments or segments[-1] != "models":
        segments = [*segments, "models"]
    new_path = "/" + "/".join(segments)
    query = parse_qs(parsed.query, keep_blank_values=True)
    existing_versions = [value for value in query.get("api-version", []) if value]
    is_openai_v1 = [segment.lower() for segment in segments[-3:]] == ["openai", "v1", "models"]
    if is_openai_v1:
        compatible_versions = [
            value for value in existing_versions if value in _AZURE_AI_FOUNDRY_OPENAI_MODELS_API_VERSIONS
        ]
        if compatible_versions:
            query["api-version"] = compatible_versions
        elif api_version in _AZURE_AI_FOUNDRY_OPENAI_MODELS_API_VERSIONS:
            query["api-version"] = [api_version]
        else:
            query.pop("api-version", None)
    elif not existing_versions:
        query["api-version"] = [api_version or AZURE_AI_FOUNDRY_MODELS_PROBE_API_VERSION]
    else:
        query["api-version"] = existing_versions
    return urlunparse((parsed.scheme, parsed.netloc, new_path, parsed.params, urlencode(query, doseq=True), ""))


def request_azure_ai_foundry_model_entries(endpoint: str, api_key: str, api_version: str | None = None) -> list[dict]:
    """Probe Foundry /models for credential validation (catalog, not deployments).

    Pasted project endpoints are first normalized to the OpenAI-compatible form
    (``normalize_azure_ai_foundry_endpoint``). Only 401/403 — genuinely bad
    credentials — raise. Azure has no reliable catalog route across Foundry
    resource shapes (project-scoped endpoints can return 400 BadRequest with
    valid credentials and a correct api-version), so any other non-2xx response
    or unexpected payload degrades to an empty catalog instead of blocking the
    credential save. Connection errors and timeouts still propagate: an
    unreachable endpoint is a real misconfiguration the save should surface.
    """
    endpoint = normalize_azure_ai_foundry_endpoint(endpoint)
    probe_url = _azure_ai_foundry_models_probe_url(endpoint, api_version)
    response = ssrf_safe_httpx_get(
        probe_url,
        headers={"api-key": api_key},
        timeout=AZURE_AI_FOUNDRY_FETCH_TIMEOUT,
    )
    if response.status_code in (HTTP_STATUS_UNAUTHORIZED, HTTP_STATUS_FORBIDDEN):
        response.raise_for_status()
    if not HTTP_STATUS_OK <= response.status_code < HTTP_STATUS_MULTIPLE_CHOICES:
        logger.debug(f"Azure AI Foundry /models probe returned {response.status_code}; treating catalog as empty")
        return []
    try:
        payload = response.json()
    except ValueError:
        return []
    raw_models = payload.get("data") if isinstance(payload, dict) else None
    return raw_models if isinstance(raw_models, list) else []


def fetch_live_openai_compatible_models(user_id: UUID | str | None, model_type: str = "llm") -> list[dict]:
    """Fetch models from a custom OpenAI-compatible endpoint (OPENAI_BASE_URL).

    Returns [] when no custom base URL is configured, so api.openai.com
    users keep the curated static catalog. Because ``/models`` carries no
    capability data, the endpoint's models are offered in whichever picker
    requested them. ``tool_calling`` is assumed only for language models.
    """
    if model_type not in {"llm", "embeddings"}:
        return []

    base_url = get_provider_variable_value(user_id, "OPENAI_BASE_URL")
    if not base_url:
        return []
    base_url = transform_localhost_url(base_url)

    api_key = get_provider_variable_value(user_id, "OPENAI_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        response = ssrf_safe_httpx_get(
            f"{base_url.rstrip('/')}/models",
            headers=headers,
            timeout=OPENAI_COMPATIBLE_FETCH_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
        logger.debug(f"Could not fetch live OpenAI-compatible models from {base_url}: {exc}")
        return []

    # An arbitrary OpenAI-compatible server may return a non-conforming body
    # (a bare list, a list of strings, …); treat anything off-spec as "no models".
    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []

    return [
        create_model_metadata(
            provider="OpenAI",
            name=entry["id"],
            icon="OpenAI",
            model_type=model_type,
            tool_calling=model_type == "llm",
            default=index < MIN_DEFAULT_MODELS,
        )
        for index, entry in enumerate(entries)
        if isinstance(entry, dict) and entry.get("id")
    ]


# Default api-version for the resource-level deployments listing, overridable per user
# via the AZURE_AI_FOUNDRY_API_VERSION variable (see _azure_ai_foundry_api_version).
# The route is data-plane; Microsoft docs steer new integrations to the ARM management
# plane (which needs Entra auth plus subscription/resource-group context this provider
# doesn't collect), but this api-version still answers with data[].{id,model,status} —
# verified live against a real Foundry resource (2026-08-11). If Azure ever retires it,
# the fetch degrades to the static seed catalog like every other failure mode here.
AZURE_AI_FOUNDRY_DEPLOYMENTS_API_VERSION = "2023-03-15-preview"

# api-version values are URL query components; anything outside this shape is ignored
# in favor of the default so a variable value can't smuggle extra query parameters.
_AZURE_AI_FOUNDRY_API_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]*")


def _azure_ai_foundry_api_version(user_id: UUID | str | None) -> str:
    """Deployments-listing api-version: the user's AZURE_AI_FOUNDRY_API_VERSION, else the default."""
    configured = get_provider_variable_value(user_id, "AZURE_AI_FOUNDRY_API_VERSION")
    configured = configured.strip() if configured else ""
    if not configured:
        return AZURE_AI_FOUNDRY_DEPLOYMENTS_API_VERSION
    if not _AZURE_AI_FOUNDRY_API_VERSION_PATTERN.fullmatch(configured):
        logger.warning(
            f"Ignoring invalid AZURE_AI_FOUNDRY_API_VERSION; using {AZURE_AI_FOUNDRY_DEPLOYMENTS_API_VERSION}"
        )
        return AZURE_AI_FOUNDRY_DEPLOYMENTS_API_VERSION
    return configured


# Live discovery sends the api-key header to the derived URL, so destinations are pinned
# to Azure AI Foundry / Azure OpenAI hosts (public, US Government, and China clouds): a
# rewritten endpoint variable must not be able to redirect the key to an arbitrary
# collector. Custom gateway domains (e.g. APIM fronting) simply keep the static seed
# catalog + free-text enables.
_AZURE_AI_FOUNDRY_HOST_SUFFIXES = (
    ".services.ai.azure.com",
    ".openai.azure.com",
    ".cognitiveservices.azure.com",
    ".services.ai.azure.us",
    ".openai.azure.us",
    ".cognitiveservices.azure.us",
    ".services.ai.azure.cn",
    ".openai.azure.cn",
    ".cognitiveservices.azure.cn",
)

# Reasoning-capable families, matched against the deployment's underlying model id:
# the o-series (o1 / o3-mini / o4-mini / …) and gpt-5 family prefixes, plus
# DeepSeek-R1 variants and explicitly reasoning-suffixed models (e.g.
# Phi-4-reasoning) anywhere in the id.
_AZURE_AI_FOUNDRY_REASONING_PATTERN = re.compile(r"^o\d|^gpt-5|deepseek-r1|reasoning")

# Chat families Microsoft's Foundry capability table documents WITHOUT tool calling
# (e.g. DeepSeek-R1, the Phi family, Codestral): they stay in the LLM picker but must
# not surface in tool-filtered (Agent) pickers. Unknown models keep tool_calling=True
# — matching free-text enables and the other live providers — so new tool-capable
# catalog additions aren't silently banned from Agents.
_AZURE_AI_FOUNDRY_NO_TOOL_CHAT_MODEL_MARKERS = (
    "deepseek-r1",
    "phi-",
    "codestral",
)

# Deployments the unified chat/embedding classes cannot drive: image, audio, and video
# models plus the legacy completions-only families (chat_completion=false in Azure's
# /models capability metadata — e.g. curie). Matched as substrings of the underlying
# model id AFTER the embeddings check, so text-embedding-ada-002 classifies as
# embeddings before "ada" reads as legacy. Deliberately no bare "instruct" marker:
# Foundry-hosted open chat models are routinely named *-Instruct (Llama, Phi, Mistral).
_AZURE_AI_FOUNDRY_NON_CHAT_MODEL_MARKERS = (
    "dall-e",
    "dalle",
    "gpt-image",
    "whisper",
    "tts",
    "sora",
    "babbage",
    "curie",
    "cushman",
    "davinci",
    "ada",
    "gpt-35-turbo-instruct",
    "gpt-3.5-turbo-instruct",
)

# The llm and embeddings picker reads land back-to-back on the same resource, so raw
# deployment entries are memoized briefly: one upstream round-trip per pair — and one
# timeout, not two sequential ones, when the resource is unreachable (failures cache
# as None for the same TTL). TTLCache evicts expired and overflow entries (a plain
# dict would retain every key ever seen for the process lifetime), and the key
# carries a SHA-256 fingerprint of the credential — the plaintext api-key must never
# be retained in the cache.
_AZURE_AI_FOUNDRY_DEPLOYMENTS_TTL_SECONDS = 30.0
_AZURE_AI_FOUNDRY_DEPLOYMENTS_CACHE_MAXSIZE = 128
_azure_ai_foundry_deployments_cache: TTLCache = TTLCache(
    maxsize=_AZURE_AI_FOUNDRY_DEPLOYMENTS_CACHE_MAXSIZE,
    ttl=_AZURE_AI_FOUNDRY_DEPLOYMENTS_TTL_SECONDS,
)


def _azure_ai_foundry_cache_key(deployments_url: str, api_key: str) -> tuple[str, str]:
    """Cache identity without credential retention: URL plus a non-reversible key fingerprint."""
    return (deployments_url, hashlib.sha256(api_key.encode()).hexdigest())


def _fetch_azure_ai_foundry_deployment_entries(deployments_url: str, api_key: str) -> list[dict] | None:
    """Return the raw deployment entries (briefly memoized), or None when the listing failed."""
    key = _azure_ai_foundry_cache_key(deployments_url, api_key)
    try:
        cached = _azure_ai_foundry_deployments_cache[key]
    except KeyError:
        pass
    else:
        return list(cached) if cached is not None else None

    entries: list[dict] | None
    try:
        response = ssrf_safe_httpx_get(
            deployments_url,
            headers={"api-key": api_key},
            timeout=AZURE_AI_FOUNDRY_FETCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (SSRFProtectionError, httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
        logger.debug(f"Could not fetch live Azure AI Foundry deployments from {deployments_url}: {exc}")
        entries = None
    else:
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, list):
            entries = data
        else:
            logger.debug(
                f"Unexpected Azure AI Foundry deployments payload from {deployments_url}; keeping static catalog"
            )
            entries = None

    _azure_ai_foundry_deployments_cache[key] = entries
    return list(entries) if entries is not None else None


def _azure_ai_foundry_deployments_url(endpoint: str, api_version: str) -> str | None:
    """Derive the resource-level deployments listing URL from the configured endpoint.

    ``AZURE_AI_FOUNDRY_ENDPOINT`` may hold any endpoint form the Foundry portal
    hands out — the OpenAI-compatible endpoint
    (``https://<resource>.services.ai.azure.com/openai/v1``), the generic Azure AI
    inference endpoint (``…/models``), or a pasted *project* endpoint
    (``…/api/projects/<name>``). Only the host matters here: the deployments
    listing hangs off the resource base as
    ``{resource}/openai/deployments?api-version=…``, where ``/openai/`` is the
    resource data-plane's route prefix (legacy Azure OpenAI naming), not a filter
    to OpenAI-family models — the listing covers the resource's deployments.
    Returns ``None`` — and the caller keeps the static catalog — unless the
    endpoint is a plain HTTPS URL (no userinfo, no explicit port) on a known
    Azure Foundry host (``_AZURE_AI_FOUNDRY_HOST_SUFFIXES``).
    """
    parsed = urlparse(endpoint)
    try:
        port = parsed.port
    except ValueError:
        return None
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or not hostname.endswith(_AZURE_AI_FOUNDRY_HOST_SUFFIXES)
    ):
        return None
    return f"https://{hostname}/openai/deployments?api-version={api_version}"


def fetch_live_azure_ai_foundry_models(user_id: UUID | str | None, model_type: str = "llm") -> list[dict]:
    """List the Foundry resource's actual deployments for the model picker.

    Foundry ``/models`` is Azure's full model *catalog* (deprecated models
    included), not this resource's deployments — never use it here; it is only
    probed for credential validation (``request_azure_ai_foundry_model_entries``).
    The real deployments come from the resource-level listing
    ``GET {resource}/openai/deployments?api-version=…`` with the same ``api-key``
    header (SSRF-validated and DNS-pinned via ``ssrf_safe_httpx_get``, memoized
    briefly so the llm and embeddings picker reads share one round-trip). Only
    ``status == "succeeded"`` deployments are offered, named by deployment id
    (what inference accepts) and classified llm/embeddings from the underlying
    ``model`` field; image/audio/legacy-completions deployments the unified chat
    class cannot drive are excluded. Returns ``[]`` on any failure — missing
    endpoint/key, endpoint not on a pinned Azure Foundry host, blocked host,
    HTTP error, malformed payload — so the static seed catalog remains the
    fallback.
    """
    if model_type not in {"llm", "embeddings"}:
        return []

    endpoint = get_provider_variable_value(user_id, "AZURE_AI_FOUNDRY_ENDPOINT")
    api_key = get_provider_variable_value(user_id, "AZURE_AI_FOUNDRY_API_KEY")
    if not endpoint or not api_key:
        return []

    deployments_url = _azure_ai_foundry_deployments_url(endpoint, _azure_ai_foundry_api_version(user_id))
    if deployments_url is None:
        # Reason only, never the raw endpoint: it may embed userinfo or query tokens.
        logger.debug(
            "AZURE_AI_FOUNDRY_ENDPOINT is not a plain HTTPS URL on a known Azure Foundry host; skipping live discovery"
        )
        return []

    entries = _fetch_azure_ai_foundry_deployment_entries(deployments_url, api_key)
    if entries is None:
        return []

    models: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        deployment_id = entry.get("id")
        if not isinstance(deployment_id, str) or not deployment_id:
            continue
        if str(entry.get("status", "")).lower() != "succeeded":
            continue
        underlying_model = entry.get("model")
        if not isinstance(underlying_model, str) or not underlying_model:
            underlying_model = deployment_id
        lowered = underlying_model.lower()
        if "embed" in lowered:
            entry_type = "embeddings"
        elif any(marker in lowered for marker in _AZURE_AI_FOUNDRY_NON_CHAT_MODEL_MARKERS):
            continue
        else:
            entry_type = "llm"
        if entry_type != model_type:
            continue
        supports_tools = model_type == "llm" and not any(
            marker in lowered for marker in _AZURE_AI_FOUNDRY_NO_TOOL_CHAT_MODEL_MARKERS
        )
        models.append(
            create_model_metadata(
                provider="Azure AI Foundry",
                name=deployment_id,
                icon="Azure",
                model_type=model_type,
                tool_calling=supports_tools,
                reasoning=bool(_AZURE_AI_FOUNDRY_REASONING_PATTERN.search(lowered)),
                # Foundry is explicit-enable-only: live rows must never auto-enable.
                default=False,
            )
        )
    return models


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
        # ibm/granite-guardian-3-8b in the Agent dropdown even though they
        # don't support tool calling. ``deprecated`` is intentionally NOT
        # copied from the static seed: the live query already excludes
        # withdrawn models (``!lifecycle_withdrawn``), and re-stamping the
        # static flag once hid live, current models whenever the seed data
        # went stale (the "IBM WatsonX shows 0 models" bug).
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
    if provider == "OpenAI":
        return fetch_live_openai_compatible_models(user_id, model_type)
    if provider == "Azure AI Foundry":
        return fetch_live_azure_ai_foundry_models(user_id, model_type)

    # Providers contributed by extension bundles supply their own live-discovery
    # callable via provider_registry (imported lazily to avoid an import cycle).
    from lfx.base.models.provider_registry import live_discovery_for

    discovery = live_discovery_for(provider)
    if discovery is not None:
        try:
            models = discovery(user_id, model_type)
        except Exception:  # noqa: BLE001
            logger.debug(f"Live discovery failed for bundle provider {provider!r}; returning no live models")
            return []
        if isinstance(models, list):
            return models
        logger.warning(f"Live discovery for bundle provider {provider!r} returned a non-list result; ignoring")
        return []
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


def apply_metadata_filters(
    provider_models: list[dict],
    metadata_filters: dict | None,
) -> dict[str, set[tuple[str, str]]]:
    """Drop models whose metadata fails *metadata_filters*; return what was dropped.

    ``get_unified_models_detailed`` applies metadata filters to the static catalog
    only, and ``replace_with_live_models`` then swaps in live rows wholesale — so
    tool-filtered pickers (e.g. the Agent picker's ``tool_calling=True``) must
    re-filter after live replacement or live models bypass the filter entirely.
    The returned ``provider -> {(name, model_type)}`` map records the dropped rows
    so ``inject_custom_enabled_models`` does not resurrect an explicitly enabled
    deployment the live catalog just filtered out (its synthetic free-text
    metadata would otherwise pass the filter).
    """
    suppressed: dict[str, set[tuple[str, str]]] = {}
    if not metadata_filters:
        return suppressed
    for provider_dict in provider_models:
        provider = provider_dict.get("provider")
        models = provider_dict.get("models", [])
        kept: list[dict] = []
        for model in models:
            metadata = model.get("metadata") or {}
            if any(metadata.get(k) != v for k, v in metadata_filters.items()):
                if isinstance(provider, str) and isinstance(model.get("model_name"), str):
                    suppressed.setdefault(provider, set()).add(
                        (model["model_name"], metadata.get("model_type") or "llm")
                    )
                continue
            kept.append(model)
        if len(kept) != len(models):
            provider_dict["models"] = kept
            provider_dict["num_models"] = len(kept)
    return suppressed


def inject_custom_enabled_models(
    provider_models: list[dict],
    explicitly_enabled_models: set[str],
    *,
    model_name: str | None = None,
    model_type: str | None = None,
    metadata_filters: dict | None = None,
    suppressed: dict[str, set[tuple[str, str]]] | None = None,
) -> None:
    """Append free-text enabled deployments missing from the catalog (e.g. Foundry)."""
    if not explicitly_enabled_models:
        return

    # Lazy imports: provider_queries pulls model constants that import model_utils.
    from lfx.base.models.unified_models.credentials import parse_model_status_key
    from lfx.base.models.unified_models.provider_queries import get_model_provider_metadata

    provider_meta = get_model_provider_metadata()
    # Track (name, model_type) so llm and embeddings rows do not collide.
    known_by_provider: dict[str, set[tuple[str, str]]] = {}
    provider_dicts: dict[str, dict] = {}
    for provider_dict in provider_models:
        provider = provider_dict.get("provider")
        if not isinstance(provider, str):
            continue
        provider_dicts[provider] = provider_dict
        known_by_provider[provider] = {
            (
                model.get("model_name"),
                (model.get("metadata") or {}).get("model_type") or "llm",
            )
            for model in provider_dict.get("models", [])
            if isinstance(model.get("model_name"), str)
        }

    # Stable order across processes (set iteration is unordered).
    for entry in sorted(explicitly_enabled_models):
        provider, custom_name, persisted_type = parse_model_status_key(entry)
        if provider not in EXPLICIT_ENABLE_ONLY_PROVIDERS:
            continue
        custom_name = custom_name.strip()
        if not provider or not custom_name:
            continue
        resolved_type = persisted_type or "llm"
        if model_type is not None and resolved_type != model_type:
            continue
        if model_name is not None and custom_name != model_name:
            continue
        # The live catalog deliberately filtered this row out (see
        # apply_metadata_filters); a synthetic free-text row must not revive it.
        if suppressed and (custom_name, resolved_type) in suppressed.get(provider, set()):
            continue

        icon = provider_meta.get(provider, {}).get("icon", "Bot")
        metadata = {
            "icon": icon,
            "model_type": resolved_type,
            "tool_calling": resolved_type == "llm",
            "default": False,
        }
        if metadata_filters and any(metadata.get(k) != v for k, v in metadata_filters.items()):
            continue

        provider_dict = provider_dicts.get(provider)
        if provider_dict is None:
            # Stub provider when embeddings filter omits chat-only Foundry seed.
            meta = provider_meta.get(provider, {})
            provider_dict = {
                "provider": provider,
                "models": [],
                "num_models": 0,
                **meta,
            }
            provider_models.append(provider_dict)
            provider_dicts[provider] = provider_dict
            known_by_provider[provider] = set()

        known = known_by_provider.setdefault(provider, set())
        if (custom_name, resolved_type) in known:
            continue
        provider_dict.setdefault("models", []).append(
            {
                "model_name": custom_name,
                "metadata": metadata,
            }
        )
        provider_dict["num_models"] = len(provider_dict["models"])
        known.add((custom_name, resolved_type))


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

    for provider in (*LIVE_MODEL_PROVIDERS, *CONDITIONAL_LIVE_MODEL_PROVIDERS):
        if provider not in enabled_providers:
            continue

        if model_type is None:
            live_llm = get_live_models_for_provider(user_id, provider, "llm")
            live_emb = get_live_models_for_provider(user_id, provider, "embeddings")
            live_models = live_llm + live_emb
        else:
            live_models = get_live_models_for_provider(user_id, provider, model_type)

        if provider in CONDITIONAL_LIVE_MODEL_PROVIDERS and not live_models:
            continue

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
