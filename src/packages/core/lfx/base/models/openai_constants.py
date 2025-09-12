from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
OPENAI_MODELS_DETAILED = [
    # GPT-5 Series
    create_model_metadata(
        provider="OpenAI",
        name="gpt-5",
        icon="OpenAI",
        tool_calling=True,
        reasoning=True,
    ),
    create_model_metadata(
        provider="OpenAI",
        name="gpt-5-mini",
        icon="OpenAI",
        tool_calling=True,
        reasoning=True,
    ),
    create_model_metadata(
        provider="OpenAI",
        name="gpt-5-nano",
        icon="OpenAI",
        tool_calling=True,
        reasoning=True,
    ),
    create_model_metadata(
        provider="OpenAI",
        name="gpt-5-chat-latest",
        icon="OpenAI",
        tool_calling=False,
        reasoning=True,
    ),
    # Regular OpenAI Models
    create_model_metadata(provider="OpenAI", name="gpt-4o-mini", icon="OpenAI", tool_calling=True),
    create_model_metadata(provider="OpenAI", name="gpt-4o", icon="OpenAI", tool_calling=True),
    create_model_metadata(provider="OpenAI", name="gpt-4.1", icon="OpenAI", tool_calling=True),
    create_model_metadata(provider="OpenAI", name="gpt-4.1-mini", icon="OpenAI", tool_calling=True),
    create_model_metadata(provider="OpenAI", name="gpt-4.1-nano", icon="OpenAI", tool_calling=True),
    create_model_metadata(
        provider="OpenAI", name="gpt-4.5-preview", icon="OpenAI", tool_calling=True, preview=True, not_supported=True
    ),
    create_model_metadata(provider="OpenAI", name="gpt-4-turbo", icon="OpenAI", tool_calling=True),
    create_model_metadata(
        provider="OpenAI", name="gpt-4-turbo-preview", icon="OpenAI", tool_calling=True, preview=True
    ),
    create_model_metadata(provider="OpenAI", name="gpt-4", icon="OpenAI", tool_calling=True),
    create_model_metadata(provider="OpenAI", name="gpt-3.5-turbo", icon="OpenAI", tool_calling=True),
    # Reasoning Models
    create_model_metadata(provider="OpenAI", name="o1", icon="OpenAI", reasoning=True),
    create_model_metadata(provider="OpenAI", name="o1-mini", icon="OpenAI", reasoning=True, not_supported=True),
    create_model_metadata(provider="OpenAI", name="o1-pro", icon="OpenAI", reasoning=True, not_supported=True),
    create_model_metadata(provider="OpenAI", name="o3-mini", icon="OpenAI", reasoning=True),
    create_model_metadata(provider="OpenAI", name="o3", icon="OpenAI", reasoning=True),
    create_model_metadata(provider="OpenAI", name="o3-pro", icon="OpenAI", reasoning=True),
    create_model_metadata(provider="OpenAI", name="o4-mini", icon="OpenAI", reasoning=True),
    create_model_metadata(provider="OpenAI", name="o4-mini-high", icon="OpenAI", reasoning=True),
    # Search Models
    create_model_metadata(
        provider="OpenAI",
        name="gpt-4o-mini-search-preview",
        icon="OpenAI",
        tool_calling=True,
        search=True,
        preview=True,
    ),
    create_model_metadata(
        provider="OpenAI",
        name="gpt-4o-search-preview",
        icon="OpenAI",
        tool_calling=True,
        search=True,
        preview=True,
    ),
    # Not Supported Models
    create_model_metadata(
        provider="OpenAI", name="computer-use-preview", icon="OpenAI", not_supported=True, preview=True
    ),
    create_model_metadata(
        provider="OpenAI", name="gpt-4o-audio-preview", icon="OpenAI", not_supported=True, preview=True
    ),
    create_model_metadata(
        provider="OpenAI", name="gpt-4o-realtime-preview", icon="OpenAI", not_supported=True, preview=True
    ),
    create_model_metadata(
        provider="OpenAI", name="gpt-4o-mini-audio-preview", icon="OpenAI", not_supported=True, preview=True
    ),
    create_model_metadata(
        provider="OpenAI", name="gpt-4o-mini-realtime-preview", icon="OpenAI", not_supported=True, preview=True
    ),
]
OPENAI_CHAT_MODEL_NAMES = [
    metadata["name"]
    for metadata in OPENAI_MODELS_DETAILED
    if not metadata.get("not_supported", False)
    and not metadata.get("reasoning", False)
    and not metadata.get("search", False)
]

OPENAI_REASONING_MODEL_NAMES = [
    metadata["name"]
    for metadata in OPENAI_MODELS_DETAILED
    if metadata.get("reasoning", False) and not metadata.get("not_supported", False)
]

OPENAI_SEARCH_MODEL_NAMES = [
    metadata["name"]
    for metadata in OPENAI_MODELS_DETAILED
    if metadata.get("search", False) and not metadata.get("not_supported", False)
]

NOT_SUPPORTED_MODELS = [metadata["name"] for metadata in OPENAI_MODELS_DETAILED if metadata.get("not_supported", False)]

OPENAI_EMBEDDING_MODEL_NAMES = [
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
]

# Backwards compatibility
MODEL_NAMES = OPENAI_CHAT_MODEL_NAMES
OPENAI_MODEL_NAMES = OPENAI_CHAT_MODEL_NAMES
