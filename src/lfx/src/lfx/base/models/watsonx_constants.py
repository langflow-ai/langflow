from .model_metadata import create_model_metadata

WATSONX_DEFAULT_LLM_MODELS = [
    create_model_metadata(
        provider="IBM WatsonX",
        name="ibm/granite-8b-code-instruct",
        icon="IBM",
        model_type="llm",
        tool_calling=True,
        deprecated=True,
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="ibm/granite-guardian-3-8b",
        icon="IBM",
        model_type="llm",
        tool_calling=False,
        deprecated=True,
    ),
]

# Marked deprecated: not natively supported by the Knowledge Base ingestion
# flow; hidden from the embedding model picker until support is added.
WATSONX_DEFAULT_EMBEDDING_MODELS = [
    create_model_metadata(
        provider="IBM WatsonX",
        name="sentence-transformers/all-minilm-l12-v2",
        icon="IBM",
        model_type="embeddings",
        tool_calling=True,
        default=True,
        deprecated=True,
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="ibm/slate-125m-english-rtrvr-v2",
        icon="IBM",
        model_type="embeddings",
        tool_calling=True,
        default=True,
        deprecated=True,
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="ibm/slate-30m-english-rtrvr-v2",
        icon="IBM",
        model_type="embeddings",
        tool_calling=True,
        default=True,
        deprecated=True,
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="intfloat/multilingual-e5-large",
        icon="IBM",
        model_type="embeddings",
        tool_calling=True,
        default=True,
        deprecated=True,
    ),
]


WATSONX_EMBEDDING_MODELS_DETAILED = WATSONX_DEFAULT_EMBEDDING_MODELS
# Combined list for all watsonx models
WATSONX_MODELS_DETAILED = WATSONX_DEFAULT_LLM_MODELS + WATSONX_DEFAULT_EMBEDDING_MODELS

WATSONX_EMBEDDING_MODEL_NAMES = [metadata["name"] for metadata in WATSONX_DEFAULT_EMBEDDING_MODELS]

IBM_WATSONX_URLS = [
    "https://us-south.ml.cloud.ibm.com",
    "https://eu-de.ml.cloud.ibm.com",
    "https://eu-gb.ml.cloud.ibm.com",
    "https://au-syd.ml.cloud.ibm.com",
    "https://jp-tok.ml.cloud.ibm.com",
    "https://ca-tor.ml.cloud.ibm.com",
]
