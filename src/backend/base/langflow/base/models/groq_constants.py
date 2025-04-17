# Production Models - Stable and reliable for production use
GROQ_PRODUCTION_MODELS = [
    "gemma2-9b-it",  # Google
    "llama-3.3-70b-versatile",  # Meta
    "llama-3.1-8b-instant",  # Meta
    "llama-guard-3-8b",  # Meta
    "llama3-70b-8192",  # Meta
    "llama3-8b-8192",  # Meta
]

# Preview Models - For evaluation purposes only
GROQ_PREVIEW_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",  # Meta
    "meta-llama/llama-4-maverick-17b-128e-instruct",  # Meta
    "qwen-qwq-32b",  # Alibaba Cloud
    "qwen-2.5-coder-32b",  # Alibaba Cloud
    "qwen-2.5-32b",  # Alibaba Cloud
    "deepseek-r1-distill-qwen-32b",  # DeepSeek
    "deepseek-r1-distill-llama-70b",  # DeepSeek
    "llama-3.3-70b-specdec",  # Meta
    "llama-3.2-1b-preview",  # Meta
    "llama-3.2-3b-preview",  # Meta
    "llama-3.2-11b-vision-preview",  # Meta
    "llama-3.2-90b-vision-preview",  # Meta
    "allam-2-7b",  # Saudi Data and AI Authority (SDAIA)
]

# Deprecated Models - Previously available but now removed
DEPRECATED_GROQ_MODELS = [
    "gemma-7b-it",  # Google
    "llama3-groq-70b-8192-tool-use-preview",  # Groq
    "llama3-groq-8b-8192-tool-use-preview",  # Groq
    "llama-3.1-70b-versatile",  # Meta
    "mixtral-8x7b-32768",  # Mistral
]

UNSUPPORTED_GROQ_MODELS = [
    "mistral-saba-24b",  # Mistral
    "playai-tts",  # Playht, Inc
    "playai-tts-arabic",  # Playht, Inc
    "whisper-large-v3",  # OpenAI
    "whisper-large-v3-turbo",  # OpenAI
    "distil-whisper-large-v3-en",  # HuggingFace
]

TOOL_CALLING_UNSUPPORTED_GROQ_MODELS = [
    "allam-2-7b",  # Saudi Data and AI Authority (SDAIA)
    "llama-3.1-8b-instant",  # Meta Slow Response
    "llama-guard-3-8b",  # Meta
    "llama-3.2-11b-vision-preview",  # Meta
    "llama3-8b-8192",  # Meta
    "llama3-70b-8192",  # Meta
    "deepseek-r1-distill-llama-70b",  # DeepSeek
]
# Combined list of all current models for backward compatibility
GROQ_MODELS = GROQ_PRODUCTION_MODELS + GROQ_PREVIEW_MODELS

# For reverse compatibility
MODEL_NAMES = GROQ_MODELS
