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
#
# Variable attributes (top-level - for UI settings screen):
#   - variable_name: Display name for the variable
#   - variable_key: Environment variable key name
#   - description: Description shown in UI settings
#   - required: Whether the variable is required in the UI settings screen
#   - is_secret: Whether the variable contains sensitive data (will be encrypted)
#   - is_list: Whether the variable accepts multiple values
#   - options: List of predefined options for the variable
#   - langchain_param: The parameter name used when instantiating the LangChain class
#
# Variable attributes (component_metadata - for component inputs):
#   - mapping_field: The component input field name that this variable maps to
#   - required: Whether the variable is required in components (False = falls back to env var)
#   - advanced: Whether to show the variable in the advanced section of components
#   - info: Help text/description shown in the component input
#
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
                "langchain_param": "api_key",
                "component_metadata": {
                    "mapping_field": "api_key",
                    "required": False,
                    "advanced": True,
                    "info": "Falls back to OPENAI_API_KEY environment variable",
                },
            }
        ],
        "api_docs_url": "https://platform.openai.com/docs/overview",
        "mapping": {
            "model_class": "ChatOpenAI",
            "model_param": "model",
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
                "langchain_param": "api_key",
                "component_metadata": {
                    "mapping_field": "api_key",
                    "required": False,
                    "advanced": True,
                    "info": "Falls back to ANTHROPIC_API_KEY environment variable",
                },
            }
        ],
        "api_docs_url": "https://console.anthropic.com/docs",
        "mapping": {
            "model_class": "ChatAnthropic",
            "model_param": "model",
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
                "langchain_param": "google_api_key",
                "component_metadata": {
                    "mapping_field": "api_key",
                    "required": False,
                    "advanced": True,
                    "info": "Falls back to GOOGLE_API_KEY environment variable",
                },
            }
        ],
        "api_docs_url": "https://aistudio.google.com/app/apikey",
        "mapping": {
            "model_class": "ChatGoogleGenerativeAIFixed",
            "model_param": "model",
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
                "langchain_param": "base_url",
                "component_metadata": {
                    "mapping_field": "ollama_base_url",
                    "required": False,
                    "advanced": True,
                    "info": "Falls back to OLLAMA_BASE_URL environment variable",
                },
            }
        ],
        "api_docs_url": "https://ollama.com/",
        "mapping": {
            "model_class": "ChatOllama",
            "model_param": "model",
        },
    },
    "IBM WatsonX": {
        "icon": "IBM",
        "variables": [
            {
                "variable_name": "API Key",
                "variable_key": "WATSONX_APIKEY",
                "description": "IBM WatsonX API key",
                "required": True,
                "is_secret": True,
                "is_list": False,
                "options": [],
                "langchain_param": "apikey",
                "component_metadata": {
                    "mapping_field": "api_key",
                    "required": False,
                    "advanced": True,
                    "info": "Falls back to WATSONX_APIKEY environment variable",
                },
            },
            {
                "variable_name": "Project ID",
                "variable_key": "WATSONX_PROJECT_ID",
                "description": "WatsonX project ID",
                "required": True,
                "is_secret": False,
                "is_list": False,
                "options": [],
                "langchain_param": "project_id",
                "component_metadata": {
                    "mapping_field": "project_id",
                    "required": False,
                    "advanced": True,
                    "info": "Falls back to WATSONX_PROJECT_ID environment variable",
                },
            },
            {
                "variable_name": "URL",
                "variable_key": "WATSONX_URL",
                "description": "WatsonX API endpoint URL",
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
                "langchain_param": "url",
                "component_metadata": {
                    "mapping_field": "base_url_ibm_watsonx",
                    "required": False,
                    "advanced": True,
                    "info": "Falls back to WATSONX_URL environment variable",
                },
            },
        ],
        "api_docs_url": "https://www.ibm.com/products/watsonx",
        "mapping": {
            "model_class": "ChatWatsonx",
            "model_param": "model_id",
        },
    },
}


def get_provider_param_mapping(provider: str) -> dict[str, str]:
    """Get parameter mapping for a provider.

    Builds the mapping from the provider's variables using their langchain_param values.
    Returns dict with keys like: model_class, model_param, and dynamically built param mappings.

    Args:
        provider: The provider name (e.g., "OpenAI", "Anthropic", "IBM WatsonX")

    Returns:
        Dict containing parameter mappings for the provider.
        Returns empty dict if provider is not found.
    """
    metadata = MODEL_PROVIDER_METADATA.get(provider, {})
    if not metadata:
        return {}

    # Start with the base mapping (model_class, model_param)
    result = dict(metadata.get("mapping", {}))

    # Build param mappings from variables using component_metadata.mapping_field
    for var in metadata.get("variables", []):
        component_meta = var.get("component_metadata", {})
        mapping_field = component_meta.get("mapping_field")
        langchain_param = var.get("langchain_param")

        if mapping_field and langchain_param:
            # Create the param key based on the mapping_field type
            if "api_key" in mapping_field:
                result["api_key_param"] = langchain_param
            elif "url" in mapping_field.lower() or "base_url" in mapping_field.lower():
                # Distinguish between different URL types
                if "ollama" in mapping_field.lower():
                    result["base_url_param"] = langchain_param
                elif "watsonx" in mapping_field.lower() or provider == "IBM WatsonX":
                    result["url_param"] = langchain_param
                else:
                    result["base_url_param"] = langchain_param
            elif "project_id" in mapping_field:
                result["project_id_param"] = langchain_param

    return result
