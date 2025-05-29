from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
OPENAI_MODELS_DETAILED = {
    # Regular OpenAI Models
    "gpt-4o-mini": create_model_metadata(provider="OpenAI", name="gpt-4o-mini", icon="OpenAI", tool_calling=True),
    "gpt-4o": create_model_metadata(provider="OpenAI", name="gpt-4o", icon="OpenAI", tool_calling=True),
    "gpt-4.1": create_model_metadata(provider="OpenAI", name="gpt-4.1", icon="OpenAI", tool_calling=True),
    "gpt-4.1-mini": create_model_metadata(provider="OpenAI", name="gpt-4.1-mini", icon="OpenAI", tool_calling=True),
    "gpt-4.1-nano": create_model_metadata(provider="OpenAI", name="gpt-4.1-nano", icon="OpenAI", tool_calling=True),
    "gpt-4.5-preview": create_model_metadata(
        provider="OpenAI", name="gpt-4.5-preview", icon="OpenAI", tool_calling=True, preview=True
    ),
    "gpt-4-turbo": create_model_metadata(provider="OpenAI", name="gpt-4-turbo", icon="OpenAI", tool_calling=True),
    "gpt-4-turbo-preview": create_model_metadata(
        provider="OpenAI", name="gpt-4-turbo-preview", icon="OpenAI", tool_calling=True, preview=True
    ),
    "gpt-4": create_model_metadata(provider="OpenAI", name="gpt-4", icon="OpenAI", tool_calling=True),
    "gpt-3.5-turbo": create_model_metadata(provider="OpenAI", name="gpt-3.5-turbo", icon="OpenAI", tool_calling=True),
    # Reasoning Models
    "o1": create_model_metadata(provider="OpenAI", name="o1", icon="OpenAI", reasoning=True),
    # Search Models
    "gpt-4o-mini-search-preview": create_model_metadata(
        provider="OpenAI",
        name="gpt-4o-mini-search-preview",
        icon="OpenAI",
        tool_calling=True,
        search=True,
        preview=True,
    ),
    "gpt-4o-search-preview": create_model_metadata(
        provider="OpenAI", name="gpt-4o-search-preview", icon="OpenAI", tool_calling=True, search=True, preview=True
    ),
    # Not Supported Models
    "computer-use-preview": create_model_metadata(
        provider="OpenAI", name="computer-use-preview", icon="OpenAI", not_supported=True, preview=True
    ),
    "gpt-4o-audio-preview": create_model_metadata(
        provider="OpenAI", name="gpt-4o-audio-preview", icon="OpenAI", not_supported=True, preview=True
    ),
    "gpt-4o-realtime-preview": create_model_metadata(
        provider="OpenAI", name="gpt-4o-realtime-preview", icon="OpenAI", not_supported=True, preview=True
    ),
    "gpt-4o-mini-audio-preview": create_model_metadata(
        provider="OpenAI", name="gpt-4o-mini-audio-preview", icon="OpenAI", not_supported=True, preview=True
    ),
    "gpt-4o-mini-realtime-preview": create_model_metadata(
        provider="OpenAI", name="gpt-4o-mini-realtime-preview", icon="OpenAI", not_supported=True, preview=True
    ),
    "o3-mini": create_model_metadata(
        provider="OpenAI", name="o3-mini", icon="OpenAI", reasoning=True, not_supported=True
    ),
    "o1-mini": create_model_metadata(
        provider="OpenAI", name="o1-mini", icon="OpenAI", reasoning=True, not_supported=True
    ),
}

OPENAI_MODEL_NAMES = [
    model
    for model, metadata in OPENAI_MODELS_DETAILED.items()
    if not metadata.get("reasoning", False)
    and not metadata.get("search", False)
    and not metadata.get("not_supported", False)
]

OPENAI_REASONING_MODEL_NAMES = [
    model
    for model, metadata in OPENAI_MODELS_DETAILED.items()
    if metadata.get("reasoning", False) and not metadata.get("not_supported", False)
]

OPENAI_SEARCH_MODEL_NAMES = [
    model
    for model, metadata in OPENAI_MODELS_DETAILED.items()
    if metadata.get("search", False) and not metadata.get("not_supported", False)
]

NOT_SUPPORTED_MODELS = [
    model for model, metadata in OPENAI_MODELS_DETAILED.items() if metadata.get("not_supported", False)
]

OPENAI_EMBEDDING_MODEL_NAMES = [
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
]

# Backwards compatibility
MODEL_NAMES = OPENAI_MODEL_NAMES
