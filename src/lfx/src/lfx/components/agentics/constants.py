"""Constants and configuration values for Agentics components."""

from __future__ import annotations

# Default URLs
DEFAULT_OLLAMA_URL = "http://localhost:11434"

# Provider names
PROVIDER_IBM_WATSONX = "IBM WatsonX"
PROVIDER_GOOGLE = "Google Generative AI"
PROVIDER_OPENAI = "OpenAI"
PROVIDER_ANTHROPIC = "Anthropic"
PROVIDER_OLLAMA = "Ollama"

SUPPORTED_PROVIDERS = [
    PROVIDER_IBM_WATSONX,
    PROVIDER_GOOGLE,
    PROVIDER_OPENAI,
    PROVIDER_ANTHROPIC,
    PROVIDER_OLLAMA,
]

# LLM model prefixes by provider
LLM_MODEL_PREFIXES = {
    PROVIDER_IBM_WATSONX: "watsonx/",
    PROVIDER_GOOGLE: "gemini/",
    PROVIDER_OPENAI: "openai/",
    PROVIDER_ANTHROPIC: "anthropic/",
    PROVIDER_OLLAMA: "ollama/",
}

# IBM WatsonX default parameters
WATSONX_DEFAULT_TEMPERATURE = 0
WATSONX_DEFAULT_MAX_TOKENS = 4000
WATSONX_DEFAULT_MAX_INPUT_TOKENS = 100000

# DataFrame operation types
OPERATION_MERGE = "merge"
OPERATION_COMPOSE = "compose"
OPERATION_CONCATENATE = "concatenate"

DATAFRAME_OPERATIONS = [OPERATION_MERGE, OPERATION_COMPOSE, OPERATION_CONCATENATE]

# Transduction types
TRANSDUCTION_AMAP = "amap"
TRANSDUCTION_AREDUCE = "areduce"
TRANSDUCTION_GENERATE = "generate"

TRANSDUCTION_TYPES = [TRANSDUCTION_AMAP, TRANSDUCTION_AREDUCE, TRANSDUCTION_GENERATE]

# Error messages for user feedback
ERROR_AGENTICS_NOT_INSTALLED = (
    "Agentics-py is not installed. Please install it with `uv pip install agentics-py==0.3.1`."
)
ERROR_API_KEY_REQUIRED = "{provider} API key is required. Please configure it in your settings or provide it directly."
ERROR_UNSUPPORTED_PROVIDER = (
    f"Unsupported provider: {{provider}}. Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
)
ERROR_UNSUPPORTED_OPERATION = (
    "Unsupported operation type: {operation_type}. Valid operations: merge, compose, concatenate."
)
ERROR_MODEL_NOT_SELECTED = "No model selected. Please select a language model from the available options."
ERROR_INPUT_SCHEMA_REQUIRED = "BOTH Input DataFrame AND Output Schema inputs should be provided."
