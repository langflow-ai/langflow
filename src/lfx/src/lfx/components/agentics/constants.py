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

AGENTICS_DOCS_URL = "https://docs.langflow.org/bundles-agentics"

# Error messages for user feedback
# No agentics-py release is co-installable with lfx: current releases pin langchain-core<1.0
# (via langchain-huggingface) and crewai>=0.140 pins json-repair/tomli below lfx's floors. The
# message must not tell users to install it: `pip install agentics-py` downgrades langchain-core
# in place and breaks Langflow.
ERROR_AGENTICS_NOT_INSTALLED = (
    "The Agentics components are deprecated and can't run in this version of Langflow. "
    "They need the agentics-py SDK, and no agentics-py release is compatible with Langflow's dependencies. "
    "Don't install it into this environment with `pip install agentics-py` or `uv pip install agentics-py`: "
    "it downgrades langchain-core and breaks Langflow. "
    f"For details, see {AGENTICS_DOCS_URL}."
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
