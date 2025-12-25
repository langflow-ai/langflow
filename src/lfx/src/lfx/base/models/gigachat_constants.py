from .model_metadata import create_model_metadata

GIGACHAT_MODELS_DETAILED = [
    create_model_metadata(
        provider="salutedevices", name="GigaChat", icon="GigaChat", tool_calling=False, deprecated=True
    ),
    create_model_metadata(
        provider="salutedevices", name="GigaChat-Plus", icon="GigaChat", tool_calling=False, deprecated=True
    ),
    create_model_metadata(
        provider="salutedevices", name="GigaChat-Pro", icon="GigaChat", tool_calling=False, deprecated=True
    ),
    create_model_metadata(
        provider="salutedevices",
        name="GigaChat-Pro-preview",
        icon="GigaChat",
        tool_calling=False,
        deprecated=True,
        preview=True,
    ),
    create_model_metadata(
        provider="salutedevices", name="GigaChat-Max", icon="GigaChat", tool_calling=False, deprecated=True
    ),
    create_model_metadata(
        provider="salutedevices",
        name="GigaChat-Max-preview",
        icon="GigaChat",
        tool_calling=False,
        deprecated=True,
        preview=True,
    ),
    create_model_metadata(provider="salutedevices", name="GigaChat-2", icon="GigaChat", tool_calling=True),
    create_model_metadata(provider="salutedevices", name="GigaChat-2-Pro", icon="GigaChat", tool_calling=True),
    create_model_metadata(provider="salutedevices", name="GigaChat-2-Max", icon="GigaChat", tool_calling=True),
]
GIGACHAT_CHAT_MODEL_NAMES = [
    metadata["name"] for metadata in GIGACHAT_MODELS_DETAILED if not metadata.get("deprecated", False)
]
GIGACHAT_SCOPES = [
    "GIGACHAT_API_PERS",
    "GIGACHAT_API_CORP",
    "GIGACHAT_API_B2B",
]
GIGACHAT_EMBEDDING_MODEL_NAMES = ["EmbeddingsGigaR", "Embeddings", "Embeddings-2"]
MODEL_NAMES = GIGACHAT_CHAT_MODEL_NAMES
