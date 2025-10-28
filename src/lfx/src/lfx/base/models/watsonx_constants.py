from .model_metadata import create_model_metadata

# Granite Embedding models
WATSONX_EMBEDDING_MODELS_DETAILED = [
    create_model_metadata(provider="IBM Watsonx", name="ibm/granite-embedding-125m-english", icon="IBMWatsonx"),
    create_model_metadata(provider="IBM Watsonx", name="ibm/granite-embedding-278m-multilingual", icon="IBMWatsonx"),
    create_model_metadata(provider="IBM Watsonx", name="ibm/granite-embedding-30m-english", icon="IBMWatsonx"),
    create_model_metadata(provider="IBM Watsonx", name="ibm/granite-embedding-107m-multilingual", icon="IBMWatsonx"),
    create_model_metadata(provider="IBM Watsonx", name="ibm/granite-embedding-30m-sparse", icon="IBMWatsonx"),
]

WATSONX_EMBEDDING_MODEL_NAMES = [metadata["name"] for metadata in WATSONX_EMBEDDING_MODELS_DETAILED]
