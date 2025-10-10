from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
GOOGLE_GENERATIVE_AI_MODELS_DETAILED = [
    # GEMINI 1.5
    create_model_metadata(
        provider="Google Generative AI", name="gemini-1.5-pro", icon="GoogleGenerativeAI", tool_calling=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-1.5-flash", icon="GoogleGenerativeAI", tool_calling=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-1.5-flash-8b", icon="GoogleGenerativeAI", tool_calling=True
    ),
    # GEMINI 2.5
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.5-pro", icon="GoogleGenerativeAI", tool_calling=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.5-flash", icon="GoogleGenerativeAI", tool_calling=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.5-flash-lite", icon="GoogleGenerativeAI", tool_calling=True
    ),
    # GEMINI 2.0
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.0-flash-lite", icon="GoogleGenerativeAI", tool_calling=True
    ),
    # PREVIEW
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.0-flash",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-exp-1206",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.0-flash-thinking-exp-01-21",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(
        provider="Google Generative AI",
        name="learnlm-1.5-pro-experimental",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True,
    ),
    # GEMMA
    create_model_metadata(
        provider="Google Generative AI", name="gemma-2-2b", icon="GoogleGenerativeAI", tool_calling=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemma-2-9b", icon="GoogleGenerativeAI", tool_calling=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemma-2-27b", icon="GoogleGenerativeAI", tool_calling=True
    ),
]

GOOGLE_GENERATIVE_AI_MODELS = [metadata["name"] for metadata in GOOGLE_GENERATIVE_AI_MODELS_DETAILED]
