from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Callable

import contextlib

from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS_DETAILED
from lfx.base.models.google_generative_ai_constants import (
    GOOGLE_GENERATIVE_AI_MODELS_DETAILED,
)
from lfx.base.models.ollama_constants import OLLAMA_EMBEDDING_MODELS_DETAILED, OLLAMA_MODELS_DETAILED
from lfx.base.models.openai_constants import OPENAI_EMBEDDING_MODELS_DETAILED, OPENAI_MODELS_DETAILED
from lfx.base.models.watsonx_constants import WATSONX_MODELS_DETAILED
from lfx.log.logger import logger
from lfx.services.deps import get_variable_service, session_scope
from lfx.utils.async_helpers import run_until_complete


@lru_cache(maxsize=1)
def get_model_classes():
    """Lazy load model classes to avoid importing optional dependencies at module level."""
    from langchain_anthropic import ChatAnthropic
    from langchain_ibm import ChatWatsonx
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI

    from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed

    return {
        "ChatOpenAI": ChatOpenAI,
        "ChatAnthropic": ChatAnthropic,
        "ChatGoogleGenerativeAIFixed": ChatGoogleGenerativeAIFixed,
        "ChatOllama": ChatOllama,
        "ChatWatsonx": ChatWatsonx,
    }


@lru_cache(maxsize=1)
def get_embedding_classes():
    """Lazy load embedding classes to avoid importing optional dependencies at module level."""
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_ibm import WatsonxEmbeddings
    from langchain_ollama import OllamaEmbeddings
    from langchain_openai import OpenAIEmbeddings

    return {
        "GoogleGenerativeAIEmbeddings": GoogleGenerativeAIEmbeddings,
        "OpenAIEmbeddings": OpenAIEmbeddings,
        "OllamaEmbeddings": OllamaEmbeddings,
        "WatsonxEmbeddings": WatsonxEmbeddings,
    }


@lru_cache(maxsize=1)
def get_model_provider_metadata():
    return {
        "OpenAI": {
            "icon": "OpenAI",
            "variable_name": "OPENAI_API_KEY",
        },
        "Anthropic": {
            "icon": "Anthropic",
            "variable_name": "ANTHROPIC_API_KEY",
        },
        "Google Generative AI": {
            "icon": "GoogleGenerativeAI",
            "variable_name": "GOOGLE_API_KEY",
        },
        "Ollama": {
            "icon": "Ollama",
            "variable_name": "OLLAMA_BASE_URL",  # Ollama is local but can have custom URL
        },
        "IBM WatsonX": {
            "icon": "WatsonxAI",
            "variable_name": "WATSONX_APIKEY",
        },
    }


model_provider_metadata = get_model_provider_metadata()


@lru_cache(maxsize=1)
def get_models_detailed():
    return [
        ANTHROPIC_MODELS_DETAILED,
        OPENAI_MODELS_DETAILED,
        OPENAI_EMBEDDING_MODELS_DETAILED,
        GOOGLE_GENERATIVE_AI_MODELS_DETAILED,
        OLLAMA_MODELS_DETAILED,
        OLLAMA_EMBEDDING_MODELS_DETAILED,
        WATSONX_MODELS_DETAILED,
    ]


MODELS_DETAILED = get_models_detailed()


@lru_cache(maxsize=1)
def get_model_provider_variable_mapping() -> dict[str, str]:
    return {provider: meta["variable_name"] for provider, meta in model_provider_metadata.items()}


def get_model_providers() -> list[str]:
    """Return a sorted list of unique provider names."""
    return sorted({md.get("provider", "Unknown") for group in MODELS_DETAILED for md in group})


