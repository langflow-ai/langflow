from .model_metadata import create_model_metadata

ANTHROPIC_MODELS_DETAILED = {
    # Tool calling supported models
    "claude-opus-4-20250514": create_model_metadata(
        provider="Anthropic", name="claude-opus-4-20250514", icon="Anthropic", tool_calling=True
    ),
    "claude-sonnet-4-20250514": create_model_metadata(
        provider="Anthropic", name="claude-sonnet-4-20250514", icon="Anthropic", tool_calling=True
    ),
    "claude-3-7-sonnet-latest": create_model_metadata(
        provider="Anthropic", name="claude-3-7-sonnet-latest", icon="Anthropic", tool_calling=True
    ),
    "claude-3-5-sonnet-latest": create_model_metadata(
        provider="Anthropic", name="claude-3-5-sonnet-latest", icon="Anthropic", tool_calling=True
    ),
    "claude-3-5-haiku-latest": create_model_metadata(
        provider="Anthropic", name="claude-3-5-haiku-latest", icon="Anthropic", tool_calling=True
    ),
    "claude-3-opus-latest": create_model_metadata(
        provider="Anthropic", name="claude-3-opus-latest", icon="Anthropic", tool_calling=True
    ),
    "claude-3-sonnet-20240229": create_model_metadata(
        provider="Anthropic", name="claude-3-sonnet-20240229", icon="Anthropic", tool_calling=True
    ),
    # Tool calling unsupported models
    "claude-2.1": create_model_metadata(provider="Anthropic", name="claude-2.1", icon="Anthropic", tool_calling=False),
    "claude-2.0": create_model_metadata(provider="Anthropic", name="claude-2.0", icon="Anthropic", tool_calling=False),
    # Deprecated models
    "claude-3-5-sonnet-20240620": create_model_metadata(
        provider="Anthropic", name="claude-3-5-sonnet-20240620", icon="Anthropic", tool_calling=True, deprecated=True
    ),
    "claude-3-5-sonnet-20241022": create_model_metadata(
        provider="Anthropic", name="claude-3-5-sonnet-20241022", icon="Anthropic", tool_calling=True, deprecated=True
    ),
    "claude-3-5-haiku-20241022": create_model_metadata(
        provider="Anthropic", name="claude-3-5-haiku-20241022", icon="Anthropic", tool_calling=True, deprecated=True
    ),
    "claude-3-haiku-20240307": create_model_metadata(
        provider="Anthropic", name="claude-3-haiku-20240307", icon="Anthropic", tool_calling=True, deprecated=True
    ),
}

ANTHROPIC_MODELS = [
    model_name
    for model_name, metadata in ANTHROPIC_MODELS_DETAILED.items()
    if not metadata.get("deprecated", False) and metadata.get("tool_calling", False)
]

TOOL_CALLING_SUPPORTED_ANTHROPIC_MODELS = [
    model_name for model_name, metadata in ANTHROPIC_MODELS_DETAILED.items() if metadata.get("tool_calling", False)
]

TOOL_CALLING_UNSUPPORTED_ANTHROPIC_MODELS = [
    model_name for model_name, metadata in ANTHROPIC_MODELS_DETAILED.items() if not metadata.get("tool_calling", False)
]

DEPRECATED_MODELS = [
    model_name for model_name, metadata in ANTHROPIC_MODELS_DETAILED.items() if metadata.get("deprecated", False)
]


DEFAULT_ANTHROPIC_API_URL = "https://api.anthropic.com"
