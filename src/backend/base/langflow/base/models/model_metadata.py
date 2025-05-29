from typing import TypedDict


class ModelMetadata(TypedDict, total=False):
    """Simple model metadata structure."""

    provider: str  # Provider name (e.g., "anthropic", "groq", "openai")
    name: str  # Model name/ID
    icon: str  # Icon name for UI
    tool_calling: bool  # Whether model supports tool calling (defaults to False)
    reasoning: bool  # Reasoning models (defaults to False)
    search: bool  # Search models (defaults to False)
    preview: bool  # Whether model is in preview/beta (defaults to False)
    not_supported: bool  # Whether model is not supported or deprecated (defaults to False)
    deprecated: bool  # Whether model is deprecated (defaults to False)


def create_model_metadata(
    provider: str,
    name: str,
    icon: str,
    *,
    tool_calling: bool = False,
    reasoning: bool = False,
    search: bool = False,
    preview: bool = False,
    not_supported: bool = False,
    deprecated: bool = False,
) -> ModelMetadata:
    """Helper function to create ModelMetadata with explicit defaults."""
    return ModelMetadata(
        provider=provider,
        name=name,
        icon=icon,
        tool_calling=tool_calling,
        reasoning=reasoning,
        search=search,
        preview=preview,
        not_supported=not_supported,
        deprecated=deprecated,
    )