def get_unified_models_detailed(
    providers: list[str] | None = None,
    model_name: str | None = None,
    model_type: str | None = None,
    *,
    include_unsupported: bool | None = None,
    include_deprecated: bool | None = None,
    only_defaults: bool = False,
    **metadata_filters,
):
    """Return a list of providers and their models, optionally filtered.

    Parameters
    ----------
    providers : list[str] | None
        If given, only models from these providers are returned.
    model_name : str | None
        If given, only the model with this exact name is returned.
    model_type : str | None
        Optional. Restrict to models whose metadata "model_type" matches this value.
    include_unsupported : bool
        When False (default) models whose metadata contains ``not_supported=True``
        are filtered out.
    include_deprecated : bool
        When False (default) models whose metadata contains ``deprecated=True``
        are filtered out.
    only_defaults : bool
        When True, only models marked as default are returned.
        The first 5 models from each provider (in list order) are automatically
        marked as default. Defaults to False to maintain backward compatibility.
    **metadata_filters
        Arbitrary key/value pairs to match against the model's metadata.
        Example: ``get_unified_models_detailed(size="4k", context_window=8192)``

    Notes:
    • Filtering is exact-match on the metadata values.
    • If you *do* want to see unsupported models set ``include_unsupported=True``.
    • If you *do* want to see deprecated models set ``include_deprecated=True``.
    """
    if include_unsupported is None:
        include_unsupported = False
    if include_deprecated is None:
        include_deprecated = False

    # Gather all models from imported *_MODELS_DETAILED lists
    all_models: list[dict] = []
    for models_detailed in MODELS_DETAILED:
        all_models.extend(models_detailed)

    # Apply filters
    filtered_models: list[dict] = []
    for md in all_models:
        # Skip models flagged as not_supported unless explicitly included
        if (not include_unsupported) and md.get("not_supported", False):
            continue

        # Skip models flagged as deprecated unless explicitly included
        if (not include_deprecated) and md.get("deprecated", False):
            continue

        if providers and md.get("provider") not in providers:
            continue
        if model_name and md.get("name") != model_name:
            continue
        if model_type and md.get("model_type") != model_type:
            continue
        # Match arbitrary metadata key/value pairs
        if any(md.get(k) != v for k, v in metadata_filters.items()):
            continue

        filtered_models.append(md)

    # Group by provider
    provider_map: dict[str, list[dict]] = {}
    for metadata in filtered_models:
        prov = metadata.get("provider", "Unknown")
        provider_map.setdefault(prov, []).append(
            {
                "model_name": metadata.get("name"),
                "metadata": {k: v for k, v in metadata.items() if k not in ("provider", "name")},
            }
        )

    # Mark the first 5 models in each provider as default (based on list order)
    # and optionally filter to only defaults
    default_model_count = 5  # Number of default models per provider

    for prov, models in provider_map.items():
        for i, model in enumerate(models):
            if i < default_model_count:
                model["metadata"]["default"] = True
            else:
                model["metadata"]["default"] = False

        # If only_defaults is True, filter to only default models
        if only_defaults:
            provider_map[prov] = [m for m in models if m["metadata"].get("default", False)]

    # Format as requested
    return [
        {
            "provider": prov,
            "models": models,
            "num_models": len(models),
            **model_provider_metadata.get(prov, {}),
        }
        for prov, models in provider_map.items()
    ]


def get_api_key_for_provider(user_id: UUID | str | None, provider: str, api_key: str | None = None) -> str | None:
    """Get API key from self.api_key or global variables.

    Args:
        user_id: The user ID to look up global variables for
        provider: The provider name (e.g., "OpenAI", "Anthropic")
        api_key: An optional API key provided directly

    Returns:
        The API key if found, None otherwise
    """
    # First check if user provided an API key directly
    if api_key:
        return api_key

    # If no user_id or user_id is the string "None", we can't look up global variables
    if user_id is None or (isinstance(user_id, str) and user_id == "None"):
        return None

    # Map provider to global variable name
    provider_variable_map = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Google Generative AI": "GOOGLE_API_KEY",
        "IBM WatsonX": "WATSONX_APIKEY",
    }

    variable_name = provider_variable_map.get(provider)
    if not variable_name:
        return None

    # Try to get from global variables
    async def _get_variable():
        async with session_scope() as session:
            variable_service = get_variable_service()
            if variable_service is None:
                return None
            return await variable_service.get_variable(
                user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                name=variable_name,
                field="",
                session=session,
            )

    return run_until_complete(_get_variable())


