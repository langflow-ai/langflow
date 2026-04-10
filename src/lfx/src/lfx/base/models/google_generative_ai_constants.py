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
        tool_calling=False,  # TODO: When Google GenAI has been upgraded, tool calling should be enabled for Gemini 3
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-3-pro-preview",
        icon="GoogleGenerativeAI",
        tool_calling=False,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-3-flash-preview",
        icon="GoogleGenerativeAI",
        tool_calling=False,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-3-pro-image-preview",
        icon="GoogleGenerativeAI",
        tool_calling=False,
        preview=True,
    ),
]

GOOGLE_GENERATIVE_AI_MODELS = [metadata["name"] for metadata in GOOGLE_GENERATIVE_AI_MODELS_DETAILED]

# Google Generative AI Embedding Models
# Embedding models as detailed metadata
GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS_DETAILED = [
    # Current supported embedding models
    create_model_metadata(
        provider="Google Generative AI",
        name="models/gemini-embedding-001",
        icon="GoogleGenerativeAI",
        model_type="embeddings",
        default=True,
    ),
    # Legacy/deprecated embedding models
    create_model_metadata(
        provider="Google Generative AI",
        name="models/text-embedding-004",
        icon="GoogleGenerativeAI",
        model_type="embeddings",
        deprecated=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="models/embedding-001",
        icon="GoogleGenerativeAI",
        model_type="embeddings",
        deprecated=True,
    ),
]

GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS = [metadata["name"] for metadata in GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS_DETAILED]
