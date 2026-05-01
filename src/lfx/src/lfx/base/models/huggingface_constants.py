"""HuggingFace local model catalog.

These models run on the user's machine via the HuggingFace pipeline backend.
Sizes shown are *approximate* download sizes for the safetensors weights and
are intentionally biased toward small CPU-friendly checkpoints — the default
ships pre-selected so a fresh install can answer prompts without further
configuration.
"""

from .model_metadata import create_model_metadata

# Default bundled model. Small (~720MB), fast on CPU, decent instruction-following.
DEFAULT_HUGGINGFACE_MODEL = "HuggingFaceTB/SmolLM2-360M-Instruct"

# Single source of truth for the HuggingFace provider's local model offerings.
# Order matters: the first 5 entries are auto-marked as `default=True` by the
# unified catalog and surface in the dropdown without further action.
HUGGINGFACE_MODELS_DETAILED = [
    # --- Tiny, ultra-fast (CPU-friendly defaults) -----------------------------
    create_model_metadata(
        provider="HuggingFace",
        name=DEFAULT_HUGGINGFACE_MODEL,  # ~720MB
        icon="HuggingFace",
        tool_calling=False,
    ),
    create_model_metadata(
        provider="HuggingFace",
        name="HuggingFaceTB/SmolLM2-135M-Instruct",  # ~270MB
        icon="HuggingFace",
        tool_calling=False,
    ),
    create_model_metadata(
        provider="HuggingFace",
        name="Qwen/Qwen2.5-0.5B-Instruct",  # ~1GB
        icon="HuggingFace",
        tool_calling=False,
    ),
    create_model_metadata(
        provider="HuggingFace",
        name="HuggingFaceTB/SmolLM2-1.7B-Instruct",  # ~3.4GB
        icon="HuggingFace",
        tool_calling=False,
    ),
    create_model_metadata(
        provider="HuggingFace",
        name="Qwen/Qwen2.5-1.5B-Instruct",  # ~3GB
        icon="HuggingFace",
        tool_calling=False,
    ),
    # --- Larger / gated (require an HF token to download) ---------------------
    create_model_metadata(
        provider="HuggingFace",
        name="meta-llama/Llama-3.2-1B-Instruct",  # ~2.4GB, gated
        icon="HuggingFace",
        tool_calling=False,
    ),
    create_model_metadata(
        provider="HuggingFace",
        name="meta-llama/Llama-3.2-3B-Instruct",  # ~6.4GB, gated
        icon="HuggingFace",
        tool_calling=False,
    ),
    create_model_metadata(
        provider="HuggingFace",
        name="microsoft/Phi-3.5-mini-instruct",  # ~7.6GB
        icon="HuggingFace",
        tool_calling=False,
    ),
]

HUGGINGFACE_MODEL_NAMES = [metadata["name"] for metadata in HUGGINGFACE_MODELS_DETAILED]