def validate_model_provider_key(variable_name: str, api_key: str) -> None:
    """Validate a model provider API key by making a minimal test call.

    Args:
        variable_name: The variable name (e.g., OPENAI_API_KEY)
        api_key: The API key to validate

    Raises:
        HTTPException: If the API key is invalid
    """
    # Map variable names to providers
    provider_map = {
        "OPENAI_API_KEY": "OpenAI",
        "ANTHROPIC_API_KEY": "Anthropic",
        "GOOGLE_API_KEY": "Google Generative AI",
        "WATSONX_APIKEY": "IBM WatsonX",
        "OLLAMA_BASE_URL": "Ollama",
    }

    provider = provider_map.get(variable_name)
    if not provider:
        return  # Not a model provider key we validate

    # Get the first available model for this provider
    try:
        models = get_unified_models_detailed(providers=[provider])
        if not models or not models[0].get("models"):
            return  # No models available, skip validation

        first_model = models[0]["models"][0]["model_name"]
    except Exception:  # noqa: BLE001
        return  # Can't get models, skip validation

    # Test the API key based on provider
    try:
        if provider == "OpenAI":
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(api_key=api_key, model_name=first_model, max_tokens=1)
            llm.invoke("test")
        elif provider == "Anthropic":
            from langchain_anthropic import ChatAnthropic

            llm = ChatAnthropic(anthropic_api_key=api_key, model=first_model, max_tokens=1)
            llm.invoke("test")
        elif provider == "Google Generative AI":
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(google_api_key=api_key, model=first_model, max_tokens=1)
            llm.invoke("test")
        elif provider == "IBM WatsonX":
            from langchain_ibm import ChatWatsonx

            default_url = "https://us-south.ml.cloud.ibm.com"
            llm = ChatWatsonx(
                apikey=api_key,
                url=default_url,
                model_id=first_model,
                project_id="dummy_project_for_validation",  # Dummy project_id for validation
                params={"max_new_tokens": 1},
            )
            llm.invoke("test")

        elif provider == "Ollama":
            # Ollama is local, just verify the URL is accessible
            import requests

            response = requests.get(f"{api_key}/api/tags", timeout=5)
            if response.status_code != requests.codes.ok:
                msg = "Invalid Ollama base URL"
                raise ValueError(msg)
    except ValueError:
        # Re-raise ValueError (validation failed)
        raise
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "authentication" in error_msg.lower() or "api key" in error_msg.lower():
            msg = f"Invalid API key for {provider}"
            raise ValueError(msg) from e
        # For other errors, we'll allow the key to be saved (might be network issues, etc.)
        return


