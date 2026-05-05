"""HuggingFace local model catalog (GGUF / llama-cpp backend).

Curated list of small/efficient GGUF models that run well on a typical laptop
(8-16 GB RAM, CPU-only). Each entry uses a short slug (``display_name``) for
the UI — matching the Ollama convention — while ``name`` keeps the canonical
HuggingFace repo id needed for downloads.

Onboarding still ships exactly one ``default=True`` entry so a fresh user
sees a single toggle. The rest light up on demand: flip them on in the
provider settings or call ``POST /api/v1/models/huggingface/download`` with
any GGUF repo id.

We use GGUF + llama-cpp-python instead of safetensors + transformers because
the transformers/torch path is unstable on macOS arm64 + Python 3.12 (worker
SIGSEGVs at first device init).
"""

from .huggingface_chat_model import DEFAULT_HUGGINGFACE_MODEL
from .model_metadata import create_model_metadata

# Curated, laptop-friendly GGUF catalog. Sizes are Q4_K_M unless noted.
# Tool-calling flags reflect what the underlying base model supports
# reasonably well — small models that *advertise* tool calling but trip on
# real-world tools are left as ``False``.
HUGGINGFACE_MODELS_DETAILED = [
    # Bundled default — tiny, ~270MB, CPU-fast, no tool calling.
    create_model_metadata(
        provider="HuggingFace",
        name=DEFAULT_HUGGINGFACE_MODEL,
        display_name="smollm2",
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
