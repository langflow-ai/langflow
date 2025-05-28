from .model_metadata import ModelMetadata, create_model_metadata

# Unified model metadata - single source of truth
GROQ_MODELS_DETAILED = {
    # Production Models - Stable and reliable for production use
    "gemma2-9b-it": create_model_metadata(  # Google
        provider="Groq",
        name="gemma2-9b-it",
        icon="Groq",
        tool_calling=True
    ),
    "llama-3.3-70b-versatile": create_model_metadata(  # Meta
        provider="Groq",
        name="llama-3.3-70b-versatile", 
        icon="Groq",
        tool_calling=True
    ),
    "llama-3.1-8b-instant": create_model_metadata(  # Meta
        provider="Groq",
        name="llama-3.1-8b-instant",
        icon="Groq"
    ),
    "llama-guard-3-8b": create_model_metadata(  # Meta
        provider="Groq", 
        name="llama-guard-3-8b",
        icon="Groq"
    ),
    "llama3-70b-8192": create_model_metadata(  # Meta
        provider="Groq",
        name="llama3-70b-8192",
        icon="Groq"
    ),
    "llama3-8b-8192": create_model_metadata(  # Meta
        provider="Groq",
        name="llama3-8b-8192",
        icon="Groq"
    ),
    
    # Preview Models - For evaluation purposes only
    "meta-llama/llama-4-scout-17b-16e-instruct": create_model_metadata(  # Meta
        provider="Groq",
        name="meta-llama/llama-4-scout-17b-16e-instruct",
        icon="Groq",
        tool_calling=True,
        preview=True
    ),
    "meta-llama/llama-4-maverick-17b-128e-instruct": create_model_metadata(  # Meta
        provider="Groq",
        name="meta-llama/llama-4-maverick-17b-128e-instruct", 
        icon="Groq",
        tool_calling=True,
        preview=True
    ),
    "qwen-qwq-32b": create_model_metadata(  # Alibaba Cloud
        provider="Groq",
        name="qwen-qwq-32b",
        icon="Groq",
        tool_calling=True,
        preview=True
    ),
    "qwen-2.5-coder-32b": create_model_metadata(  # Alibaba Cloud
        provider="Groq",
        name="qwen-2.5-coder-32b",
        icon="Groq", 
        tool_calling=True,
        preview=True
    ),
    "qwen-2.5-32b": create_model_metadata(  # Alibaba Cloud
        provider="Groq",
        name="qwen-2.5-32b",
        icon="Groq",
        tool_calling=True,
        preview=True
    ),
    "deepseek-r1-distill-qwen-32b": create_model_metadata(  # DeepSeek
        provider="Groq",
        name="deepseek-r1-distill-qwen-32b",
        icon="Groq",
        tool_calling=True,
        preview=True
    ),
    "deepseek-r1-distill-llama-70b": create_model_metadata(  # DeepSeek
        provider="Groq",
        name="deepseek-r1-distill-llama-70b",
        icon="Groq",
        preview=True
    ),
    "llama-3.3-70b-specdec": create_model_metadata(  # Meta
        provider="Groq",
        name="llama-3.3-70b-specdec",
        icon="Groq",
        tool_calling=True,
        preview=True
    ),
    "llama-3.2-1b-preview": create_model_metadata(  # Meta
        provider="Groq", 
        name="llama-3.2-1b-preview",
        icon="Groq",
        tool_calling=True,
        preview=True
    ),
    "llama-3.2-3b-preview": create_model_metadata(  # Meta
        provider="Groq",
        name="llama-3.2-3b-preview",
        icon="Groq",
        tool_calling=True,
        preview=True
    ),
    "llama-3.2-11b-vision-preview": create_model_metadata(  # Meta
        provider="Groq",
        name="llama-3.2-11b-vision-preview",
        icon="Groq",
        preview=True
    ),
    "llama-3.2-90b-vision-preview": create_model_metadata(  # Meta
        provider="Groq",
        name="llama-3.2-90b-vision-preview",
        icon="Groq",
        tool_calling=True,
        preview=True
    ),
    "allam-2-7b": create_model_metadata(  # Saudi Data and AI Authority (SDAIA)
        provider="Groq",
        name="allam-2-7b",
        icon="Groq",
        preview=True
    ),
    
    # Deprecated Models - Previously available but now removed
    "gemma-7b-it": create_model_metadata(  # Google
        provider="Groq",
        name="gemma-7b-it",
        icon="Groq",
        tool_calling=True,
        deprecated=True
    ),
    "llama3-groq-70b-8192-tool-use-preview": create_model_metadata(  # Groq
        provider="Groq",
        name="llama3-groq-70b-8192-tool-use-preview",
        icon="Groq",
        tool_calling=True,
        deprecated=True
    ),
    "llama3-groq-8b-8192-tool-use-preview": create_model_metadata(  # Groq
        provider="Groq",
        name="llama3-groq-8b-8192-tool-use-preview",
        icon="Groq",
        tool_calling=True,
        deprecated=True
    ),
    "llama-3.1-70b-versatile": create_model_metadata(  # Meta
        provider="Groq",
        name="llama-3.1-70b-versatile",
        icon="Groq",
        tool_calling=True,
        deprecated=True
    ),
    "mixtral-8x7b-32768": create_model_metadata(  # Mistral
        provider="Groq",
        name="mixtral-8x7b-32768",
        icon="Groq",
        tool_calling=True,
        deprecated=True
    ),
    
    # Unsupported Models
    "mistral-saba-24b": create_model_metadata(  # Mistral
        provider="Groq",
        name="mistral-saba-24b",
        icon="Groq",
        not_supported=True
    ),
    "playai-tts": create_model_metadata(  # Playht, Inc
        provider="Groq",
        name="playai-tts",
        icon="Groq", 
        not_supported=True
    ),
    "playai-tts-arabic": create_model_metadata(  # Playht, Inc
        provider="Groq",
        name="playai-tts-arabic",
        icon="Groq",
        not_supported=True
    ),
    "whisper-large-v3": create_model_metadata(  # OpenAI
        provider="Groq",
        name="whisper-large-v3",
        icon="Groq",
        not_supported=True
    ),
    "whisper-large-v3-turbo": create_model_metadata(  # OpenAI
        provider="Groq",
        name="whisper-large-v3-turbo",
        icon="Groq",
        not_supported=True
    ),
    "distil-whisper-large-v3-en": create_model_metadata(  # HuggingFace
        provider="Groq",
        name="distil-whisper-large-v3-en",
        icon="Groq",
        not_supported=True
    ),
}