def get_language_model_options(
    user_id: UUID | str | None = None, *, tool_calling: bool | None = None
) -> list[dict[str, Any]]:
    """Return a list of available language model providers with their configuration.

    This function uses get_unified_models_detailed() which respects the enabled/disabled
    status from the settings page and automatically filters out deprecated/unsupported models.

    Args:
        user_id: Optional user ID to filter by user-specific enabled/disabled models
        tool_calling: If True, only return models that support tool calling.
                     If False, only return models that don't support tool calling.
                     If None (default), return all models regardless of tool calling support.
    """
    # Get all LLM models (excluding embeddings, deprecated, and unsupported by default)
    # Apply tool_calling filter if specified
    if tool_calling is not None:
        all_models = get_unified_models_detailed(
            model_type="llm",
            include_deprecated=False,
            include_unsupported=False,
            tool_calling=tool_calling,
        )
    else:
        all_models = get_unified_models_detailed(
            model_type="llm",
            include_deprecated=False,
            include_unsupported=False,
        )

    # Get disabled and explicitly enabled models for this user if user_id is provided
    disabled_models = set()
    explicitly_enabled_models = set()
    if user_id:
        try:

            async def _get_model_status():
                async with session_scope() as session:
                    variable_service = get_variable_service()
                    if variable_service is None:
                        return set(), set()
                    from langflow.services.variable.service import DatabaseVariableService

                    if not isinstance(variable_service, DatabaseVariableService):
                        return set(), set()
                    all_vars = await variable_service.get_all(
                        user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                        session=session,
                    )
                    disabled = set()
                    enabled = set()
                    import json

                    for var in all_vars:
                        if var.name == "__disabled_models__" and var.value:
                            with contextlib.suppress(json.JSONDecodeError, TypeError):
                                disabled = set(json.loads(var.value))
                        elif var.name == "__enabled_models__" and var.value:
                            with contextlib.suppress(json.JSONDecodeError, TypeError):
                                enabled = set(json.loads(var.value))
                    return disabled, enabled

            disabled_models, explicitly_enabled_models = run_until_complete(_get_model_status())
        except Exception:  # noqa: BLE001, S110
            # If we can't get model status, continue without filtering
            pass

    # Get enabled providers (those with credentials configured)
    enabled_providers = set()
    if user_id:
        try:

            async def _get_enabled_providers():
                async with session_scope() as session:
                    variable_service = get_variable_service()
                    if variable_service is None:
                        return set()
                    from langflow.services.variable.constants import CREDENTIAL_TYPE
                    from langflow.services.variable.service import DatabaseVariableService

                    if not isinstance(variable_service, DatabaseVariableService):
                        return set()
                    all_vars = await variable_service.get_all(
                        user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                        session=session,
                    )
                    credential_names = {var.name for var in all_vars if var.type == CREDENTIAL_TYPE}
                    provider_variable_map = get_model_provider_variable_mapping()
                    return {
                        provider for provider, var_name in provider_variable_map.items() if var_name in credential_names
                    }

            enabled_providers = run_until_complete(_get_enabled_providers())
        except Exception:  # noqa: BLE001, S110
            # If we can't get enabled providers, show all
            pass

    options = []
    model_class_mapping = {
        "OpenAI": "ChatOpenAI",
        "Anthropic": "ChatAnthropic",
        "Google Generative AI": "ChatGoogleGenerativeAIFixed",
        "Ollama": "ChatOllama",
        "IBM WatsonX": "ChatWatsonx",
    }

    api_key_param_mapping = {
        "OpenAI": "api_key",
        "Anthropic": "api_key",
        "Google Generative AI": "google_api_key",
        "Ollama": "base_url",
        "IBM WatsonX": "apikey",
    }

    # Track which providers have models
    providers_with_models = set()

    for provider_data in all_models:
        provider = provider_data.get("provider")
        models = provider_data.get("models", [])
        icon = provider_data.get("icon", "Bot")

        # Check if provider is enabled
        is_provider_enabled = not user_id or not enabled_providers or provider in enabled_providers

        # Track this provider
        if is_provider_enabled:
            providers_with_models.add(provider)

        # Skip provider if user_id is provided and provider is not enabled
        if user_id and enabled_providers and provider not in enabled_providers:
            continue

        for model_data in models:
            model_name = model_data.get("model_name")
            metadata = model_data.get("metadata", {})
            is_default = metadata.get("default", False)

            # Determine if model should be shown:
            # - If not default and not explicitly enabled, skip it
            # - If in disabled list, skip it
            # - Otherwise, show it
            if not is_default and model_name not in explicitly_enabled_models:
                continue
            if model_name in disabled_models:
                continue

            # Build the option dict
            option = {
                "name": model_name,
                "icon": icon,
                "category": provider,
                "provider": provider,
                "metadata": {
                    "context_length": 128000,  # Default, can be overridden
                    "model_class": model_class_mapping.get(provider, "ChatOpenAI"),
                    "model_name_param": "model",
                    "api_key_param": api_key_param_mapping.get(provider, "api_key"),
                },
            }

            # Add reasoning models list for OpenAI
            if provider == "OpenAI" and metadata.get("reasoning"):
                if "reasoning_models" not in option["metadata"]:
                    option["metadata"]["reasoning_models"] = []
                option["metadata"]["reasoning_models"].append(model_name)

            # Add base_url_param for Ollama
            if provider == "Ollama":
                option["metadata"]["base_url_param"] = "base_url"

            # Add extra params for WatsonX
            if provider == "IBM WatsonX":
                option["metadata"]["model_name_param"] = "model_id"
                option["metadata"]["url_param"] = "url"
                option["metadata"]["project_id_param"] = "project_id"

            options.append(option)

    # Add disabled providers (providers that exist in metadata but have no enabled models)
    if user_id:
        for provider, metadata in model_provider_metadata.items():
            if provider not in providers_with_models:
                # This provider has no enabled models, add it as a disabled provider entry
                options.append(
                    {
                        "name": f"__enable_provider_{provider}__",
                        "icon": metadata.get("icon", "Bot"),
                        "category": provider,
                        "provider": provider,
                        "metadata": {
                            "is_disabled_provider": True,
                            "variable_name": metadata.get("variable_name"),
                        },
                    }
                )

    return options


