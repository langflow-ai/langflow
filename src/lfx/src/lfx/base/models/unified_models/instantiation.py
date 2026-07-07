"""Model instantiation helpers (LLM + embeddings)."""

from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING, Any

from lfx.base.embeddings.embeddings_class import EmbeddingsWithModels
from lfx.base.models.model_utils import _to_str, replace_with_live_models
from lfx.log.logger import logger
from lfx.services.variable.request_scope import is_env_fallback_disabled
from lfx.utils.async_helpers import run_until_complete

from .class_registry import EMBEDDING_PARAM_MAPPINGS, EMBEDDING_PROVIDER_CLASS_MAPPING
from .credentials import _fetch_enabled_providers_for_user, _get_model_status
from .model_catalog import get_unified_models_detailed
from .provider_queries import model_provider_metadata

if TYPE_CHECKING:
    from uuid import UUID

    from langchain_core.embeddings import Embeddings


def _env_if_allowed(key: str) -> str | None:
    """Return ``os.environ.get(key)`` unless the active request disables env fallback.

    Connection config (provider URLs, project IDs, attribution headers) falls back to
    process env only when env fallback is allowed, so a served flow under
    ``no_env_fallback`` stays isolated from process-wide environment.
    """
    if is_env_fallback_disabled():
        return None
    return os.environ.get(key)


