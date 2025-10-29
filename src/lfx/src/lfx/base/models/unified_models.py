from functools import lru_cache
from uuid import UUID

from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS_DETAILED
from lfx.base.models.google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS_DETAILED
from lfx.base.models.ollama_constants import OLLAMA_EMBEDDING_MODELS_DETAILED, OLLAMA_MODELS_DETAILED
from lfx.base.models.openai_constants import OPENAI_EMBEDDING_MODELS_DETAILED, OPENAI_MODELS_DETAILED
from lfx.base.models.watsonx_constants import WATSONX_MODELS_DETAILED
from lfx.services.deps import get_variable_service, session_scope
from lfx.utils.async_helpers import run_until_complete


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
        "Google": {
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
    **metadata_filters
        Arbitrary key/value pairs to match against the model's metadata.
        Example: ``get_unified_models_detailed(size="4k", context_window=8192)``

    Notes:
    • Filtering is exact-match on the metadata values.
    • If you *do* want to see unsupported models set ``include_unsupported=True``.
    """
    if include_unsupported is None:
        include_unsupported = False

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


def get_api_key_for_provider(user_id: UUID | str, provider: str, api_key: str | None = None) -> str | None:
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

    # Map provider to global variable name
    provider_variable_map = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Google": "GOOGLE_API_KEY",
        "IBM WatsonX": "WATSONX_APIKEY",
    }

    variable_name = provider_variable_map.get(provider)
    if not variable_name:
        return None

    # Try to get from global variables
    try:

        async def _get_variable():
            async with session_scope() as session:
                variable_service = get_variable_service()
                if variable_service is None:
                    return None
                return await variable_service.get_variable(
                    user_id=UUID(user_id),
                    name=variable_name,
                    field="",
                    session=session,
                )

        return run_until_complete(_get_variable())
    except (RuntimeError, ValueError, TypeError, AttributeError):
        # If we can't get the global variable, return None
        # Handles: RuntimeError (async issues), ValueError (invalid UUID),
        # TypeError (None user_id), AttributeError (service issues)
        return None


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
            # WatsonX validation would require additional parameters
            # Skip for now as it needs project_id, url, etc.
            return
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