def get_embedding_model_options(user_id: UUID | str | None = None) -> list[dict[str, Any]]:
    """Return a list of available embedding model providers with their configuration.

    This function uses get_unified_models_detailed() which respects the enabled/disabled
    status from the settings page and automatically filters out deprecated/unsupported models.

    Args:
        user_id: Optional user ID to filter by user-specific enabled/disabled models
    """
    # Get all embedding models (excluding deprecated and unsupported by default)
    all_models = get_unified_models_detailed(
        model_type="embeddings",
        include_deprecated=False,
        include_unsupported=False,
    )

    # Get disabled and explicitly enabled models for this user if user_id is provided
    disabled_models = set()
    explicitly_enabled_models = set()
    if user_id:
        try:

            async def _get_model_status():
                async with session_scope() as session:
                    variable_service = get_variable_service()
                    if variable_service is None:
                        return set(), set()
                    from langflow.services.variable.service import DatabaseVariableService

                    if not isinstance(variable_service, DatabaseVariableService):
                        return set(), set()
                    all_vars = await variable_service.get_all(
                        user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                        session=session,
                    )
                    disabled = set()
                    enabled = set()
                    import json

                    for var in all_vars:
                        if var.name == "__disabled_models__" and var.value:
                            with contextlib.suppress(json.JSONDecodeError, TypeError):
                                disabled = set(json.loads(var.value))
                        elif var.name == "__enabled_models__" and var.value:
                            with contextlib.suppress(json.JSONDecodeError, TypeError):
                                enabled = set(json.loads(var.value))
                    return disabled, enabled

            disabled_models, explicitly_enabled_models = run_until_complete(_get_model_status())
        except Exception:  # noqa: BLE001, S110
            # If we can't get model status, continue without filtering
            pass

    # Get enabled providers (those with credentials configured)
    enabled_providers = set()
    if user_id:
        try:

            async def _get_enabled_providers():
                async with session_scope() as session:
                    variable_service = get_variable_service()
                    if variable_service is None:
                        return set()
                    from langflow.services.variable.constants import CREDENTIAL_TYPE
                    from langflow.services.variable.service import DatabaseVariableService

                    if not isinstance(variable_service, DatabaseVariableService):
                        return set()
                    all_vars = await variable_service.get_all(
                        user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                        session=session,
                    )
                    credential_names = {var.name for var in all_vars if var.type == CREDENTIAL_TYPE}
                    provider_variable_map = get_model_provider_variable_mapping()
                    return {
                        provider for provider, var_name in provider_variable_map.items() if var_name in credential_names
                    }

            enabled_providers = run_until_complete(_get_enabled_providers())
        except Exception:  # noqa: BLE001, S110
            # If we can't get enabled providers, show all
            pass

    options = []
    embedding_class_mapping = {
        "OpenAI": "OpenAIEmbeddings",
        "Google Generative AI": "GoogleGenerativeAIEmbeddings",
        "Ollama": "OllamaEmbeddings",
        "IBM WatsonX": "WatsonxEmbeddings",
    }

    # Provider-specific param mappings
    param_mappings = {
        "OpenAI": {
            "model": "model",
            "api_key": "api_key",
            "api_base": "base_url",
            "dimensions": "dimensions",
            "chunk_size": "chunk_size",
            "request_timeout": "timeout",
            "max_retries": "max_retries",
            "show_progress_bar": "show_progress_bar",
            "model_kwargs": "model_kwargs",
        },
        "Google Generative AI": {
            "model": "model",
            "api_key": "google_api_key",
            "request_timeout": "request_options",
            "model_kwargs": "client_options",
        },
        "Ollama": {
            "model": "model",
            "base_url": "base_url",
            "num_ctx": "num_ctx",
            "request_timeout": "request_timeout",
            "model_kwargs": "model_kwargs",
        },
        "IBM WatsonX": {
            "model_id": "model_id",
            "url": "url",
            "api_key": "apikey",
            "project_id": "project_id",
            "space_id": "space_id",
            "request_timeout": "request_timeout",
        },
    }

    # Track which providers have models
    providers_with_models = set()

    for provider_data in all_models:
        provider = provider_data.get("provider")
        models = provider_data.get("models", [])
        icon = provider_data.get("icon", "Bot")

        # Check if provider is enabled
        is_provider_enabled = not user_id or not enabled_providers or provider in enabled_providers

        # Track this provider
        if is_provider_enabled:
            providers_with_models.add(provider)

        # Skip provider if user_id is provided and provider is not enabled
        if user_id and enabled_providers and provider not in enabled_providers:
            continue

        for model_data in models:
            model_name = model_data.get("model_name")
            metadata = model_data.get("metadata", {})
            is_default = metadata.get("default", False)

            # Determine if model should be shown:
            # - If not default and not explicitly enabled, skip it
            # - If in disabled list, skip it
            # - Otherwise, show it
            if not is_default and model_name not in explicitly_enabled_models:
                continue
            if model_name in disabled_models:
                continue

            # Build the option dict
            option = {
                "name": model_name,
                "icon": icon,
                "category": provider,
                "provider": provider,
                "metadata": {
                    "embedding_class": embedding_class_mapping.get(provider, "OpenAIEmbeddings"),
                    "param_mapping": param_mappings.get(provider, param_mappings["OpenAI"]),
                    "model_type": "embeddings",  # Mark as embedding model
                },
            }

            options.append(option)

    # Add disabled providers (providers that exist in metadata but have no enabled models)
    if user_id:
        for provider, metadata in model_provider_metadata.items():
            if provider not in providers_with_models and provider in embedding_class_mapping:
                # This provider has no enabled models and supports embeddings, add it as a disabled provider entry
                options.append(
                    {
                        "name": f"__enable_provider_{provider}__",
                        "icon": metadata.get("icon", "Bot"),
                        "category": provider,
                        "provider": provider,
                        "metadata": {
                            "is_disabled_provider": True,
                            "variable_name": metadata.get("variable_name"),
                        },
                    }
                )

    return options