def _apply_registered_provider_connection(provider: str, user_id: UUID | str | None, kwargs: dict[str, Any]) -> None:
    """Apply a bundle-registered provider's non-secret connection variables to ``kwargs``.

    Core providers keep their explicit per-provider branches in ``get_llm`` /
    ``get_embeddings``; this generic path covers providers contributed via
    ``provider_registry``. Each non-secret metadata variable is resolved
    (database value, then process env when allowed) and applied to its declared
    ``langchain_param`` -- or forwarded as an HTTP header when ``is_header`` is
    set, mirroring the OpenRouter attribution-header handling. ``base_url`` is
    localhost-rewritten so a Dockerised backend can still reach a host-side
    server (e.g. a local vLLM endpoint). API keys / secrets are intentionally
    skipped: they are resolved through the dedicated api-key path.
    """
    from lfx.base.models import unified_models as unified_models_module
    from lfx.utils.util import transform_localhost_url

    provider_meta = model_provider_metadata.get(provider, {})
    provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)
    default_headers: dict[str, str] = {}
    for var in provider_meta.get("variables", []):
        if var.get("is_secret"):
            continue
        variable_key = var.get("variable_key")
        value = provider_vars.get(variable_key) or _env_if_allowed(variable_key)
        if not value:
            continue
        if var.get("is_header"):
            header_name = var.get("header_name")
            if header_name:
                default_headers[header_name] = value
            continue
        langchain_param = var.get("langchain_param")
        if not langchain_param or kwargs.get(langchain_param):
            continue
        kwargs[langchain_param] = transform_localhost_url(value) if langchain_param == "base_url" else value
    if default_headers:
        kwargs.setdefault("default_headers", {}).update(default_headers)


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

    # Stored selections sourced from ``get_unified_models_detailed`` (e.g. the
    # ``GET /api/v1/models`` catalog the frontend uses to augment its dropdown
    # right after a provider is configured, before the backend repopulates
    # ``template[model]["options"]``) carry only the raw ``create_model_metadata``
    # fields — none of the enriched ``*_param`` keys. Derive those param names
    # from the provider mapping (the same source ``get_language_model_options``
    # uses) so provider-specific names are honored instead of the generic
    # ``model`` / ``api_key`` defaults. This matters for IBM WatsonX: passing a
    # foundation-model id under the generic ``model`` kwarg routes ChatWatsonx to
    # the Model Gateway (a different, OpenAI-style catalog), surfacing as
    # "model <id> not found" / IAM "Provided user not found or active" even
    # though the dropdown, connection test, and standalone component all work.
    from lfx.base.models.model_metadata import get_provider_param_mapping

    provider_param_mapping = get_provider_param_mapping(provider) if provider else {}

    # Get model class and parameter names from metadata
    api_key_param = metadata.get("api_key_param") or provider_param_mapping.get("api_key_param", "api_key")

    # Capture the user-supplied api_key BEFORE resolution so we can name
    # it back in the error message if it was a Global Variable reference
    # the resolver couldn't find — see PR-12575 Bug 2.
    original_api_key_input = api_key.strip() if isinstance(api_key, str) else None

    # Get API key from user input or global variables
    api_key = unified_models_module.get_api_key_for_provider(user_id, provider, api_key)

    # Validate API key. Ollama needs none; extension-bundle providers that
    # declare api_key_required=False (e.g. local OpenAI-compatible servers such
    # as vLLM) also opt out via provider_registry.
    from lfx.base.models.provider_registry import is_api_key_optional, is_registered

    if not api_key and provider != "Ollama" and not is_api_key_optional(provider):
        # Bug 2 [P1] — Defensive guard: provider arriving as empty / None /
        # literal "Unknown" produces a nonsense error message (the worst
        # case being ``Unknown API key is required when using Unknown
        # provider … configure it globally as UNKNOWN_API_KEY``). The root
        # cause is the frontend ``ModelInputComponent`` falling back to
        # ``provider: "Unknown"`` when an option has no provider — but
        # regardless of how the bad value arrived, surfacing the literal
        # placeholder gives the user zero hint about what to do. Replace it
        # with a message that points back to the actionable fix: reselect
        # the model in the dropdown.
        if not provider or provider == "Unknown":
            msg = (
                "The selected model is missing a provider. "
                "Please reselect a model from the dropdown in the Language Model field "
                "so the component knows which provider's API key to use."
            )
            raise ValueError(msg)

        # Get the correct variable name from the provider variable mapping
        provider_variable_map = unified_models_module.get_model_provider_variable_mapping()
        variable_name = provider_variable_map.get(provider, f"{provider.upper().replace(' ', '_')}_API_KEY")
        # Bug 2 [P1] — when the user (or the assistant) passed a Global
        # Variable name as ``api_key`` that the resolver couldn't find,
        # name it back so the user can fix the actual reference instead
        # of being pointed at the canonical key (which may not be what
        # they configured).
        if original_api_key_input and original_api_key_input != variable_name:
            msg = (
                f"{provider} API key is required when using {provider} provider. "
                f"The variable '{original_api_key_input}' referenced by the component's "
                f"`api_key` field could not be resolved from environment variables or "
                f"Global Variables. Configure '{original_api_key_input}' (or the canonical "
                f"'{variable_name}') in Settings → Model Providers."
            )
        else:
            msg = (
                f"{provider} API key is required when using {provider} provider. "
                f"Please provide it in the component or configure it globally as {variable_name}."
            )
        raise ValueError(msg)

    # OpenAI-compatible servers that opt out of API keys (api_key_required=False)
    # still need a non-empty placeholder so the client library constructs, e.g.
    # a local vLLM endpoint without auth.
    if not api_key and is_api_key_optional(provider):
        api_key = "EMPTY"  # pragma: allowlist secret

    # Get model class from metadata, falling back to the provider-level
    # mapping when the stored model value was sourced from
    # ``get_unified_models_detailed`` (which, unlike
    # ``get_language_model_options``, does not inject ``model_class`` into
    # each model's metadata).  This happens for example immediately after a
    # user configures a provider and the frontend augments its dropdown from
    # ``/api/v1/models`` before the backend has repopulated
    # ``template[model]["options"]``; the resulting stored selection only
    # carries the raw ``create_model_metadata`` fields, so we have to derive
    # ``model_class`` from the provider mapping that
    # ``get_language_model_options`` would have used.
    model_class_name = metadata.get("model_class") or provider_param_mapping.get("model_class")
    if not model_class_name:
        msg = f"No model class defined for {model_name}"
        raise ValueError(msg)
    model_class = unified_models_module.get_model_class(model_class_name)
    # The provider mapping stores the model-name param under ``model_param``
    # (``get_language_model_options`` re-keys it to ``model_name_param``); fall
    # back to it so e.g. IBM WatsonX resolves to ``model_id`` rather than the
    # generic ``model``.
    model_name_param = metadata.get("model_name_param") or provider_param_mapping.get("model_param", "model")

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
        url_param = metadata.get("url_param") or provider_param_mapping.get("url_param", "url")
        project_id_param = metadata.get("project_id_param") or provider_param_mapping.get(
            "project_id_param", "project_id"
        )

        # Get all provider variables from database
        provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)

        # Priority: component value > database value > env var
        watsonx_url_value = (
            watsonx_url if watsonx_url else provider_vars.get("WATSONX_URL") or _env_if_allowed("WATSONX_URL")
        )
        watsonx_project_id_value = (
            watsonx_project_id
            if watsonx_project_id
            else provider_vars.get("WATSONX_PROJECT_ID") or _env_if_allowed("WATSONX_PROJECT_ID")
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
            else provider_vars.get("OLLAMA_BASE_URL") or _env_if_allowed("OLLAMA_BASE_URL")
        )
        if ollama_base_url_value:
            kwargs[base_url_param] = ollama_base_url_value
    elif provider == "OpenAI":
        from lfx.utils.util import transform_localhost_url

        provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)
        openai_base_url_value = provider_vars.get("OPENAI_BASE_URL") or _env_if_allowed("OPENAI_BASE_URL")
        if openai_base_url_value:
            kwargs["base_url"] = transform_localhost_url(openai_base_url_value)
    elif provider == "OpenRouter":
        # OpenRouter speaks the OpenAI wire format. Point ChatOpenAI at the
        # OpenRouter base URL (declared in MODEL_PROVIDER_METADATA) and forward
        # any configured attribution headers (HTTP-Referer, X-Title) so usage
        # shows up correctly in the OpenRouter dashboard.
        provider_meta = model_provider_metadata.get(provider, {})
        base_url_value = provider_meta.get("base_url")
        if base_url_value:
            kwargs["base_url"] = base_url_value

        provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)
        default_headers: dict[str, str] = {}
        for var in provider_meta.get("variables", []):
            if not var.get("is_header"):
                continue
            header_name = var.get("header_name")
            # KeyError on a misconfigured metadata entry beats silently
            # skipping a header the operator expects to be sent.
            variable_key = var["variable_key"]
            value = provider_vars.get(variable_key) or _env_if_allowed(variable_key)
            if header_name and value:
                default_headers[header_name] = value
        if default_headers:
            kwargs["default_headers"] = default_headers
    elif provider == "Azure AI Foundry":
        provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)
        endpoint_value = provider_vars.get("AZURE_AI_FOUNDRY_ENDPOINT") or _env_if_allowed("AZURE_AI_FOUNDRY_ENDPOINT")
        if not endpoint_value:
            msg = (
                "Azure AI Foundry endpoint is required. Configure AZURE_AI_FOUNDRY_ENDPOINT "
                "in Settings → Model Providers or set the environment variable."
            )
            raise ValueError(msg)
        kwargs["endpoint"] = endpoint_value
    elif is_registered(provider):
        # Bundle-contributed provider: apply its declared connection variables
        # (base_url, attribution headers, etc.) generically from its metadata.
        _apply_registered_provider_connection(provider, user_id, kwargs)

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


