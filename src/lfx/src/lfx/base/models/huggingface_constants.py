"""HuggingFace local model catalog.

The bundled catalog ships exactly one small CPU-friendly model so onboarding
stays simple: the user sees a single toggle, flips it, and the backend pulls
the weights to ``~/.cache/huggingface/hub`` automatically.

Additional models are not surfaced here — they're installed through the
``POST /api/v1/models/huggingface/download`` endpoint, which downloads any
HF repo id on demand and wires it into the user's enabled-models list.
"""

from .model_metadata import create_model_metadata

# Default bundled model. Small (~720MB), fast on CPU, decent instruction-following.
DEFAULT_HUGGINGFACE_MODEL = "HuggingFaceTB/SmolLM2-360M-Instruct"

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
