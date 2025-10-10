from .model_metadata import create_model_metadata

ANTHROPIC_MODELS_DETAILED = [
    # Tool calling supported models
    create_model_metadata(provider="Anthropic", name="claude-sonnet-4-5-20250929", icon="Anthropic", tool_calling=True),
    create_model_metadata(provider="Anthropic", name="claude-opus-4-1-20250805", icon="Anthropic", tool_calling=True),
    create_model_metadata(provider="Anthropic", name="claude-opus-4-20250514", icon="Anthropic", tool_calling=True),
    create_model_metadata(provider="Anthropic", name="claude-sonnet-4-20250514", icon="Anthropic", tool_calling=True),
    create_model_metadata(provider="Anthropic", name="claude-3-7-sonnet-latest", icon="Anthropic", tool_calling=True),
    create_model_metadata(provider="Anthropic", name="claude-3-5-sonnet-latest", icon="Anthropic", tool_calling=True),
    create_model_metadata(provider="Anthropic", name="claude-3-5-haiku-latest", icon="Anthropic", tool_calling=True),
    create_model_metadata(provider="Anthropic", name="claude-3-opus-latest", icon="Anthropic", tool_calling=True),
    create_model_metadata(
        provider="Anthropic", name="claude-3-sonnet-20240229", icon="Anthropic", tool_calling=True, deprecated=True
    ),
    # Tool calling unsupported models
    create_model_metadata(provider="Anthropic", name="claude-2.1", icon="Anthropic", tool_calling=False),
    create_model_metadata(provider="Anthropic", name="claude-2.0", icon="Anthropic", tool_calling=False),
    # Deprecated models
    create_model_metadata(
        provider="Anthropic", name="claude-3-5-sonnet-20240620", icon="Anthropic", tool_calling=True, deprecated=True
    ),
    create_model_metadata(
        provider="Anthropic", name="claude-3-5-sonnet-20241022", icon="Anthropic", tool_calling=True, deprecated=True
    ),
    create_model_metadata(
        provider="Anthropic", name="claude-3-5-haiku-20241022", icon="Anthropic", tool_calling=True, deprecated=True
    ),
    create_model_metadata(
        provider="Anthropic", name="claude-3-haiku-20240307", icon="Anthropic", tool_calling=True, deprecated=True
    ),
]

ANTHROPIC_MODELS = [
    metadata["name"]
    for metadata in ANTHROPIC_MODELS_DETAILED
    if not metadata.get("deprecated", False) and metadata.get("tool_calling", False)
]

TOOL_CALLING_SUPPORTED_ANTHROPIC_MODELS = [
    metadata["name"] for metadata in ANTHROPIC_MODELS_DETAILED if metadata.get("tool_calling", False)
]

TOOL_CALLING_UNSUPPORTED_ANTHROPIC_MODELS = [
    metadata["name"] for metadata in ANTHROPIC_MODELS_DETAILED if not metadata.get("tool_calling", False)
]

DEPRECATED_MODELS = [metadata["name"] for metadata in ANTHROPIC_MODELS_DETAILED if metadata.get("deprecated", False)]


DEFAULT_ANTHROPIC_API_URL = "https://api.anthropic.com"
