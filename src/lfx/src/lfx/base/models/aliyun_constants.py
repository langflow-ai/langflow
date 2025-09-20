from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
ALIYUN_MODELS_DETAILED = [
    # Qwen3.0
    create_model_metadata(
        provider="Aliyun",
        name="qwen-flash",
        icon="Aliyun",
        tool_calling=True,
        reasoning=True,
    ),
    create_model_metadata(
        provider="Aliyun",
        name="qwen-plus",
        icon="Aliyun",
        tool_calling=True,
        reasoning=True,
    ),
    create_model_metadata(
        provider="Aliyun",
        name="qwen3-coder-plus",
        icon="Aliyun",
        tool_calling=True,
        reasoning=True,
    ),
    # Qwen2.5
    create_model_metadata(
        provider="Aliyun",
        name="qwen-max",
        icon="Aliyun",
        tool_calling=True,
        reasoning=True,
    ),
    # PREVIEW
    create_model_metadata(
        provider="Aliyun",
        name="qwen3-max-preview",
        icon="Aliyun",
        tool_calling=True,
        reasoning=True,
    ),
]
ALIYUN_CHAT_MODEL_NAMES = [metadata["name"] for metadata in ALIYUN_MODELS_DETAILED]

ALIYUN_EMBEDDING_MODEL_NAMES = [
    "text-embedding-v4",
    "text-embedding-v3",
]

# Backwards compatibility
MODEL_NAMES = ALIYUN_CHAT_MODEL_NAMES
ALIYUN_MODEL_NAMES = ALIYUN_CHAT_MODEL_NAMES
