from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
WATSONX_MODELS_DETAILED = [
    # Granite Embedding Models
    create_model_metadata(
        provider="IBM Watsonx",
        name="ibm/granite-embedding-125m-english",
        icon="IBMWatsonx",
        model_type="embeddings",
        default=True,
    ),
    create_model_metadata(
        provider="IBM Watsonx",
        name="ibm/granite-embedding-278m-multilingual",
        icon="IBMWatsonx",
        model_type="embeddings",
        default=True,
    ),
    create_model_metadata(
        provider="IBM Watsonx",
        name="ibm/granite-embedding-30m-english",
        icon="IBMWatsonx",
        model_type="embeddings",
    ),
    create_model_metadata(
        provider="IBM Watsonx",
        name="ibm/granite-embedding-107m-multilingual",
        icon="IBMWatsonx",
        model_type="embeddings",
    ),
    create_model_metadata(
        provider="IBM Watsonx",
        name="ibm/granite-embedding-30m-sparse",
        icon="IBMWatsonx",
        model_type="embeddings",
    ),
]

# Filter lists based on metadata properties
WATSONX_EMBEDDING_MODEL_NAMES = [
    metadata["name"] for metadata in WATSONX_MODELS_DETAILED if not metadata.get("not_supported", False)
]

# Backwards compatibility
WATSONX_EMBEDDING_MODELS_DETAILED = WATSONX_MODELS_DETAILED

IBM_WATSONX_URLS = [
    "https://us-south.ml.cloud.ibm.com",
    "https://eu-de.ml.cloud.ibm.com",
    "https://eu-gb.ml.cloud.ibm.com",
    "https://au-syd.ml.cloud.ibm.com",
    "https://jp-tok.ml.cloud.ibm.com",
    "https://ca-tor.ml.cloud.ibm.com",
]
