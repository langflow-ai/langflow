from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
GOOGLE_GENERATIVE_AI_MODELS_DETAILED = {
    # GEMINI 1.5
    "gemini-1.5-pro": create_model_metadata(
        provider="Google Generative AI",
        name="gemini-1.5-pro",
        icon="GoogleGenerativeAI",
        tool_calling=True
    ),
    "gemini-1.5-flash": create_model_metadata(
        provider="Google Generative AI",
        name="gemini-1.5-flash",
        icon="GoogleGenerativeAI",
        tool_calling=True
    ),
    "gemini-1.5-flash-8b": create_model_metadata(
        provider="Google Generative AI",
        name="gemini-1.5-flash-8b",
        icon="GoogleGenerativeAI",
        tool_calling=True
    ),
    
    # PREVIEW
    "gemini-2.0-flash": create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.0-flash",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True
    ),
    "gemini-exp-1206": create_model_metadata(
        provider="Google Generative AI",
        name="gemini-exp-1206",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True
    ),
    "gemini-2.0-flash-thinking-exp-01-21": create_model_metadata(
        provider="Google Generative AI",
        name="gemini-2.0-flash-thinking-exp-01-21",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True
    ),
    "learnlm-1.5-pro-experimental": create_model_metadata(
        provider="Google Generative AI",
        name="learnlm-1.5-pro-experimental",
        icon="GoogleGenerativeAI",
        tool_calling=True,
        preview=True
    ),
    
    # GEMMA
    "gemma-2-2b": create_model_metadata(
        provider="Google Generative AI",
        name="gemma-2-2b",
        icon="GoogleGenerativeAI",
        tool_calling=True
    ),
    "gemma-2-9b": create_model_metadata(
        provider="Google Generative AI",
        name="gemma-2-9b",
        icon="GoogleGenerativeAI",
        tool_calling=True
    ),
    "gemma-2-27b": create_model_metadata(
        provider="Google Generative AI",
        name="gemma-2-27b",
        icon="GoogleGenerativeAI",
        tool_calling=True
    ),
}

GOOGLE_GENERATIVE_AI_MODELS = list(GOOGLE_GENERATIVE_AI_MODELS_DETAILED.keys())