# Generate backwards-compatible lists from the metadata
GROQ_PRODUCTION_MODELS = [
    model_name for model_name, metadata in GROQ_MODELS_DETAILED.items()
    if not metadata.get('preview', False) and not metadata.get('deprecated', False) and not metadata.get('not_supported', False)
]

GROQ_PREVIEW_MODELS = [
    model_name for model_name, metadata in GROQ_MODELS_DETAILED.items()
    if metadata.get('preview', False)
]

DEPRECATED_GROQ_MODELS = [
    model_name for model_name, metadata in GROQ_MODELS_DETAILED.items()
    if metadata.get('deprecated', False)
]

UNSUPPORTED_GROQ_MODELS = [
    model_name for model_name, metadata in GROQ_MODELS_DETAILED.items()
    if metadata.get('not_supported', False)
]

TOOL_CALLING_UNSUPPORTED_GROQ_MODELS = [
    model_name for model_name, metadata in GROQ_MODELS_DETAILED.items()
    if not metadata.get('tool_calling', False) and not metadata.get('not_supported', False) and not metadata.get('deprecated', False)
]

# Combined list of all current models for backward compatibility
GROQ_MODELS = GROQ_PRODUCTION_MODELS + GROQ_PREVIEW_MODELS

# For reverse compatibility
MODEL_NAMES = GROQ_MODELS