def normalize_model_names_to_dicts(model_names: list[str] | str) -> list[dict[str, Any]]:
    """Convert simple model name(s) to list of dicts format.

    Args:
        model_names: A string or list of strings representing model names

    Returns:
        A list of dicts with full model metadata including runtime info

    Examples:
        >>> normalize_model_names_to_dicts('gpt-4o')
        [{'name': 'gpt-4o', 'provider': 'OpenAI', 'metadata': {'model_class': 'ChatOpenAI', ...}}]

        >>> normalize_model_names_to_dicts(['gpt-4o', 'claude-3'])
        [{'name': 'gpt-4o', ...}, {'name': 'claude-3', ...}]
    """
    # Convert single string to list
    if isinstance(model_names, str):
        model_names = [model_names]

    # Get all available models to look up metadata
    try:
        all_models = get_unified_models_detailed()
    except Exception:  # noqa: BLE001
        # If we can't get models, just create basic dicts
        return [{"name": name} for name in model_names]

    # Model class mapping for runtime metadata
    model_class_mapping = {
        "OpenAI": "ChatOpenAI",
        "Anthropic": "ChatAnthropic",
        "Google Generative AI": "ChatGoogleGenerativeAIFixed",
        "Ollama": "ChatOllama",
        "IBM WatsonX": "ChatWatsonx",
    }

    api_key_param_mapping = {
        "OpenAI": "api_key",
        "Anthropic": "api_key",
        "Google Generative AI": "google_api_key",
        "Ollama": "base_url",
        "IBM WatsonX": "apikey",
    }

    # Build a lookup map of model_name -> full model data with runtime metadata
    model_lookup = {}
    for provider_data in all_models:
        provider = provider_data.get("provider")
        icon = provider_data.get("icon", "Bot")
        for model_data in provider_data.get("models", []):
            model_name = model_data.get("model_name")
            base_metadata = model_data.get("metadata", {})

            # Build runtime metadata similar to get_language_model_options
            runtime_metadata = {
                "context_length": 128000,  # Default
                "model_class": model_class_mapping.get(provider, "ChatOpenAI"),
                "model_name_param": "model",
                "api_key_param": api_key_param_mapping.get(provider, "api_key"),
            }

            # Add reasoning models list for OpenAI
            if provider == "OpenAI" and base_metadata.get("reasoning"):
                runtime_metadata["reasoning_models"] = [model_name]

            # Add base_url_param for Ollama
            if provider == "Ollama":
                runtime_metadata["base_url_param"] = "base_url"

            # Add extra params for WatsonX
            if provider == "IBM WatsonX":
                runtime_metadata["model_name_param"] = "model_id"
                runtime_metadata["url_param"] = "url"
                runtime_metadata["project_id_param"] = "project_id"

            # Merge base metadata with runtime metadata
            full_metadata = {**base_metadata, **runtime_metadata}

            model_lookup[model_name] = {
                "name": model_name,
                "icon": icon,
                "category": provider,
                "provider": provider,
                "metadata": full_metadata,
            }

    # Convert string list to dict list
    result = []
    for name in model_names:
        if name in model_lookup:
            result.append(model_lookup[name])
        else:
            # Model not found in registry, create basic entry with minimal required metadata
            result.append(
                {
                    "name": name,
                    "provider": "Unknown",
                    "metadata": {
                        "model_class": "ChatOpenAI",  # Default fallback
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                    },
                }
            )

    return result


