from .model_metadata import create_model_metadata

# Unified model metadata
#
# NOTE: This file serves as a FALLBACK when the dynamic model discovery system
# (groq_model_discovery.py) cannot fetch fresh data from the Groq API.
#
# The dynamic system is the PRIMARY source and will:
# - Fetch available models directly from Groq API
# - Test each model for tool calling support automatically
# - Cache results for 24 hours
# - Always provide up-to-date model lists
#
# This fallback list should contain:
# - Minimal set of stable production models
# - Deprecated models for backwards compatibility
# - Non-LLM models (audio, TTS) marked as not_supported
#
# Last manually updated: 2025-01-06
#
GROQ_MODELS_DETAILED = [
    # ===== FALLBACK PRODUCTION MODELS =====
    # These are stable models that are very unlikely to be removed
    create_model_metadata(provider="Groq", name="llama-3.1-8b-instant", icon="Groq", tool_calling=True),
    create_model_metadata(provider="Groq", name="llama-3.3-70b-versatile", icon="Groq", tool_calling=True),
    # ===== DEPRECATED MODELS =====
    # Keep these for backwards compatibility - users may have flows using them
    # These will appear in the list but show as deprecated in the UI
    create_model_metadata(  # Google - Removed
        provider="Groq", name="gemma2-9b-it", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Google
        provider="Groq", name="gemma-7b-it", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Meta - Removed
        provider="Groq", name="llama3-70b-8192", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Meta - Removed
        provider="Groq", name="llama3-8b-8192", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Meta - Removed, replaced by llama-guard-4-12b
        provider="Groq", name="llama-guard-3-8b", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Meta - Removed
        provider="Groq", name="llama-3.2-1b-preview", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Meta - Removed
        provider="Groq", name="llama-3.2-3b-preview", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Meta - Removed
        provider="Groq", name="llama-3.2-11b-vision-preview", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Meta - Removed
        provider="Groq", name="llama-3.2-90b-vision-preview", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Meta - Removed
        provider="Groq", name="llama-3.3-70b-specdec", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Alibaba - Removed, replaced by qwen/qwen3-32b
        provider="Groq", name="qwen-qwq-32b", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Alibaba - Removed
        provider="Groq", name="qwen-2.5-coder-32b", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Alibaba - Removed
        provider="Groq", name="qwen-2.5-32b", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # DeepSeek - Removed
        provider="Groq", name="deepseek-r1-distill-qwen-32b", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # DeepSeek - Removed
        provider="Groq", name="deepseek-r1-distill-llama-70b", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Groq
        provider="Groq", name="llama3-groq-70b-8192-tool-use-preview", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Groq
        provider="Groq", name="llama3-groq-8b-8192-tool-use-preview", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Meta
        provider="Groq", name="llama-3.1-70b-versatile", icon="Groq", deprecated=True
    ),
    create_model_metadata(  # Mistral
        provider="Groq", name="mixtral-8x7b-32768", icon="Groq", deprecated=True
    ),
    # ===== UNSUPPORTED MODELS =====
    # Audio/TTS/Guard models that should not appear in LLM model lists
    # The dynamic system automatically filters these out
    create_model_metadata(  # Mistral
        provider="Groq", name="mistral-saba-24b", icon="Groq", not_supported=True
    ),
    create_model_metadata(  # Playht, Inc
        provider="Groq", name="playai-tts", icon="Groq", not_supported=True
    ),
    create_model_metadata(  # Playht, Inc
        provider="Groq", name="playai-tts-arabic", icon="Groq", not_supported=True
    ),
    create_model_metadata(  # OpenAI
        provider="Groq", name="whisper-large-v3", icon="Groq", not_supported=True
    ),
    create_model_metadata(  # OpenAI
        provider="Groq", name="whisper-large-v3-turbo", icon="Groq", not_supported=True
    ),
    create_model_metadata(  # Hugging Face
        provider="Groq", name="distil-whisper-large-v3-en", icon="Groq", not_supported=True
    ),
    create_model_metadata(  # Meta
        provider="Groq", name="meta-llama/llama-guard-4-12b", icon="Groq", not_supported=True
    ),
    create_model_metadata(  # Meta
        provider="Groq", name="meta-llama/llama-prompt-guard-2-86m", icon="Groq", not_supported=True
    ),
    create_model_metadata(  # Meta
        provider="Groq", name="meta-llama/llama-prompt-guard-2-22m", icon="Groq", not_supported=True
    ),
    create_model_metadata(  # OpenAI
        provider="Groq", name="openai/gpt-oss-safeguard-20b", icon="Groq", not_supported=True
    ),
]

# Generate backwards-compatible lists from the metadata
GROQ_PRODUCTION_MODELS = [
    metadata["name"]
    for metadata in GROQ_MODELS_DETAILED
    if not metadata.get("preview", False)
    and not metadata.get("deprecated", False)
    and not metadata.get("not_supported", False)
]

GROQ_PREVIEW_MODELS = [metadata["name"] for metadata in GROQ_MODELS_DETAILED if metadata.get("preview", False)]

DEPRECATED_GROQ_MODELS = [metadata["name"] for metadata in GROQ_MODELS_DETAILED if metadata.get("deprecated", False)]

UNSUPPORTED_GROQ_MODELS = [
    metadata["name"] for metadata in GROQ_MODELS_DETAILED if metadata.get("not_supported", False)
]

TOOL_CALLING_UNSUPPORTED_GROQ_MODELS = [
    metadata["name"]
    for metadata in GROQ_MODELS_DETAILED
    if not metadata.get("tool_calling", False)
    and not metadata.get("not_supported", False)
    and not metadata.get("deprecated", False)
]

# Combined list of all current models for backward compatibility
GROQ_MODELS = GROQ_PRODUCTION_MODELS + GROQ_PREVIEW_MODELS

# For reverse compatibility
MODEL_NAMES = GROQ_MODELS
