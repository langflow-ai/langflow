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
# https://ollama.com/search?c=tools
OLLAMA_TOOL_MODELS_BASE = [
    "llama3.3",
    "qwq",
    "llama3.2",
    "llama3.1",
    "mistral",
    "qwen2",
    "qwen2.5",
    "qwen2.5-coder",
    "mistral-nemo",
    "mixtral",
    "command-r",
    "command-r-plus",
    "mistral-large",
    "smollm2",
    "hermes3",
    "athene-v2",
    "mistral-small",
    "nemotron-mini",
    "nemotron",
    "llama3-groq-tool-use",
    "granite3-dense",
    "granite3.1-dense",
    "aya-expanse",
    "granite3-moe",
    "firefunction-v2",
    "cogito",
]


URL_LIST = [
    "http://localhost:11434",
    "http://host.docker.internal:11434",
    "http://127.0.0.1:11434",
    "http://0.0.0.0:11434",
]


DEFAULT_OLLAMA_API_URL = "https://ollama.com"
