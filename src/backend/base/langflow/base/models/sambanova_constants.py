from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
SAMBANOVA_MODELS_DETAILED = [
    create_model_metadata(  # Meta
        provider="SambaNova", name="Meta-Llama-3.3-70B-Instruct", icon="SambaNova", tool_calling=True
    ),
    create_model_metadata(  # Meta
        provider="SambaNova",
        name="Llama-4-Maverick-17B-128E-Instruct",
        icon="SambaNova",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(  # Meta
        provider="SambaNova", name="Meta-Llama-3.1-8B-Instruct", icon="SambaNova"
    ),
    create_model_metadata(  # Alibaba Cloud
        provider="SambaNova",
        name="Qwen3-32B",
        icon="SambaNova",
        tool_calling=True,
        preview=True,
    ),
    create_model_metadata(  # DeepSeek
        provider="SambaNova", name="DeepSeek-V3-0324", icon="SambaNova", tool_calling=True
    ),
    create_model_metadata(  # DeepSeek
        provider="SambaNova", name="DeepSeek-R1", icon="SambaNova"
    ),
]

SAMBANOVA_PRODUCTION_MODELS = [
    metadata["name"]
    for metadata in SAMBANOVA_MODELS_DETAILED
    if not metadata.get("preview", False)
    and not metadata.get("deprecated", False)
    and not metadata.get("not_supported", False)
]

SAMBANOVA_PREVIEW_MODELS = [
    metadata["name"] for metadata in SAMBANOVA_MODELS_DETAILED if metadata.get("preview", False)
]

TOOL_CALLING_UNSUPPORTED_SAMBANOVA_MODELS = [
    metadata["name"]
    for metadata in SAMBANOVA_MODELS_DETAILED
    if not metadata.get("tool_calling", False)
    and not metadata.get("not_supported", False)
    and not metadata.get("deprecated", False)
]

SAMBANOVA_MODEL_NAMES = SAMBANOVA_PRODUCTION_MODELS + SAMBANOVA_PREVIEW_MODELS

SAMBANOVA_EMBEDDING_MODEL_NAMES = [
    "E5-Mistral-7B-Instruct",
]

MODEL_NAMES = SAMBANOVA_MODEL_NAMES
