from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
CEREBRAS_MODELS_DETAILED = [
    # Cerebras Models
    create_model_metadata(provider="🧠 Cerebras", name="llama-4-scout-17b-16e-instruct", icon="🧠", tool_calling=True),
    create_model_metadata(provider="🧠 Cerebras", name="llama3.1-8b", icon="🧠", tool_calling=True),
    create_model_metadata(provider="🧠 Cerebras", name="llama-3.3-70b", icon="🧠", tool_calling=True),
    create_model_metadata(provider="🧠 Cerebras", name="qwen-3-32b", icon="🧠", tool_calling=True),
    create_model_metadata(
        provider="🧠 Cerebras", name="deepseek-r1-distill-llama-70b", icon="🧠", tool_calling=True, preview=True
    ),
]

CEREBRAS_CHAT_MODEL_NAMES = [
    metadata["name"]
    for metadata in CEREBRAS_MODELS_DETAILED
    if not metadata.get("not_supported", False)
    and not metadata.get("reasoning", False)
    and not metadata.get("search", False)
]

CEREBRAS_REASONING_MODEL_NAMES = [
    metadata["name"]
    for metadata in CEREBRAS_MODELS_DETAILED
    if metadata.get("reasoning", False) and not metadata.get("not_supported", False)
]


# Backwards compatibility
MODEL_NAMES = CEREBRAS_CHAT_MODEL_NAMES
