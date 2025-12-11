from .model_metadata import create_model_metadata

WATSONX_DEFAULT_LLM_MODELS = [
    create_model_metadata(
        provider="IBM Watsonx",
        name="ibm/granite-3-2b-instruct",
        icon="WatsonxAI",
        model_type="llm",
        default=True,
    ),
    create_model_metadata(
        provider="IBM Watsonx",
        name="ibm/granite-3-8b-instruct",
        icon="WatsonxAI",
        model_type="llm",
        default=True,
    ),
    create_model_metadata(
        provider="IBM Watsonx",
        name="ibm/granite-13b-instruct-v2",
        icon="WatsonxAI",
        model_type="llm",
        default=True,
    ),
]

WATSONX_DEFAULT_EMBEDDING_MODELS = [
    create_model_metadata(
        provider="IBM Watsonx",
        name="sentence-transformers/all-minilm-l12-v2",
        icon="WatsonxAI",
        model_type="embeddings",
        default=True,
    ),
    create_model_metadata(
        provider="IBM Watsonx",
        name="ibm/slate-125m-english-rtrvr-v2",
        icon="WatsonxAI",
        model_type="embeddings",
        default=True,
    ),
    create_model_metadata(
        provider="IBM Watsonx",
        name="ibm/slate-30m-english-rtrvr-v2",
        icon="WatsonxAI",
        model_type="embeddings",
        default=True,
    ),
    create_model_metadata(
        provider="IBM Watsonx",
        name="intfloat/multilingual-e5-large",
        icon="WatsonxAI",
        model_type="embeddings",
        default=True,
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
