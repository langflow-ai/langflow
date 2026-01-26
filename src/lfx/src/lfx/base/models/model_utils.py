import asyncio
from urllib.parse import urljoin

import httpx
import requests

from lfx.base.models.watsonx_constants import (
    WATSONX_DEFAULT_EMBEDDING_MODELS as WATSONX_EMBEDDING_METADATA,
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
