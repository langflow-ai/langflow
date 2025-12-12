from typing import TypedDict


class ModelCost(TypedDict, total=False):
    """Cost information per million tokens."""

    input: float  # Cost per million input tokens
    output: float  # Cost per million output tokens
    reasoning: float  # Cost per million reasoning tokens (if applicable)
    cache_read: float  # Cost per million cached read tokens
    cache_write: float  # Cost per million cached write tokens
    input_audio: float  # Cost per million audio input tokens
    output_audio: float  # Cost per million audio output tokens


class ModelLimits(TypedDict, total=False):
    """Token limits for the model."""

    context: int  # Maximum context window size
    output: int  # Maximum output tokens


class ModelModalities(TypedDict, total=False):
    """Input/output modalities supported by the model."""

    input: list[str]  # Supported input types (e.g., ["text", "image", "audio"])
    output: list[str]  # Supported output types (e.g., ["text", "image"])


class ModelMetadata(TypedDict, total=False):
    """Model metadata structure with extended fields from models.dev API."""

    # Core identification
    provider: str  # Provider name (e.g., "Anthropic", "OpenAI")
    provider_id: str  # Provider ID from API (e.g., "anthropic", "openai")
    name: str  # Model name/ID
    display_name: str  # Human-readable model name
    icon: str  # Icon name for UI

    # Capabilities
    tool_calling: bool  # Whether model supports tool calling (defaults to False)
    reasoning: bool  # Reasoning models (defaults to False)
    search: bool  # Search models (defaults to False)
    structured_output: bool  # Whether model supports structured output
    temperature: bool  # Whether model supports temperature parameter
    attachment: bool  # Whether model supports file attachments

    # Status flags
    preview: bool  # Whether model is in preview/beta (defaults to False)
    not_supported: bool  # Whether model is not supported (defaults to False)
    deprecated: bool  # Whether model is deprecated (defaults to False)
    default: bool  # Whether model is a default/recommended option (defaults to False)
    open_weights: bool  # Whether model has open weights

    # Model classification
    model_type: str  # Type of model ("llm", "embeddings", "image", "audio", "video")

    # Extended metadata from models.dev
    cost: ModelCost  # Pricing information
    limits: ModelLimits  # Token limits
    modalities: ModelModalities  # Supported input/output modalities
    knowledge_cutoff: str  # Knowledge cutoff date (e.g., "2024-04")
    release_date: str  # Model release date
    last_updated: str  # Last update date

    # Provider metadata
    api_base: str  # Base API URL for the provider
    env_vars: list[str]  # Environment variables for API keys
    documentation_url: str  # Link to provider documentation


def create_model_metadata(
    provider: str,
    name: str,
    icon: str,
    *,
    provider_id: str | None = None,
    display_name: str | None = None,
    tool_calling: bool = False,
    reasoning: bool = False,
    search: bool = False,
    structured_output: bool = False,
    temperature: bool = True,
    attachment: bool = False,
    preview: bool = False,
    not_supported: bool = False,
    deprecated: bool = False,
    default: bool = False,
    open_weights: bool = False,
    model_type: str = "llm",
    cost: ModelCost | None = None,
    limits: ModelLimits | None = None,
    modalities: ModelModalities | None = None,
    knowledge_cutoff: str | None = None,
    release_date: str | None = None,
    last_updated: str | None = None,
    api_base: str | None = None,
    env_vars: list[str] | None = None,
    documentation_url: str | None = None,
) -> ModelMetadata:
    """Helper function to create ModelMetadata with explicit defaults."""
    metadata = ModelMetadata(
        provider=provider,
        name=name,
        icon=icon,
        tool_calling=tool_calling,
        reasoning=reasoning,
        search=search,
        structured_output=structured_output,
        temperature=temperature,
        attachment=attachment,
        preview=preview,
        not_supported=not_supported,
        deprecated=deprecated,
        default=default,
        open_weights=open_weights,
        model_type=model_type,
    )

    # Add optional fields if provided
    if provider_id is not None:
        metadata["provider_id"] = provider_id
    if display_name is not None:
        metadata["display_name"] = display_name
    if cost is not None:
        metadata["cost"] = cost
    if limits is not None:
        metadata["limits"] = limits
    if modalities is not None:
        metadata["modalities"] = modalities
    if knowledge_cutoff is not None:
        metadata["knowledge_cutoff"] = knowledge_cutoff
    if release_date is not None:
        metadata["release_date"] = release_date
    if last_updated is not None:
        metadata["last_updated"] = last_updated
    if api_base is not None:
        metadata["api_base"] = api_base
    if env_vars is not None:
        metadata["env_vars"] = env_vars
    if documentation_url is not None:
        metadata["documentation_url"] = documentation_url

    return metadata
