from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
GOOGLE_GENERATIVE_AI_MODELS_DETAILED = [
    # GEMINI 2.5 (latest, most powerful and flash variants)
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.5-pro-preview-05-06", icon="GoogleGenerativeAI", tool_calling=True, preview=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.5-flash-preview-05-20", icon="GoogleGenerativeAI", tool_calling=True, preview=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.5-flash-preview-native-audio-dialog", icon="GoogleGenerativeAI", tool_calling=True, preview=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.5-flash-exp-native-audio-thinking-dialog", icon="GoogleGenerativeAI", tool_calling=True, preview=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.5-flash-preview-tts", icon="GoogleGenerativeAI", tool_calling=True, preview=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.5-pro-preview-tts", icon="GoogleGenerativeAI", tool_calling=True, preview=True
    ),
    # GEMINI 2.0
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.0-flash", icon="GoogleGenerativeAI", tool_calling=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.0-flash-preview-image-generation", icon="GoogleGenerativeAI", tool_calling=True, preview=True
    ),
    create_model_metadata(
        provider="Google Generative AI", name="gemini-2.0-flash-lite", icon="GoogleGenerativeAI", tool_calling=True
    ),
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
    # EMBEDDING
    create_model_metadata(
        provider="Google Generative AI", name="gemini-embedding-exp", icon="GoogleGenerativeAI", tool_calling=True, preview=True
    ),
    # AQA
    create_model_metadata(
        provider="Google Generative AI", name="models/aqa", icon="GoogleGenerativeAI", tool_calling=True, preview=True
    ),
]

GOOGLE_GENERATIVE_AI_MODELS = [metadata["name"] for metadata in GOOGLE_GENERATIVE_AI_MODELS_DETAILED]

