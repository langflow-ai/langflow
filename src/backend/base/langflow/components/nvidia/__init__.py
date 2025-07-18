import sys

from .nvidia import NVIDIAModelComponent
from .nvidia_embedding import NVIDIAEmbeddingsComponent
from .nvidia_ingest import NvidiaIngestComponent
from .nvidia_rerank import NvidiaRerankComponent

# Try to import nemoguardrails component, but don't fail if not available
try:
    from .nemo_guardrails import NVIDIANeMoGuardrailsComponent

    NEMOGUARDRAILS_AVAILABLE = True
except ImportError:
    NEMOGUARDRAILS_AVAILABLE = False

if sys.platform == "win32":
    from .system_assist import NvidiaSystemAssistComponent

    __all__ = [
        "NVIDIAEmbeddingsComponent",
        "NVIDIAModelComponent",
        "NvidiaIngestComponent",
        "NvidiaRerankComponent",
        "NvidiaSystemAssistComponent",
    ]
    if NEMOGUARDRAILS_AVAILABLE:
        __all__ += ["NVIDIANeMoGuardrailsComponent"]
else:
    __all__ = [
        "NVIDIAEmbeddingsComponent",
        "NVIDIAModelComponent",
        "NvidiaIngestComponent",
        "NvidiaRerankComponent",
    ]
    if NEMOGUARDRAILS_AVAILABLE:
        __all__ += ["NVIDIANeMoGuardrailsComponent"]
