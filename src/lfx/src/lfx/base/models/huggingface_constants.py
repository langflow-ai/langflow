"""HuggingFace local model catalog (GGUF / llama-cpp backend).

The bundled catalog ships exactly one small GGUF model so onboarding stays
simple: the user sees a single toggle, flips it, and the backend pulls the
weights to ``~/.cache/huggingface/hub`` automatically. We use GGUF +
llama-cpp-python instead of safetensors + transformers because the
transformers/torch path is unstable on macOS arm64 + Python 3.12 (worker
SIGSEGVs at first device init).

Additional models are added by calling ``POST /api/v1/models/huggingface/
download`` with any GGUF repo id.
"""

from .huggingface_chat_model import DEFAULT_HUGGINGFACE_MODEL
from .model_metadata import create_model_metadata

HUGGINGFACE_MODELS_DETAILED = [
    create_model_metadata(
        provider="HuggingFace",
        name=DEFAULT_HUGGINGFACE_MODEL,
        icon="HuggingFace",
        tool_calling=False,
        default=True,
    ),
]

HUGGINGFACE_MODEL_NAMES = [metadata["name"] for metadata in HUGGINGFACE_MODELS_DETAILED]

__all__ = [
    "DEFAULT_HUGGINGFACE_MODEL",
    "HUGGINGFACE_MODELS_DETAILED",
    "HUGGINGFACE_MODEL_NAMES",
]
