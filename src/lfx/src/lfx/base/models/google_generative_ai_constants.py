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
        tool_calling=True,
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
        tool_calling=True,
        deprecated=True,
    ),
    # GEMINI 3.0 (preview)
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-3.1-pro-preview",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-3-pro-preview",
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
        name="gemini-3-pro-image-preview",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
]

GOOGLE_GENERATIVE_AI_MODELS = [metadata["name"] for metadata in GOOGLE_GENERATIVE_AI_MODELS_DETAILED]

# Google Generative AI Embedding Models
GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS = [
    "models/text-embedding-004",
    "models/embedding-001",
]

# Embedding models as detailed metadata
GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS_DETAILED = [
    create_model_metadata(
        provider="Google Generative AI",
        name=name,
        icon="GoogleGenerativeAI",
        model_type="embeddings",
    )
    for name in GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS
]
