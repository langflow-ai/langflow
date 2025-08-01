import sys

# Base components that are always available
from .nvidia import NVIDIAModelComponent
from .nvidia_embedding import NVIDIAEmbeddingsComponent
from .nvidia_rerank import NvidiaRerankComponent

# Start with base components that are always available
__all__ = [
    "NVIDIAEmbeddingsComponent",
    "NVIDIAModelComponent",
    "NvidiaRerankComponent",
]

# Platform-specific components
if sys.platform == "win32":
    from .system_assist import NvidiaSystemAssistComponent

    __all__ += ["NvidiaSystemAssistComponent"]

# Optional dependency components
# Try to import nemoguardrails component, but don't fail if not available
try:
    from .nemo_guardrails import NVIDIANeMoGuardrailsComponent

    __all__ += ["NVIDIANeMoGuardrailsComponent"]
except ImportError:
    pass

# Try to import nv-ingest component, but don't fail if not available
try:
    from .nvidia_ingest import NvidiaIngestComponent

    __all__ += ["NvidiaIngestComponent"]
except ImportError:
    pass
