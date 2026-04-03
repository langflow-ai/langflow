"""Model instantiation helpers (LLM + embeddings)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from lfx.base.models.model_utils import _to_str

from .provider_queries import model_provider_metadata

if TYPE_CHECKING:
    from uuid import UUID


def get_llm(
    model,
    user_id: UUID | str | None,
    api_key=None,
    temperature=None,
    *,
    stream=False,
    max_tokens=None,
    watsonx_url=None,
    watsonx_project_id=None,
    ollama_base_url=None,
) -> Any:
    # Resolve helpers via package namespace so tests patching
    # lfx.base.models.unified_models.<name> keep working.
    from lfx.base.models import unified_models as unified_models_module

    # Coerce provider-specific string params (Message/Data may leak through StrInput)
    ollama_base_url = _to_str(ollama_base_url)
    watsonx_url = _to_str(watsonx_url)
    watsonx_project_id = _to_str(watsonx_project_id)

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
    api_key = unified_models_module.get_api_key_for_provider(user_id, provider, api_key)

    # Validate API key (Ollama doesn't require one)
    if not api_key and provider != "Ollama":
        # Get the correct variable name from the provider variable mapping
        provider_variable_map = unified_models_module.get_model_provider_variable_mapping()
        variable_name = provider_variable_map.get(provider, f"{provider.upper().replace(' ', '_')}_API_KEY")
        msg = (
            f"{provider} API key is required when using {provider} provider. "
            f"Please provide it in the component or configure it globally as {variable_name}."
        )
        raise ValueError(msg)

    # Get model class from metadata
    model_class_name = metadata.get("model_class")
    if not model_class_name:
        msg = f"No model class defined for {model_name}"
        raise ValueError(msg)
    model_class = unified_models_module.get_model_class(model_class_name)
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

    # Add max_tokens with provider-specific field name (only when a valid integer >= 1)
    if max_tokens is not None and max_tokens != "":
        try:
            max_tokens_int = int(max_tokens)
            if max_tokens_int >= 1:
                # Look up provider-specific field name from model metadata first,
                # then fall back to provider metadata, then default to "max_tokens"
                max_tokens_param = metadata.get("max_tokens_field_name")
                if not max_tokens_param:
                    provider_meta = model_provider_metadata.get(provider, {})
                    max_tokens_param = provider_meta.get("max_tokens_field_name", "max_tokens")
                kwargs[max_tokens_param] = max_tokens_int
        except (TypeError, ValueError):
            pass  # Skip invalid max_tokens (e.g. empty string from form input)

    # Enable streaming usage for providers that support it
    if provider in ["OpenAI", "Anthropic"]:
        kwargs["stream_usage"] = True

    # Add provider-specific parameters
    if provider in {"IBM WatsonX", "IBM watsonx.ai"}:
        # For watsonx, url and project_id are required parameters
        # Try database first, then component values, then environment variables
        url_param = metadata.get("url_param", "url")
        project_id_param = metadata.get("project_id_param", "project_id")

        # Get all provider variables from database
        provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)

        # Priority: component value > database value > env var
        watsonx_url_value = (
            watsonx_url if watsonx_url else provider_vars.get("WATSONX_URL") or os.environ.get("WATSONX_URL")
        )
        watsonx_project_id_value = (
            watsonx_project_id
            if watsonx_project_id
            else provider_vars.get("WATSONX_PROJECT_ID") or os.environ.get("WATSONX_PROJECT_ID")
        )

        has_url = bool(watsonx_url_value)
        has_project_id = bool(watsonx_project_id_value)

        if has_url and has_project_id:
            # Both provided - add them to kwargs
            kwargs[url_param] = watsonx_url_value
            kwargs[project_id_param] = watsonx_project_id_value
        elif has_url or has_project_id:
            # Only one provided - this is a misconfiguration
            missing = "project ID (WATSONX_PROJECT_ID)" if has_url else "URL (WATSONX_URL)"
            provided = "URL" if has_url else "project ID"
            msg = (
                f"IBM WatsonX requires both a URL and project ID. "
                f"You provided a watsonx {provided} but no {missing}. "
                f"Please configure the missing value in the component or set the environment variable."
            )
            raise ValueError(msg)
        # else: neither provided - let ChatWatsonx handle it (will fail with its own error)
    elif provider == "Ollama":
        # For Ollama, handle custom base_url with database > component > env var fallback
        base_url_param = metadata.get("base_url_param", "base_url")

        # Get all provider variables from database
        provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)

        # Priority: component value > database value > env var
        ollama_base_url_value = (
            ollama_base_url
            if ollama_base_url
            else provider_vars.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_BASE_URL")
        )
        if ollama_base_url_value:
            kwargs[base_url_param] = ollama_base_url_value

    try:
        return model_class(**kwargs)
    except Exception as e:
        # If instantiation fails and it's WatsonX, provide additional context
        if provider in {"IBM WatsonX", "IBM watsonx.ai"} and ("url" in str(e).lower() or "project" in str(e).lower()):
            msg = (
                f"Failed to initialize IBM WatsonX model: {e}\n\n"
                "IBM WatsonX requires additional configuration parameters (API endpoint URL and project ID). "
                "This component may not support these parameters. "
                "Consider using the 'Language Model' component instead, which fully supports IBM WatsonX."
            )
            raise ValueError(msg) from e
        # Re-raise the original exception for other cases
        raise


def get_embeddings(
    model,
    user_id: UUID | str | None = None,
    api_key=None,
    *,
    api_base=None,
    dimensions=None,
    chunk_size=None,
    request_timeout=None,
    max_retries=None,
    show_progress_bar=None,
    model_kwargs=None,
    watsonx_url=None,
    watsonx_project_id=None,
    watsonx_truncate_input_tokens=None,
    watsonx_input_text=None,
    ollama_base_url=None,
) -> Any:
    """Instantiate an embeddings model from a model selection dict."""
    # Resolve helpers via package namespace so tests patching
    # lfx.base.models.unified_models.<name> keep working.
    from lfx.base.models import unified_models as unified_models_module

    # Coerce provider-specific string params
    ollama_base_url = _to_str(ollama_base_url)
    watsonx_url = _to_str(watsonx_url)
    watsonx_project_id = _to_str(watsonx_project_id)

    # Passthrough: already-instantiated Embeddings object from a connection
    try:
        from langchain_core.embeddings import Embeddings as BaseEmbeddings

        if isinstance(model, BaseEmbeddings):
            return model
    except ImportError:
        pass

    # Validate input
    if not model or not isinstance(model, list) or len(model) == 0:
        msg = "An embedding model selection is required"
        raise ValueError(msg)

    model_dict = model[0]
    model_name = model_dict.get("name")
    provider = model_dict.get("provider")
    metadata = model_dict.get("metadata", {})

    # --- resolve API key -----------------------------------------------------
    api_key = unified_models_module.get_api_key_for_provider(user_id, provider, api_key)
    if not api_key and provider != "Ollama":
        provider_variable_map = unified_models_module.get_model_provider_variable_mapping()
        variable_name = provider_variable_map.get(provider, f"{provider.upper().replace(' ', '_')}_API_KEY")
        msg = (
            f"{provider} API key is required. "
            f"Please provide it in the component or configure it globally as {variable_name}."
        )
        raise ValueError(msg)

    if not model_name:
        msg = "Embedding model name is required"
        raise ValueError(msg)

    # Get embedding class from metadata
    embedding_class_name = metadata.get("embedding_class")
    if not embedding_class_name:
        msg = f"No embedding class defined in metadata for {model_name}"
        raise ValueError(msg)
    embedding_class = unified_models_module.get_embedding_class(embedding_class_name)

    # --- build kwargs from param_mapping -------------------------------------
    param_mapping: dict[str, str] = metadata.get("param_mapping", {})
    if not param_mapping:
        msg = (
            f"Parameter mapping not found in metadata for model '{model_name}' (provider: {provider}). "
            "This usually means the model was saved with an older format that is no longer recognized. "
            "Please re-select the embedding model in the component configuration."
        )
        raise ValueError(msg)

    kwargs: dict[str, Any] = {}

    # Model name
    if "model" in param_mapping:
        kwargs[param_mapping["model"]] = model_name
    elif "model_id" in param_mapping:
        kwargs[param_mapping["model_id"]] = model_name

    # API key
    if "api_key" in param_mapping and api_key:
        kwargs[param_mapping["api_key"]] = api_key

    # Optional parameters - only add when both a value is supplied *and* the
    # provider's param_mapping declares the corresponding key.
    optional_params: dict[str, Any] = {
        "api_base": _to_str(api_base) or None,
        "dimensions": int(dimensions) if dimensions else None,
        "chunk_size": int(chunk_size) if chunk_size else None,
        "request_timeout": float(request_timeout) if request_timeout else None,
        "max_retries": int(max_retries) if max_retries else None,
        "show_progress_bar": show_progress_bar,
        "model_kwargs": model_kwargs if model_kwargs else None,
    }

    # Watson-specific parameters
    if provider in {"IBM WatsonX", "IBM watsonx.ai"}:
        watsonx_provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)
        url_value = watsonx_url or watsonx_provider_vars.get("WATSONX_URL") or os.environ.get("WATSONX_URL")
        pid_value = (
            watsonx_project_id
            or watsonx_provider_vars.get("WATSONX_PROJECT_ID")
            or os.environ.get("WATSONX_PROJECT_ID")
        )

        has_url = bool(url_value)
        has_project_id = bool(pid_value)

        if has_url and has_project_id:
            if "url" in param_mapping:
                kwargs[param_mapping["url"]] = url_value
            if "project_id" in param_mapping:
                kwargs[param_mapping["project_id"]] = pid_value
        elif has_url or has_project_id:
            missing = "project ID (WATSONX_PROJECT_ID)" if has_url else "URL (WATSONX_URL)"
            provided = "URL" if has_url else "project ID"
            msg = (
                f"IBM WatsonX requires both a URL and project ID. "
                f"You provided a watsonx {provided} but no {missing}. "
                f"Please configure the missing value in the component or set the environment variable."
            )
            raise ValueError(msg)

        # Build WatsonX embed params (truncate_input_tokens, return_options)
        watsonx_params = {}
        if watsonx_truncate_input_tokens is not None:
            try:
                from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames

                watsonx_params[EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS] = int(watsonx_truncate_input_tokens)
            except ImportError:
                watsonx_params["truncate_input_tokens"] = int(watsonx_truncate_input_tokens)
        if watsonx_input_text is not None:
            try:
                from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames

                watsonx_params[EmbedTextParamsMetaNames.RETURN_OPTIONS] = {"input_text": bool(watsonx_input_text)}
            except ImportError:
                watsonx_params["return_options"] = {"input_text": bool(watsonx_input_text)}
        if watsonx_params:
            kwargs["params"] = watsonx_params

    # Ollama-specific parameters
    if provider == "Ollama" and "base_url" in param_mapping:
        provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)
        base_url_value = (
            ollama_base_url
            or provider_vars.get("OLLAMA_BASE_URL")
            or os.environ.get("OLLAMA_BASE_URL")
            or "http://localhost:11434"
        )
        kwargs[param_mapping["base_url"]] = base_url_value

    # Add optional parameters if they have values and are mapped
    for param_name, param_value in optional_params.items():
        if param_value is not None and param_name in param_mapping:
            # Google wraps timeout in a dict
            if (
                param_name == "request_timeout"
                and provider == "Google Generative AI"
                and isinstance(param_value, (int, float))
            ):
                kwargs[param_mapping[param_name]] = {"timeout": param_value}
            else:
                kwargs[param_mapping[param_name]] = param_value

    try:
        return embedding_class(**kwargs)
    except Exception as e:
        if provider == "IBM WatsonX" and ("url" in str(e).lower() or "project" in str(e).lower()):
            msg = (
                f"Failed to initialize IBM WatsonX embedding model: {e}\n\n"
                "IBM WatsonX requires additional configuration parameters (API endpoint URL and project ID)."
            )
            raise ValueError(msg) from e
        raise
