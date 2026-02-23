import asyncio
from urllib.parse import urljoin
from uuid import UUID

import httpx
from lfx.base.models.model_metadata import create_model_metadata
from lfx.services.deps import get_variable_service, session_scope
from lfx.utils.async_helpers import run_until_complete
import requests

from lfx.base.models.watsonx_constants import (
    IBM_WATSONX_URLS,
    WATSONX_DEFAULT_EMBEDDING_MODELS as WATSONX_EMBEDDING_METADATA,
)
from lfx.base.models.watsonx_constants import (
    WATSONX_DEFAULT_LLM_MODELS as WATSONX_LLM_METADATA,
)
from lfx.log.logger import logger
from lfx.utils.util import transform_localhost_url

HTTP_STATUS_OK = 200

# Extract model names from metadata for fallback defaults
WATSONX_DEFAULT_LLM_MODEL_NAMES = [m["name"] for m in WATSONX_LLM_METADATA]
WATSONX_DEFAULT_EMBEDDING_MODEL_NAMES = [m["name"] for m in WATSONX_EMBEDDING_METADATA]


def get_model_name(llm, display_name: str | None = "Custom"):
    attributes_to_check = ["model_name", "model", "model_id", "deployment_name"]

    # Use a generator expression with next() to find the first matching attribute
    model_name = next((getattr(llm, attr) for attr in attributes_to_check if hasattr(llm, attr)), None)

    # If no matching attribute is found, return the class name as a fallback
    return model_name if model_name is not None else display_name


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
        tags_response = None

        async with httpx.AsyncClient() as client:
            # Fetch available models
            tags_response = await client.get(url=tags_url)
            tags_response.raise_for_status()
            models = tags_response.json()
            if asyncio.iscoroutine(models):
                models = await models
            await logger.adebug(f"Available models: {models}")

            # Filter models that are NOT embedding models
            model_ids = []
            for model in models.get(json_models_key, []):
                model_name = model.get(json_name_key)
                if not model_name:
                    continue
                await logger.adebug(f"Checking model: {model_name}")

                payload = {"model": model_name}
                show_response = await client.post(url=show_url, json=payload)
                show_response.raise_for_status()
                json_data = show_response.json()
                if asyncio.iscoroutine(json_data):
                    json_data = await json_data

                capabilities = json_data.get(json_capabilities_key, [])
                await logger.adebug(f"Model: {model_name}, Capabilities: {capabilities}")

                if desired_capability in capabilities:
                    model_ids.append(model_name)

            return sorted(model_ids)

    except (httpx.RequestError, ValueError) as e:
        msg = "Could not get model names from Ollama."
        await logger.aexception(msg)
        raise ValueError(msg) from e


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
        The variable value if found, None otherwise
    """
    if user_id is None or (isinstance(user_id, str) and user_id == "None"):
        return None

    async def _get_variable():
        async with session_scope() as session:
            variable_service = get_variable_service()
            if variable_service is None:
                return None
            return await variable_service.get_variable(
                user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                name=variable_key,
                field="",
                session=session,
            )

    return run_until_complete(_get_variable())


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
                default=i < 5,  # Mark first 5 as default
            )
            for i, name in enumerate(model_names)
        ]
    except Exception:  # noqa: BLE001
        logger.debug(f"Could not fetch live Ollama {model_type} models from {base_url}")
        return []


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

        # Convert to model metadata format
        return [
            create_model_metadata(
                provider="IBM WatsonX",
                name=name,
                icon="IBM",
                model_type=model_type if model_type == "llm" else "embeddings",
                tool_calling=model_type == "llm",
                default=i < 5,  # Mark first 5 as default
            )
            for i, name in enumerate(model_names)
        ]
    except Exception:  # noqa: BLE001
        logger.debug(f"Could not fetch live WatsonX {model_type} models from {watsonx_url}")
        return []


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
    return []

