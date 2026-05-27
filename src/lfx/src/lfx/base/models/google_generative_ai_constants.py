from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth

GOOGLE_GENERATIVE_AI_MODELS_DETAILED = [
    # GEMINI 2.5 (stable - recommended)
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.5-flash",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        default=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.5-pro",
        icon="GoogleGenerativeAI",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.5-flash-lite",
        icon="GoogleGenerativeAI",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.5-flash-preview-09-2025",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.5-flash-lite-preview-09-2025",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.5-flash-image",
        icon="GoogleGenerativeAI",
        # Image-output Gemini models can't run with tools per Google's API
        # (modalities.output includes "image"). Setting this to True caused
        # the Agent picker to surface image-generation models alongside
        # text models.
        tool_calling=False,
    ),
    # GEMINI 1.5 (legacy - long out of rotation). These names live in the
    # static list specifically so the models.dev override preserves the
    # deprecation flag by name match; the 900-day age heuristic alone wouldn't
    # catch the more recent 1.5 builds (gemini-1.5-flash-8b is only ~600d).
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-1.5-pro",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        deprecated=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-1.5-flash",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        deprecated=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-1.5-flash-8b",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        deprecated=True,
    ),
    # GEMINI 2.0 (legacy - scheduled deprecation)
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.0-flash",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        deprecated=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.0-flash-lite",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        deprecated=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.0-flash-preview-image-generation",
        icon="GoogleGenerativeAI",
        # Image-generation model — no tool calling support.
        tool_calling=False,
        deprecated=True,
    ),
    # GEMINI 3 (preview)
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-3.1-pro-preview",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-3-flash-preview",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-3.1-flash-lite-preview",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-3-pro-image-preview",
        icon="GoogleGenerativeAI",
        # Image-output preview — no tool calling support.
        tool_calling=False,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-3.1-flash-image-preview",
        icon="GoogleGenerativeAI",
        # Image-output preview — no tool calling support.
        tool_calling=False,
        preview=True,
    ),
]

GOOGLE_GENERATIVE_AI_MODELS = [metadata["name"] for metadata in GOOGLE_GENERATIVE_AI_MODELS_DETAILED]

# Google Generative AI Embedding Models
GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS = [
    "models/gemini-embedding-001",
    "models/text-embedding-004",
    "models/embedding-001",
]

# Embedding models as detailed metadata.
# `text-embedding-004` and `embedding-001` are marked deprecated because they
# are no longer served by the Google Generative AI v1beta endpoint used by KB
# ingestion (404). `gemini-embedding-001` is the current supported model.
_GOOGLE_DEPRECATED_EMBEDDING_MODELS = {
    "models/text-embedding-004",
    "models/embedding-001",
}

GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS_DETAILED = [
    create_model_metadata(
        provider="Google Generative AI",
        name=name,
        icon="GoogleGenerativeAI",
        model_type="embeddings",
        default=True,
        deprecated=name in _GOOGLE_DEPRECATED_EMBEDDING_MODELS,
    )
    for name in GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS
]
