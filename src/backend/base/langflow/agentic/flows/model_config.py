"""Shared model configuration for agentic flows."""

from lfx.base.models.model_metadata import get_provider_param_mapping


def build_model_config(provider: str, model_name: str) -> list[dict]:
    """Build model configuration for LanguageModelComponent.

    Resolves the ``model_class`` and param names from the CANONICAL provider
    metadata (``get_provider_param_mapping`` — the same source TranslationFlow
    and the central model registry use). A previous hardcoded ``MODEL_CLASSES``
    dict drifted from the registry and mapped Google Generative AI to
    ``ChatGoogleGenerativeAI`` while the registry only knows
    ``ChatGoogleGenerativeAIFixed`` — so any Gemini model died at first prompt
    with "Unknown model class: ChatGoogleGenerativeAI". Deriving from the
    canonical mapping makes that drift impossible (and picks up provider-
    specific params like Ollama's base_url / WatsonX's url+project_id).
    """
    mapping = get_provider_param_mapping(provider)
    metadata: dict = {
        "api_key_param": mapping.get("api_key_param", "api_key"),  # pragma: allowlist secret
        "context_length": 128000,
        "model_class": mapping.get("model_class", "ChatOpenAI"),
        "model_name_param": mapping.get("model_name_param", "model"),
    }
    for extra_param in ("url_param", "project_id_param", "base_url_param"):
        if extra_param in mapping:
            metadata[extra_param] = mapping[extra_param]
    return [
        {
            "icon": provider,
            "metadata": metadata,
            "name": model_name,
            "provider": provider,
        }
    ]