def get_llm(
    model,
    user_id: UUID | str | None,
    api_key=None,
    temperature=None,
    *,
    stream=False,
    watsonx_url=None,
    watsonx_project_id=None,
    ollama_base_url=None,
) -> Any:
    # Check if model is already a BaseLanguageModel instance (from a connection)
    try:
        from langchain_core.language_models import BaseLanguageModel

        if isinstance(model, BaseLanguageModel):
            # Model is already instantiated, return it directly
            return model
    except ImportError:
        pass

    # Safely extract model configuration
    if not model or not isinstance(model, list) or len(model) == 0:
        msg = "A model selection is required"
        raise ValueError(msg)

    # Extract the first model (only one expected)
    model = model[0]

    # Extract model configuration from metadata
    model_name = model.get("name")
    provider = model.get("provider")
    metadata = model.get("metadata", {})

    # Get model class and parameter names from metadata
    api_key_param = metadata.get("api_key_param", "api_key")

    # Get API key from user input or global variables
    api_key = get_api_key_for_provider(user_id, provider, api_key)

    # Validate API key (Ollama doesn't require one)
    if not api_key and provider != "Ollama":
        # Get the correct variable name from the provider variable mapping
        provider_variable_map = get_model_provider_variable_mapping()
        variable_name = provider_variable_map.get(provider, f"{provider.upper().replace(' ', '_')}_API_KEY")
        msg = (
            f"{provider} API key is required when using {provider} provider. "
            f"Please provide it in the component or configure it globally as {variable_name}."
        )
        raise ValueError(msg)

    # Get model class from metadata
    model_class = get_model_classes().get(metadata.get("model_class"))
    if model_class is None:
        msg = f"No model class defined for {model_name}"
        raise ValueError(msg)
    model_name_param = metadata.get("model_name_param", "model")

    # Check if this is a reasoning model that doesn't support temperature
    reasoning_models = metadata.get("reasoning_models", [])
    if model_name in reasoning_models:
        temperature = None

    # Build kwargs dynamically
    kwargs = {
        model_name_param: model_name,
        "streaming": stream,
        api_key_param: api_key,
    }

    if temperature is not None:
        kwargs["temperature"] = temperature

    # Add provider-specific parameters
    if provider == "IBM WatsonX":
        # For watsonx, url and project_id are required parameters
        # Only add them if both are provided by the component
        # If neither are provided, let ChatWatsonx handle it with its native error
        # This allows components without WatsonX-specific fields to fail gracefully

        url_param = metadata.get("url_param", "url")
        project_id_param = metadata.get("project_id_param", "project_id")

        has_url = watsonx_url is not None
        has_project_id = watsonx_project_id is not None

        if has_url and has_project_id:
            # Both provided - add them to kwargs
            kwargs[url_param] = watsonx_url
            kwargs[project_id_param] = watsonx_project_id
        elif has_url or has_project_id:
            # Only one provided - this is a misconfiguration in the component
            missing = "project ID" if has_url else "URL"
            provided = "URL" if has_url else "project ID"
            msg = (
                f"IBM WatsonX requires both a URL and project ID. "
                f"You provided a watsonx {provided} but no {missing}. "
                f"Please add a 'watsonx {missing.title()}' field to your component or use the Language Model component "
                f"which fully supports IBM WatsonX configuration."
            )
            raise ValueError(msg)
        # else: neither provided - let ChatWatsonx handle it (will fail with its own error)
    elif provider == "Ollama" and ollama_base_url:
        # For Ollama, handle custom base_url
        base_url_param = metadata.get("base_url_param", "base_url")
        kwargs[base_url_param] = ollama_base_url

    try:
        return model_class(**kwargs)
    except Exception as e:
        # If instantiation fails and it's WatsonX, provide additional context
        if provider == "IBM WatsonX" and ("url" in str(e).lower() or "project" in str(e).lower()):
            msg = (
                f"Failed to initialize IBM WatsonX model: {e}\n\n"
                "IBM WatsonX requires additional configuration parameters (API endpoint URL and project ID). "
                "This component may not support these parameters. "
                "Consider using the 'Language Model' component instead, which fully supports IBM WatsonX."
            )
            raise ValueError(msg) from e
        # Re-raise the original exception for other cases
        raise


