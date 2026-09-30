from .model_metadata import create_model_metadata

# Pre-credential seed catalog. Once the provider is configured,
# ``fetch_live_watsonx_models`` replaces these entries with the live
# ``/ml/v1/foundation_model_specs`` listing (which already excludes
# withdrawn models), so this list only needs to track the commonly
# available watsonx.ai models. ``deprecated=True`` is reserved for models
# IBM has withdrawn from the catalog — kept here so legacy flows that
# reference them still resolve; the UI hides them behind the
# "Show deprecated" toggle.
WATSONX_DEFAULT_LLM_MODELS = [
    create_model_metadata(
        provider="IBM WatsonX",
        name="ibm/granite-4-h-small",
        icon="IBM",
        model_type="llm",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="meta-llama/llama-3-3-70b-instruct",
        icon="IBM",
        model_type="llm",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="mistral-large-2512",
        icon="IBM",
        model_type="llm",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="meta-llama/llama-4-maverick-17b-128e-instruct-fp8",
        icon="IBM",
        model_type="llm",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="mistralai/mistral-medium-2505",
        icon="IBM",
        model_type="llm",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="mistralai/mistral-small-3-1-24b-instruct-2503",
        icon="IBM",
        model_type="llm",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="openai/gpt-oss-120b",
        icon="IBM",
        model_type="llm",
        tool_calling=True,
    ),
    # Guardian is a safety-classification model; it does not support tools.
    create_model_metadata(
        provider="IBM WatsonX",
        name="ibm/granite-guardian-3-8b",
        icon="IBM",
        model_type="llm",
        tool_calling=False,
    ),
    # Withdrawn from IBM's chat catalog.
    create_model_metadata(
        provider="IBM WatsonX",
        name="ibm/granite-8b-code-instruct",
        icon="IBM",
        model_type="llm",
        tool_calling=True,
        deprecated=True,
    ),
]

WATSONX_DEFAULT_EMBEDDING_MODELS = [
    create_model_metadata(
        provider="IBM WatsonX",
        name="ibm/granite-embedding-278m-multilingual",
        icon="IBM",
        model_type="embeddings",
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="ibm/slate-125m-english-rtrvr-v2",
        icon="IBM",
        model_type="embeddings",
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="ibm/slate-30m-english-rtrvr-v2",
        icon="IBM",
        model_type="embeddings",
    ),
    create_model_metadata(
        provider="IBM WatsonX",
        name="intfloat/multilingual-e5-large",
        icon="IBM",
        model_type="embeddings",
    ),
    # Withdrawn from IBM's embedding catalog.
    create_model_metadata(
        provider="IBM WatsonX",
        name="sentence-transformers/all-minilm-l12-v2",
        icon="IBM",
        model_type="embeddings",
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