def _get_provider_catalog_models(
    provider: str,
    user_id: UUID | str | None,
) -> list[dict[str, Any]]:
    """Return catalog model entries for a provider (LLM + embedding, not type-filtered)."""
    provider_models = get_unified_models_detailed(
        providers=[provider],
        include_deprecated=False,
        include_unsupported=False,
    )

    if user_id:
        with contextlib.suppress(Exception):
            enabled_providers = run_until_complete(_fetch_enabled_providers_for_user(user_id))
            if provider in enabled_providers:
                replace_with_live_models(
                    provider_models,
                    user_id,
                    {provider},
                    None,
                    model_provider_metadata,
                )

    catalog_models: list[dict[str, Any]] = []
    for provider_data in provider_models:
        if provider_data.get("provider") != provider:
            continue
        catalog_models.extend(provider_data.get("models", []))
    return catalog_models


def _get_provider_enabled_model_names(
    provider: str,
    user_id: UUID | str | None,
) -> list[str]:
    """Return model names enabled for a provider in Model Providers settings.

    Includes both LLM and embedding models (e.g. gpt-5 and text-embedding-3-small).
    When *user_id* is absent, returns all non-deprecated catalog models for the provider.
    """
    catalog_models = _get_provider_catalog_models(provider, user_id)

    disabled_models: set[str] = set()
    explicitly_enabled_models: set[str] = set()
    enabled_providers: set[str] = set()
    if user_id:
        with contextlib.suppress(Exception):
            disabled_models, explicitly_enabled_models = run_until_complete(_get_model_status(user_id))
        with contextlib.suppress(Exception):
            enabled_providers = run_until_complete(_fetch_enabled_providers_for_user(user_id))

    apply_user_prefs = bool(user_id and enabled_providers and provider in enabled_providers)

    model_names: list[str] = []
    for model_data in catalog_models:
        model_name = model_data.get("model_name")
        if not model_name:
            continue

        if apply_user_prefs:
            metadata = model_data.get("metadata", {})
            is_default = metadata.get("default", False)
            if not is_default and model_name not in explicitly_enabled_models:
                continue
            if model_name in disabled_models:
                continue

        model_names.append(model_name)
    return model_names


