from typing import Any, TypedDict


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
    default: bool  # Whether model is a default/recommended option (defaults to False)
    model_type: str  # Type of model (defaults to "llm" or "embeddings")


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
    default: bool = False,
    model_type: str = "llm",
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
        default=default,
        model_type=model_type,
    )


# Provider metadata configuration
# Defines the variables (credentials, URLs, etc.) required for each model provider
MODEL_PROVIDER_METADATA: dict[str, Any] = {
    "OpenAI": {
        "icon": "OpenAI",
        "variables": [
            {
                "variable_name": "API Key",
                "variable_key": "OPENAI_API_KEY",
                "description": "Your OpenAI API key",
                "required": True,
                "is_secret": True,
                "is_list": False,
                "options": [],
            }
        ],
        "api_docs_url": "https://platform.openai.com/docs/overview",
        "mapping": {
            "model_class": "ChatOpenAI",
            "model_param": "model",
            "api_key_param": "api_key",
        },
    },
    "Anthropic": {
        "icon": "Anthropic",
        "variables": [
            {
                "variable_name": "API Key",
                "variable_key": "ANTHROPIC_API_KEY",
                "description": "Your Anthropic API key",
                "required": True,
                "is_secret": True,
                "is_list": False,
                "options": [],
            }
        ],
        "api_docs_url": "https://console.anthropic.com/docs",
        "mapping": {
            "model_class": "ChatAnthropic",
            "model_param": "model",
            "api_key_param": "api_key",
        },
    },
    "Google Generative AI": {
        "icon": "GoogleGenerativeAI",
        "variables": [
            {
                "variable_name": "API Key",
                "variable_key": "GOOGLE_API_KEY",
                "description": "Your Google AI API key",
                "required": True,
                "is_secret": True,
                "is_list": False,
                "options": [],
            }
        ],
        "api_docs_url": "https://aistudio.google.com/app/apikey",
        "mapping": {
            "model_class": "ChatGoogleGenerativeAIFixed",
            "model_param": "model",
            "api_key_param": "google_api_key",
        },
    },
    "Ollama": {
        "icon": "Ollama",
        "variables": [
            {
                "variable_name": "Base URL",
                "variable_key": "OLLAMA_BASE_URL",
                "description": "Ollama server URL (default: http://localhost:11434)",
                "required": True,
                "is_secret": False,
                "is_list": False,
                "options": [],
            }
        ],
        "api_docs_url": "https://ollama.com/",
        "mapping": {
            "model_class": "ChatOllama",
            "model_param": "model",
            "base_url_param": "base_url",
        },
    },
    "IBM WatsonX": {
        "icon": "IBM",
        "variables": [
            {
                "variable_name": "API Key",
                "variable_key": "WATSONX_APIKEY",
                "description": "IBM WatsonX API key for authentication",
                "required": True,
                "is_secret": True,
                "is_list": False,
                "options": [],
            },
            {
                "variable_name": "Project ID",
                "variable_key": "WATSONX_PROJECT_ID",
                "description": "The project ID associated with your WatsonX instance",
                "required": True,
                "is_secret": False,
                "is_list": False,
                "options": [],
            },
            {
                "variable_name": "URL",
                "variable_key": "WATSONX_URL",
                "description": "WatsonX API endpoint URL for your region",
                "required": True,
                "is_secret": False,
                "is_list": False,
                "options": [
                    "https://us-south.ml.cloud.ibm.com",
                    "https://eu-de.ml.cloud.ibm.com",
                    "https://eu-gb.ml.cloud.ibm.com",
                    "https://au-syd.ml.cloud.ibm.com",
                    "https://jp-tok.ml.cloud.ibm.com",
                    "https://ca-tor.ml.cloud.ibm.com",
                ],
            },
        ],
        "api_docs_url": "https://www.ibm.com/products/watsonx",
        "mapping": {
            "model_class": "ChatWatsonx",
            "model_param": "model_id",
            "api_key_param": "apikey",
            "url_param": "url",
            "project_id_param": "project_id",
        },
    },
}


def get_provider_param_mapping(provider: str) -> dict[str, str]:
    """Get parameter mapping for a provider.

    Returns dict with keys like: model_class, model_param, api_key_param, etc.

    Args:
        provider: The provider name (e.g., "OpenAI", "Anthropic", "IBM WatsonX")

    Returns:
        Dict containing parameter mappings for the provider.
        Returns empty dict if provider is not found.
    """
    metadata = MODEL_PROVIDER_METADATA.get(provider, {})
    return metadata.get("mapping", {})