def update_model_options_in_build_config(
    component: Any,
    build_config: dict,
    cache_key_prefix: str,
    get_options_func: Callable,
    field_name: str | None = None,
    field_value: Any = None,
) -> dict:
    """Helper function to update build config with cached model options.

    Uses instance-level caching to avoid expensive database calls on every field change.
    Cache is refreshed when:
    - api_key changes (may enable/disable providers)
    - Initial load (field_name is None)
    - Cache is empty or expired
    - Model field is being refreshed (field_name == "model")

    Args:
        component: Component instance with cache, user_id, and log attributes
        build_config: The build configuration dict to update
        cache_key_prefix: Prefix for the cache key (e.g., "language_model_options" or "embedding_model_options")
        get_options_func: Function to call to get model options (e.g., get_language_model_options)
        field_name: The name of the field being changed, if any
        field_value: The current value of the field being changed, if any

    Returns:
        Updated build_config dict with model options and providers set
    """
    import time

    # Cache key based on user_id
    cache_key = f"{cache_key_prefix}_{component.user_id}"
    cache_timestamp_key = f"{cache_key}_timestamp"
    cache_ttl = 30  # 30 seconds TTL to catch global variable changes faster

    # Check if cache is expired
    cache_expired = False
    if cache_timestamp_key in component.cache:
        time_since_cache = time.time() - component.cache[cache_timestamp_key]
        cache_expired = time_since_cache > cache_ttl

    # Check if we need to refresh
    should_refresh = (
        field_name == "api_key"  # API key changed
        or field_name is None  # Initial load
        or field_name == "model"  # Model field refresh button clicked
        or cache_key not in component.cache  # Cache miss
        or cache_expired  # Cache expired
    )

    if should_refresh:
        # Fetch options based on user's enabled models
        try:
            options = get_options_func(user_id=component.user_id)
            # Cache the results with timestamp
            component.cache[cache_key] = {"options": options}
            component.cache[cache_timestamp_key] = time.time()
        except KeyError as exc:
            # If we can't get user-specific options, fall back to empty
            component.log("Failed to fetch user-specific model options: %s", exc)
            component.cache[cache_key] = {"options": []}
            component.cache[cache_timestamp_key] = time.time()

    # Use cached results
    cached = component.cache.get(cache_key, {"options": []})
    build_config["model"]["options"] = cached["options"]

    # Set default value on initial load when field is empty
    # Fetch from user's default model setting in the database
    if not field_value or field_value == "":
        options = cached.get("options", [])
        if options:
            # Determine model type based on cache_key_prefix
            model_type = "embeddings" if cache_key_prefix == "embedding_model_options" else "language"

            # Try to get user's default model from the variable service
            default_model_name = None
            default_model_provider = None
            try:

                async def _get_default_model():
                    async with session_scope() as session:
                        variable_service = get_variable_service()
                        if variable_service is None:
                            return None, None
                        from langflow.services.variable.service import DatabaseVariableService

                        if not isinstance(variable_service, DatabaseVariableService):
                            return None, None

                        # Variable names match those in the API
                        var_name = (
                            "__default_embedding_model__"
                            if model_type == "embeddings"
                            else "__default_language_model__"
                        )

                        try:
                            var = await variable_service.get_variable_object(
                                user_id=UUID(component.user_id)
                                if isinstance(component.user_id, str)
                                else component.user_id,
                                name=var_name,
                                session=session,
                            )
                            if var and var.value:
                                import json

                                parsed_value = json.loads(var.value)
                                if isinstance(parsed_value, dict):
                                    return parsed_value.get("model_name"), parsed_value.get("provider")
                        except (ValueError, json.JSONDecodeError, TypeError):
                            # Variable not found or invalid format
                            logger.info("Variable not found or invalid format", exc_info=True)
                        return None, None

                default_model_name, default_model_provider = run_until_complete(_get_default_model())
            except Exception:  # noqa: BLE001
                # If we can't get default model, continue without it
                logger.info("Failed to get default model, continue without it", exc_info=True)

            # Find the default model in options
            default_model = None
            if default_model_name and default_model_provider:
                # Look for the user's preferred default model
                for opt in options:
                    if opt.get("name") == default_model_name and opt.get("provider") == default_model_provider:
                        default_model = opt
                        break

            # If user's default not found, fallback to first option
            if not default_model and options:
                default_model = options[0]

            # Set the value
            if default_model:
                build_config["model"]["value"] = [default_model]

    # Handle visibility logic:
    # - Show handle ONLY when field_value is "connect_other_models"
    # - Hide handle in all other cases (default, model selection, etc.)
    if field_value == "connect_other_models":
        # User explicitly selected "Connect other models", show the handle
        if cache_key_prefix == "embedding_model_options":
            build_config["model"]["input_types"] = ["Embeddings"]
        else:
            build_config["model"]["input_types"] = ["LanguageModel"]
    else:
        # Default case or model selection: hide the handle
        build_config["model"]["input_types"] = []

    return build_config