def _is_embedding_catalog_model(model_data: dict[str, Any]) -> bool:
    """Return True when a catalog entry is an embedding model."""
    model_type = model_data.get("metadata", {}).get("model_type", "llm")
    return model_type == "embeddings"


def _get_configured_embedding_providers(
    user_id: UUID | str | None,
    selected_provider: str,
) -> list[str]:
    """Return embedding-capable providers configured in Model Providers."""
    if not user_id:
        return [selected_provider]

    with contextlib.suppress(Exception):
        enabled_providers = run_until_complete(_fetch_enabled_providers_for_user(user_id))
        providers = sorted(p for p in enabled_providers if p in EMBEDDING_PROVIDER_CLASS_MAPPING)
        if selected_provider not in providers:
            providers.insert(0, selected_provider)
        return providers

    return [selected_provider]


def _get_provider_embedding_model_names(
    provider: str,
    user_id: UUID | str | None,
) -> list[str]:
    """Return enabled embedding model names for a single provider."""
    catalog_by_name = {
        model_data.get("model_name"): model_data
        for model_data in _get_provider_catalog_models(provider, user_id)
        if model_data.get("model_name")
    }

    model_names: list[str] = []
    for model_name in _get_provider_enabled_model_names(provider, user_id):
        model_data = catalog_by_name.get(model_name)
        if model_data is None or not _is_embedding_catalog_model(model_data):
            continue
        model_names.append(model_name)
    return model_names


