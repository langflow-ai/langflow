from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
OLLAMA_MODELS_DETAILED = [
    # Tool Calling Models
    create_model_metadata(
        provider="Ollama",
        name="llama3.3",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="qwq",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="llama3.2",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="llama3.1",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="mistral",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="qwen2",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="qwen2.5",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="qwen2.5-coder",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="mistral-nemo",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="mixtral",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="command-r",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="command-r-plus",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="mistral-large",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="smollm2",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="hermes3",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="athene-v2",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="mistral-small",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="nemotron-mini",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="nemotron",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="llama3-groq-tool-use",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="granite3-dense",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="granite3.1-dense",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="aya-expanse",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="granite3-moe",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="firefunction-v2",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="cogito",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="gpt-oss:20b",
        icon="Ollama",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Ollama",
        name="qwen3-vl:4b",
        icon="Ollama",
        tool_calling=True,
    ),
]

# Filter lists based on metadata properties
OLLAMA_TOOL_MODELS_BASE = [
    metadata["name"]
    for metadata in OLLAMA_MODELS_DETAILED
    if metadata.get("tool_calling", False) and not metadata.get("not_supported", False)
]

# Embedding models - following OpenAI's pattern of keeping these as a simple list
# https://ollama.com/search?c=embedding
OLLAMA_EMBEDDING_MODELS = [
    "nomic-embed-text",
    "mxbai-embed-large",
    "snowflake-arctic-embed",
    "all-minilm",
    "bge-m3",
    "bge-large",
    "paraphrase-multilingual",
    "granite-embedding",
    "jina-embeddings-v2-base-en",
]

# Embedding models as detailed metadata
OLLAMA_EMBEDDING_MODELS_DETAILED = [
    create_model_metadata(
        provider="Ollama",
        name=name,
        icon="Ollama",
        model_type="embeddings",
    )
    for name in OLLAMA_EMBEDDING_MODELS
]

# Connection URLs
URL_LIST = [
    "http://localhost:11434",
    "http://host.docker.internal:11434",
    "http://127.0.0.1:11434",
    "http://0.0.0.0:11434",
]

# Backwards compatibility
OLLAMA_MODEL_NAMES = OLLAMA_TOOL_MODELS_BASE
DEFAULT_OLLAMA_API_URL = "https://ollama.com"