def _compose_embedding_kwargs(
    provider: str,
    model_name: str,
    user_id: UUID | str | None,
    unified_models_module: Any,
    *,
    selected_provider: str,
    metadata: dict[str, Any] | None = None,
    component_api_key: str | None = None,
    api_base: str | None = None,
    dimensions: int | None = None,
    chunk_size: int | None = None,
    request_timeout: float | None = None,
    max_retries: int | None = None,
    show_progress_bar: bool | None = None,
    model_kwargs: dict[str, Any] | None = None,
    watsonx_url: str | None = None,
    watsonx_project_id: str | None = None,
    watsonx_truncate_input_tokens: int | None = None,
    watsonx_input_text: bool | None = None,
    ollama_base_url: str | None = None,
) -> tuple[type, dict[str, Any]] | None:
    """Build kwargs for a provider/model pair. Returns None when credentials are missing."""
    from lfx.base.models.provider_registry import is_api_key_optional, is_registered

    metadata = metadata or {}
    api_key_override = component_api_key if provider == selected_provider else None
    api_key = unified_models_module.get_api_key_for_provider(user_id, provider, api_key_override)
    if not api_key and provider != "Ollama" and not is_api_key_optional(provider):
        return None
    if not api_key and is_api_key_optional(provider):
        api_key = "EMPTY"  # pragma: allowlist secret

    embedding_class_name = metadata.get("embedding_class") or EMBEDDING_PROVIDER_CLASS_MAPPING.get(provider)
    if not embedding_class_name:
        return None

    param_mapping: dict[str, str] = metadata.get("param_mapping") or EMBEDDING_PARAM_MAPPINGS.get(provider, {})
    if not param_mapping:
        return None

    embedding_class = unified_models_module.get_embedding_class(embedding_class_name)

    api_base_value = _to_str(api_base) if provider == selected_provider else None
    if provider == "OpenAI" and not api_base_value:
        api_base_value = _to_str(os.environ.get("OPENAI_EMBEDDINGS_API_BASE")) or _to_str(
            os.environ.get("OPENAI_API_BASE")
        )

    kwargs: dict[str, Any] = {}
    if "model" in param_mapping:
        kwargs[param_mapping["model"]] = model_name
    elif "model_id" in param_mapping:
        kwargs[param_mapping["model_id"]] = model_name

    if "api_key" in param_mapping and api_key:
        kwargs[param_mapping["api_key"]] = api_key
    elif is_registered(provider) and api_key:
        # Bundle providers may omit an explicit "api_key" slot in their embedding
        # param_mapping; pass the resolved key (or the api-key-optional
        # placeholder) under the OpenAI-compatible "api_key" kwarg so the client
        # still authenticates.
        kwargs.setdefault("api_key", api_key)

    use_component_overrides = provider == selected_provider
    optional_params: dict[str, Any] = {
        "api_base": api_base_value if use_component_overrides else None,
        "dimensions": dimensions if use_component_overrides else None,
        "chunk_size": chunk_size if use_component_overrides else None,
        "request_timeout": request_timeout if use_component_overrides else None,
        "max_retries": max_retries if use_component_overrides else None,
        "show_progress_bar": show_progress_bar if use_component_overrides else None,
        "model_kwargs": model_kwargs if use_component_overrides else None,
    }

    if provider in {"IBM WatsonX", "IBM watsonx.ai"}:
        watsonx_provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)
        url_value = (
            (watsonx_url if use_component_overrides else None)
            or watsonx_provider_vars.get("WATSONX_URL")
            or _env_if_allowed("WATSONX_URL")
        )
        pid_value = (
            (watsonx_project_id if use_component_overrides else None)
            or watsonx_provider_vars.get("WATSONX_PROJECT_ID")
            or _env_if_allowed("WATSONX_PROJECT_ID")
        )
        has_url = bool(url_value)
        has_project_id = bool(pid_value)

        if has_url and has_project_id:
            if "url" in param_mapping:
                kwargs[param_mapping["url"]] = url_value
            if "project_id" in param_mapping:
                kwargs[param_mapping["project_id"]] = pid_value
        elif has_url or has_project_id:
            if use_component_overrides:
                missing = "project ID (WATSONX_PROJECT_ID)" if has_url else "URL (WATSONX_URL)"
                provided = "URL" if has_url else "project ID"
                msg = (
                    f"IBM WatsonX requires both a URL and project ID. "
                    f"You provided a watsonx {provided} but no {missing}. "
                    f"Please configure the missing value in the component or set the environment variable."
                )
                raise ValueError(msg)
            return None

        if use_component_overrides:
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

    if provider == "Ollama" and "base_url" in param_mapping:
        provider_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)
        base_url_value = (
            (ollama_base_url if use_component_overrides else None)
            or provider_vars.get("OLLAMA_BASE_URL")
            or _env_if_allowed("OLLAMA_BASE_URL")
            or "http://localhost:11434"
        )
        kwargs[param_mapping["base_url"]] = base_url_value

    # Bundle-contributed provider: apply its declared connection variables
    # (e.g. an OpenAI-compatible base_url) generically from its metadata. Runs
    # before the optional-params loop so an explicit api_base still wins.
    if is_registered(provider):
        _apply_registered_provider_connection(provider, user_id, kwargs)

    for param_name, param_value in optional_params.items():
        if param_value is not None and param_name in param_mapping:
            if (
                param_name == "request_timeout"
                and provider == "Google Generative AI"
                and isinstance(param_value, (int, float))
            ):
                kwargs[param_mapping[param_name]] = {"timeout": param_value}
            else:
                kwargs[param_mapping[param_name]] = param_value

    return embedding_class, kwargs


def _build_available_embedding_models(
    *,
    selected_provider: str,
    primary_model_name: str,
    primary_instance: Embeddings,
    user_id: UUID | str | None,
    unified_models_module: Any,
    metadata: dict[str, Any],
    component_api_key: str | None,
    api_base: str | None,
    dimensions: int | None,
    chunk_size: int | None,
    request_timeout: float | None,
    max_retries: int | None,
    show_progress_bar: bool | None,
    model_kwargs: dict[str, Any] | None,
    watsonx_url: str | None,
    watsonx_project_id: str | None,
    watsonx_truncate_input_tokens: int | None,
    watsonx_input_text: bool | None,
    ollama_base_url: str | None,
) -> dict[str, Embeddings]:
    """Build embedding instances for every enabled embedding model on configured providers."""
    available_models: dict[str, Embeddings] = {primary_model_name: primary_instance}

    for provider in _get_configured_embedding_providers(user_id, selected_provider):
        provider_metadata = metadata if provider == selected_provider else {}
        for model_name in _get_provider_embedding_model_names(provider, user_id):
            if model_name in available_models:
                continue

            composed = _compose_embedding_kwargs(
                provider,
                model_name,
                user_id,
                unified_models_module,
                selected_provider=selected_provider,
                metadata=provider_metadata,
                component_api_key=component_api_key,
                api_base=api_base,
                dimensions=dimensions,
                chunk_size=chunk_size,
                request_timeout=request_timeout,
                max_retries=max_retries,
                show_progress_bar=show_progress_bar,
                model_kwargs=model_kwargs,
                watsonx_url=watsonx_url,
                watsonx_project_id=watsonx_project_id,
                watsonx_truncate_input_tokens=watsonx_truncate_input_tokens,
                watsonx_input_text=watsonx_input_text,
                ollama_base_url=ollama_base_url,
            )
            if composed is None:
                continue

            embedding_class, model_kwargs_dict = composed
            try:
                available_models[model_name] = embedding_class(**model_kwargs_dict)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Failed to instantiate embedding model %s for provider %s; skipping",
                    model_name,
                    provider,
                    exc_info=True,
                )

    return available_models


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
    """Instantiate an embeddings model from a model selection dict.

    Returns an :class:`~lfx.base.embeddings.embeddings_class.EmbeddingsWithModels`
    wrapper containing the primary instance for the selected model and an
    ``available_models`` map of enabled embedding models from every configured provider.
    """
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

    # --- resolve API key for the selected provider ---------------------------
    api_key = unified_models_module.get_api_key_for_provider(user_id, provider, api_key)
    from lfx.base.models.provider_registry import is_api_key_optional

    if not api_key and provider != "Ollama" and not is_api_key_optional(provider):
        provider_variable_map = unified_models_module.get_model_provider_variable_mapping()
        variable_name = provider_variable_map.get(provider, f"{provider.upper().replace(' ', '_')}_API_KEY")
        msg = (
            f"{provider} API key is required. "
            f"Please provide it in the component or configure it globally as {variable_name}."
        )
        raise ValueError(msg)

    # OpenAI-compatible embedding servers that opt out of API keys still need a
    # non-empty placeholder so the client library constructs (e.g. local vLLM).
    if not api_key and is_api_key_optional(provider):
        api_key = "EMPTY"  # pragma: allowlist secret

    if not model_name:
        msg = "Embedding model name is required"
        raise ValueError(msg)

    composed = _compose_embedding_kwargs(
        provider,
        model_name,
        user_id,
        unified_models_module,
        selected_provider=provider,
        metadata=metadata,
        component_api_key=api_key,
        api_base=_to_str(api_base),
        dimensions=int(dimensions) if dimensions else None,
        chunk_size=int(chunk_size) if chunk_size else None,
        request_timeout=float(request_timeout) if request_timeout else None,
        max_retries=int(max_retries) if max_retries else None,
        show_progress_bar=show_progress_bar,
        model_kwargs=model_kwargs if model_kwargs else None,
        watsonx_url=watsonx_url,
        watsonx_project_id=watsonx_project_id,
        watsonx_truncate_input_tokens=watsonx_truncate_input_tokens,
        watsonx_input_text=watsonx_input_text,
        ollama_base_url=ollama_base_url,
    )
    if composed is None:
        embedding_class_name = metadata.get("embedding_class") or EMBEDDING_PROVIDER_CLASS_MAPPING.get(provider)
        if not embedding_class_name:
            msg = (
                f"No embedding class defined in metadata for {model_name} (provider: {provider}). "
                "Add the provider to EMBEDDING_PROVIDER_CLASS_MAPPING or re-select the model."
            )
            raise ValueError(msg)
        unified_models_module.get_embedding_class(embedding_class_name)
        param_mapping = metadata.get("param_mapping") or EMBEDDING_PARAM_MAPPINGS.get(provider, {})
        if not param_mapping:
            msg = (
                f"Parameter mapping not found in metadata for model '{model_name}' (provider: {provider}). "
                "This usually means the model was saved with an older format that is no longer recognized. "
                "Please re-select the embedding model in the component configuration."
            )
            raise ValueError(msg)
        msg = f"{provider} API key is required."
        raise ValueError(msg)

    embedding_class, kwargs = composed

    try:
        primary_instance = embedding_class(**kwargs)
    except Exception as e:
        if provider == "IBM WatsonX" and ("url" in str(e).lower() or "project" in str(e).lower()):
            msg = (
                f"Failed to initialize IBM WatsonX embedding model: {e}\n\n"
                "IBM WatsonX requires additional configuration parameters (API endpoint URL and project ID)."
            )
            raise ValueError(msg) from e
        raise

    available_models = _build_available_embedding_models(
        selected_provider=provider,
        primary_model_name=model_name,
        primary_instance=primary_instance,
        user_id=user_id,
        unified_models_module=unified_models_module,
        metadata=metadata,
        component_api_key=api_key,
        api_base=_to_str(api_base),
        dimensions=int(dimensions) if dimensions else None,
        chunk_size=int(chunk_size) if chunk_size else None,
        request_timeout=float(request_timeout) if request_timeout else None,
        max_retries=int(max_retries) if max_retries else None,
        show_progress_bar=show_progress_bar,
        model_kwargs=model_kwargs if model_kwargs else None,
        watsonx_url=watsonx_url,
        watsonx_project_id=watsonx_project_id,
        watsonx_truncate_input_tokens=watsonx_truncate_input_tokens,
        watsonx_input_text=watsonx_input_text,
        ollama_base_url=ollama_base_url,
    )

    return EmbeddingsWithModels(
        embeddings=primary_instance,
        available_models=available_models,
    )
